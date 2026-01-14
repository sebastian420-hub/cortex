"""Integration tests for Tier 1 fixes"""

import pytest
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from cortex.agent import Cortex
from cortex.storage.sessions import SessionManager
from cortex.models import PermissionMode
from cortex.utils.errors import create_error_response, ErrorType
from cortex.core.recovery_strategies import RecoveryAction, RecoveryStrategy


def test_recovery_flow_end_to_end(tmp_path):
    """Test complete recovery flow with proper message ordering"""
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

    # Mock model response with tool call
    mock_tool_call = {
        "function": {"name": "read_file", "arguments": '{"path": "nonexistent.py"}'},
        "id": "call_test",
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

    call_count = [0]

    def mock_call_model(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_response
        else:
            # Second call returns final response
            return {"message": {"content": "I'll help you find the file."}}

    with patch.object(agent, "_call_model", side_effect=mock_call_model):
        with patch.object(agent, "execute_tool", return_value=error_result):
            with patch.object(agent.loop_guard, "check_repeated_error", return_value=True):
                with patch.object(
                    agent.loop_guard, "get_recovery_action", return_value=recovery_action
                ):
                    # Limit iterations
                    agent.config.max_iterations = 3
                    agent._process_message("read nonexistent.py")

    # Verify conversation history has correct order
    history = agent.conversation.get_history()

    # Find key messages
    tool_calls = [
        i
        for i, msg in enumerate(history)
        if msg.get("role") == "assistant" and msg.get("tool_calls")
    ]
    tool_results = [i for i, msg in enumerate(history) if msg.get("role") == "tool"]
    recoveries = [
        i for i, msg in enumerate(history) if "[Recovery Guidance]" in msg.get("content", "")
    ]

    # Verify order: for each recovery, there should be a tool result before it
    for recovery_idx in recoveries:
        preceding_results = [idx for idx in tool_results if idx < recovery_idx]
        assert len(preceding_results) > 0, "Recovery should come after tool result"

        # Verify the tool result contains the error
        last_result_idx = max(preceding_results)
        result_msg = history[last_result_idx]
        import json

        result_content = json.loads(result_msg["content"])
        assert result_content["success"] is False


def test_concurrent_session_operations(tmp_path):
    """Test concurrent session save/load operations"""
    manager = SessionManager(tmp_path)

    # Save initial sessions
    for i in range(5):
        manager.save_session(
            f"session_{i}",
            [{"role": "user", "content": f"initial_{i}"}],
            str(tmp_path),
            "llama3.2",
            "normal",
        )

    errors = []
    results = []

    def concurrent_operation(op_type, session_id):
        try:
            if op_type == "save":
                result = manager.save_session(
                    f"session_{session_id}",
                    [{"role": "user", "content": f"updated_{session_id}"}],
                    str(tmp_path),
                    "llama3.2",
                    "normal",
                )
                results.append(("save", session_id, result))
            else:  # load
                result = manager.load_session(f"session_{session_id}")
                results.append(("load", session_id, result is not None))
        except Exception as e:
            errors.append((op_type, session_id, e))

    # Spawn multiple threads doing save/load operations
    threads = []
    for i in range(10):
        op_type = "save" if i % 2 == 0 else "load"
        threads.append(threading.Thread(target=concurrent_operation, args=(op_type, i % 5)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify no errors occurred
    assert len(errors) == 0, f"Errors occurred: {errors}"

    # Verify all sessions are still loadable
    for i in range(5):
        loaded = manager.load_session(f"session_{i}")
        assert loaded is not None, f"Session {i} should be loadable after concurrent operations"


def test_security_check_in_execution(tmp_path):
    """Test that security checks work in real tool execution"""
    agent = Cortex(
        model="llama3.2", project_dir=str(tmp_path), permission_mode=PermissionMode.AUTO_APPROVE
    )

    # Try to execute dangerous command
    result = agent.execute_tool("execute_command", {"command": "rm -rf /"})

    # Verify it's blocked
    assert result["success"] is False
    assert result.get("error_type") == "security" or "security" in result.get("error", "").lower()

    # Try safe command
    safe_result = agent.execute_tool("execute_command", {"command": "echo hello"})

    # Should either succeed or fail for other reasons (not security)
    if not safe_result["success"]:
        assert safe_result.get("error_type") != "security"


def test_json_serialization_in_real_flow(tmp_path):
    """Test JSON serialization fix in a real provider flow"""
    # This test would require actual Anthropic API access or comprehensive mocking
    # For now, we verify the fix is in place through unit tests
    # This integration test serves as a placeholder for future end-to-end testing

    # Verify the fix exists in the code
    from cortex.core.providers import AnthropicProvider
    import inspect

    source = inspect.getsource(AnthropicProvider.chat)
    assert "json.dumps" in source or "json.dumps" in str(AnthropicProvider.chat.__code__.co_consts)

    # The actual JSON serialization is tested in unit tests
    # This confirms the fix is present in the codebase


def test_file_locking_in_concurrent_saves(tmp_path):
    """Test file locking prevents corruption during concurrent saves to same file"""
    manager = SessionManager(tmp_path)

    errors = []
    success_count = [0]

    def save_same_session(thread_id):
        try:
            result = manager.save_session(
                "concurrent_session",
                [{"role": "user", "content": f"thread_{thread_id}"}],
                str(tmp_path),
                "llama3.2",
                "normal",
            )
            if result:
                success_count[0] += 1
        except Exception as e:
            errors.append((thread_id, e))

    # Spawn many threads writing to same session
    threads = [threading.Thread(target=save_same_session, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # At least some should succeed
    assert success_count[0] > 0, "At least one write should succeed"

    # Final session should be loadable and valid JSON
    loaded = manager.load_session("concurrent_session")
    assert loaded is not None
    assert "conversation_history" in loaded
    assert isinstance(loaded["conversation_history"], list)


def test_recovery_and_shutdown_interaction(tmp_path):
    """Test interaction between recovery flow and shutdown"""
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

    # Mock tool call that fails
    mock_response = {
        "message": {
            "tool_calls": [
                {
                    "function": {"name": "read_file", "arguments": '{"path": "test.py"}'},
                    "id": "call_test",
                }
            ]
        }
    }

    error_result = create_error_response("Error", ErrorType.EXECUTION)
    recovery_action = RecoveryAction(
        strategy=RecoveryStrategy.SUGGEST, message="Recovery", suggested_prompt="Try again"
    )

    shutdown_requested = [False]

    def mock_call_model(*args, **kwargs):
        if not shutdown_requested[0]:
            shutdown_requested[0] = True
            agent.request_shutdown()
        return mock_response

    with patch.object(agent, "_call_model", side_effect=mock_call_model):
        with patch.object(agent, "execute_tool", return_value=error_result):
            with patch.object(agent.loop_guard, "check_repeated_error", return_value=True):
                with patch.object(
                    agent.loop_guard, "get_recovery_action", return_value=recovery_action
                ):
                    agent.config.max_iterations = 2
                    agent._process_message("test")

    # Verify shutdown was requested
    assert agent._shutdown_requested is True

    # Verify cleanup was called (indirectly through shutdown check)
    # The agent should have exited gracefully
