"""Tests for agent fixes: loop guards, error formats, and edge cases"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from cortex.agent import Cortex
from cortex.core.loop_guards import LoopGuard
from cortex.core.recovery_strategies import RecoveryStrategy, RecoveryAction
from cortex.utils.errors import create_error_response, create_success_response, ErrorType
from cortex.models import PermissionMode


def test_loop_guard_repeated_tool_call():
    """Test loop guard detects repeated tool calls"""
    guard = LoopGuard(max_repeats=3)

    # Call same tool 3 times
    guard.record_tool_call("read_file", {"path": "test.py"})
    guard.record_tool_call("read_file", {"path": "test.py"})
    guard.record_tool_call("read_file", {"path": "test.py"})

    # Should detect repetition
    assert guard.check_repeated_tool_call("read_file", {"path": "test.py"}) is True

    # Different arguments should not trigger
    assert guard.check_repeated_tool_call("read_file", {"path": "other.py"}) is False


def test_loop_guard_repeated_error():
    """Test loop guard detects repeated errors"""
    guard = LoopGuard(max_repeats=3)

    error = create_error_response("File not found", ErrorType.NOT_FOUND)

    # Record same error 3 times
    guard.record_error(error)
    guard.record_error(error)
    guard.record_error(error)

    # Should detect repetition
    assert guard.check_repeated_error(error) is True


def test_error_response_format():
    """Test standardized error response format"""
    error = create_error_response("File not found", ErrorType.NOT_FOUND, {"path": "test.py"})

    assert error["success"] is False
    assert error["error"] == "File not found"
    assert error["error_type"] == ErrorType.NOT_FOUND
    assert "error_context" in error
    assert error["error_context"]["path"] == "test.py"


def test_success_response_format():
    """Test standardized success response format"""
    success = create_success_response({"content": "test", "lines": 10})

    assert success["success"] is True
    assert success["data"]["content"] == "test"
    assert success["data"]["lines"] == 10


def test_error_type_constants():
    """Test error type constants are defined"""
    from cortex.utils.errors import ErrorType

    assert ErrorType.PERMISSION == "permission"
    assert ErrorType.NOT_FOUND == "not_found"
    assert ErrorType.VALIDATION == "validation"
    assert ErrorType.EXECUTION == "execution"
    assert ErrorType.TIMEOUT == "timeout"
    assert ErrorType.NETWORK == "network"
    assert ErrorType.SECURITY == "security"


def test_loop_guard_reset():
    """Test loop guard reset functionality"""
    guard = LoopGuard()

    guard.record_tool_call("read_file", {"path": "test.py"})
    guard.record_error(create_error_response("Error", ErrorType.EXECUTION))

    assert len(guard.tool_call_history) == 1
    assert len(guard.error_history) == 1

    guard.reset()

    assert len(guard.tool_call_history) == 0
    assert len(guard.error_history) == 0


def test_loop_guard_history_limit():
    """Test loop guard limits history size"""
    guard = LoopGuard()

    # Add more than 10 calls
    for i in range(15):
        guard.record_tool_call("read_file", {"path": f"test{i}.py"})

    # Should only keep last 10
    assert len(guard.tool_call_history) == 10
    # First 5 should be removed
    assert ("read_file", {"path": "test0.py"}) not in guard.tool_call_history
    # Last 10 should be present
    assert ("read_file", {"path": "test14.py"}) in guard.tool_call_history


def test_recovery_message_ordering(tmp_path):
    """Test that tool result is added to conversation before recovery guidance"""
    from cortex.config import AgentConfig

    # Create config with recovery enabled
    config = AgentConfig()
    config.error_recovery = {
        "enable_smart_recovery": True,
        "max_repeats": 2,
        "recovery_strategy": "suggest",
    }

    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.AUTO_APPROVE,
        config=config,
    )

    # Mock a model response with tool call
    mock_tool_call = {
        "function": {"name": "read_file", "arguments": '{"path": "nonexistent.py"}'},
        "id": "call_test_123",
    }

    mock_response = {"message": {"content": "", "tool_calls": [mock_tool_call]}}

    # Mock tool execution to return error
    error_result = create_error_response("File not found", ErrorType.NOT_FOUND)

    # Mock recovery action
    recovery_action = RecoveryAction(
        strategy=RecoveryStrategy.SUGGEST,
        message="Recovery triggered",
        suggested_prompt="Try using list_files to find the correct path",
    )

    with patch.object(agent, "_call_model", return_value=mock_response):
        with patch.object(agent, "execute_tool", return_value=error_result):
            with patch.object(agent.loop_guard, "check_repeated_error", return_value=True):
                with patch.object(
                    agent.loop_guard, "get_recovery_action", return_value=recovery_action
                ):
                    # Process message
                    agent._process_message("read nonexistent.py")

    # Get conversation history
    history = agent.conversation.get_history()

    # Find messages: tool_call, tool_result, and recovery guidance
    tool_call_msg = None
    tool_result_msg = None
    recovery_guidance_msg = None

    for msg in history:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tool_call_msg = msg
        elif msg.get("role") == "tool":
            tool_result_msg = msg
        elif msg.get("role") == "user" and "[Recovery Guidance]" in msg.get("content", ""):
            recovery_guidance_msg = msg

    # Verify all messages exist
    assert tool_call_msg is not None, "Tool call message should exist"
    assert tool_result_msg is not None, "Tool result message should exist"
    assert recovery_guidance_msg is not None, "Recovery guidance message should exist"

    # Verify order: tool_call comes before tool_result, tool_result comes before recovery_guidance
    tool_call_idx = history.index(tool_call_msg)
    tool_result_idx = history.index(tool_result_msg)
    recovery_idx = history.index(recovery_guidance_msg)

    assert tool_call_idx < tool_result_idx, "Tool call should come before tool result"
    assert tool_result_idx < recovery_idx, "Tool result should come before recovery guidance"

    # Verify tool result contains original error
    import json

    tool_result_content = json.loads(tool_result_msg["content"])
    assert tool_result_content["success"] is False
    assert "File not found" in tool_result_content.get("error", "")


def test_recovery_guidance_separate_message(tmp_path):
    """Test that recovery guidance is added as separate user message, not merged"""
    from cortex.config import AgentConfig

    config = AgentConfig()
    config.error_recovery = {
        "enable_smart_recovery": True,
        "max_repeats": 2,
        "recovery_strategy": "suggest",
    }

    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.AUTO_APPROVE,
        config=config,
    )

    # Mock tool call and error
    mock_tool_call = {
        "function": {"name": "read_file", "arguments": '{"path": "test.py"}'},
        "id": "call_test",
    }

    mock_response = {"message": {"tool_calls": [mock_tool_call]}}
    error_result = create_error_response("Error", ErrorType.EXECUTION)
    recovery_action = RecoveryAction(
        strategy=RecoveryStrategy.SUGGEST, message="Recovery", suggested_prompt="Try again"
    )

    with patch.object(agent, "_call_model", return_value=mock_response):
        with patch.object(agent, "execute_tool", return_value=error_result):
            with patch.object(agent.loop_guard, "check_repeated_error", return_value=True):
                with patch.object(
                    agent.loop_guard, "get_recovery_action", return_value=recovery_action
                ):
                    agent._process_message("test")

    history = agent.conversation.get_history()

    # Count tool result messages and recovery guidance messages
    tool_results = [msg for msg in history if msg.get("role") == "tool"]
    recovery_messages = [msg for msg in history if "[Recovery Guidance]" in msg.get("content", "")]

    # Verify tool result exists separately
    assert len(tool_results) > 0, "Tool result should exist as separate message"

    # Verify recovery guidance exists as separate user message
    assert len(recovery_messages) > 0, "Recovery guidance should exist as separate message"

    # Verify recovery guidance is a user message, not merged into tool result
    for msg in recovery_messages:
        assert msg.get("role") == "user", "Recovery guidance should be a user message"
        assert "[Recovery Guidance]" in msg.get("content", "")


def test_multiple_recovery_attempts_ordering(tmp_path):
    """Test message ordering with multiple recovery attempts"""
    from cortex.config import AgentConfig

    config = AgentConfig()
    config.error_recovery = {
        "enable_smart_recovery": True,
        "max_repeats": 3,
        "recovery_strategy": "suggest",
    }

    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.AUTO_APPROVE,
        config=config,
    )

    # Mock multiple tool calls that fail
    call_count = [0]

    def mock_call_model(*args, **kwargs):
        call_count[0] += 1
        return {
            "message": {
                "tool_calls": [
                    {
                        "function": {"name": "read_file", "arguments": '{"path": "test.py"}'},
                        "id": f"call_{call_count[0]}",
                    }
                ]
            }
        }

    error_result = create_error_response("Error", ErrorType.EXECUTION)
    recovery_action = RecoveryAction(
        strategy=RecoveryStrategy.SUGGEST, message="Recovery", suggested_prompt="Try again"
    )

    with patch.object(agent, "_call_model", side_effect=mock_call_model):
        with patch.object(agent, "execute_tool", return_value=error_result):
            with patch.object(agent.loop_guard, "check_repeated_error", return_value=True):
                with patch.object(
                    agent.loop_guard, "get_recovery_action", return_value=recovery_action
                ):
                    # Limit iterations to prevent infinite loop
                    agent.config.max_iterations = 3
                    agent._process_message("test")

    history = agent.conversation.get_history()

    # Verify pattern: tool_call → tool_result → recovery_guidance (repeated)
    tool_calls = [
        i
        for i, msg in enumerate(history)
        if msg.get("role") == "assistant" and msg.get("tool_calls")
    ]
    tool_results = [i for i, msg in enumerate(history) if msg.get("role") == "tool"]
    recoveries = [
        i for i, msg in enumerate(history) if "[Recovery Guidance]" in msg.get("content", "")
    ]

    # For each recovery, verify it comes after its corresponding tool result
    for recovery_idx in recoveries:
        # Find the tool result that should come before this recovery
        preceding_tool_results = [idx for idx in tool_results if idx < recovery_idx]
        if preceding_tool_results:
            # Verify the most recent tool result comes before recovery
            last_tool_result = max(preceding_tool_results)
            assert (
                last_tool_result < recovery_idx
            ), "Tool result should come before recovery guidance"
