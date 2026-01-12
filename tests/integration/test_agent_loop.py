"""Integration tests for agent loop"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from cortex.agent import Cortex
from cortex.models import PermissionMode
from cortex.config import AgentConfig
from tests.fixtures.mock_ollama import create_mock_response, create_tool_call


@pytest.fixture
def mock_provider():
    """Mock model provider"""
    mock = MagicMock()
    yield mock


def test_agent_completes_simple_task(tmp_path, mock_provider):
    """Test agent completes a simple task"""
    # Setup: Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    # Mock provider responses
    # 1. Agent decides to read the file
    mock_provider.chat.return_value = create_mock_response(
        tool_calls=[create_tool_call("read_file", {"path": "test.txt"})]
    )
    mock_provider.supports_streaming.return_value = False
    mock_provider.normalize_model_name.return_value = "test-model"
    mock_provider.validate_api_key.return_value = True

    # Create agent with mocked provider
    with patch("cortex.agent.ProviderFactory.get_provider", return_value=mock_provider):
        agent = Cortex(
            model="test-model",
            project_dir=str(tmp_path),
            permission_mode=PermissionMode.AUTO_APPROVE,
        )

        # Process message
        agent._process_message("read test.txt")

        # Verify file was read
        history = agent.get_conversation_history()
        assert len(history) > 1  # Should have system + user + assistant + tool result


def test_agent_handles_tool_errors(tmp_path, mock_provider):
    """Test agent handles tool errors gracefully"""
    # Mock provider to call read_file on non-existent file
    mock_provider.chat.return_value = create_mock_response(
        tool_calls=[create_tool_call("read_file", {"path": "nonexistent.txt"})]
    )
    mock_provider.supports_streaming.return_value = False
    mock_provider.normalize_model_name.return_value = "test-model"
    mock_provider.validate_api_key.return_value = True

    with patch("cortex.agent.ProviderFactory.get_provider", return_value=mock_provider):
        agent = Cortex(
            model="test-model",
            project_dir=str(tmp_path),
            permission_mode=PermissionMode.AUTO_APPROVE,
        )

        # Process message
        agent._process_message("read nonexistent.txt")

        # Verify error was handled
        history = agent.get_conversation_history()
        # Should have tool result with error
        tool_results = [msg for msg in history if msg.get("role") == "tool"]
        assert len(tool_results) > 0
        import json

        tool_result = json.loads(tool_results[0]["content"])
        assert tool_result["success"] is False


def test_agent_loop_guard_prevents_infinite_loop(tmp_path, mock_provider):
    """Test that loop guards prevent infinite loops"""
    # Mock provider to repeatedly call same tool
    mock_provider.chat.return_value = create_mock_response(
        tool_calls=[create_tool_call("read_file", {"path": "nonexistent.txt"})]
    )
    mock_provider.supports_streaming.return_value = False
    mock_provider.normalize_model_name.return_value = "test-model"
    mock_provider.validate_api_key.return_value = True

    with patch("cortex.agent.ProviderFactory.get_provider", return_value=mock_provider):
        agent = Cortex(
            model="test-model",
            project_dir=str(tmp_path),
            permission_mode=PermissionMode.AUTO_APPROVE,
            config=AgentConfig(max_iterations=10),
        )

        # Process message - should stop due to loop guard
        agent._process_message("read nonexistent.txt")

        # Verify loop guard prevented infinite loop
        # (The agent should stop after detecting repeated errors)
        assert agent.loop_guard.iteration_count <= 10


def test_agent_handles_permission_denial(tmp_path, mock_provider):
    """Test agent handles permission denials correctly"""
    # Mock provider to try writing a file
    mock_provider.chat.return_value = create_mock_response(
        tool_calls=[create_tool_call("write_file", {"path": "test.txt", "content": "test"})]
    )
    mock_provider.supports_streaming.return_value = False
    mock_provider.normalize_model_name.return_value = "test-model"
    mock_provider.validate_api_key.return_value = True

    # Create agent in PLAN mode (should deny writes)
    with patch("cortex.agent.ProviderFactory.get_provider", return_value=mock_provider):
        agent = Cortex(
            model="test-model", project_dir=str(tmp_path), permission_mode=PermissionMode.PLAN
        )

        # Process message
        agent._process_message("write test.txt")

        # Verify permission denial
        history = agent.get_conversation_history()
        tool_results = [msg for msg in history if msg.get("role") == "tool"]
        if tool_results:
            import json

            tool_result = json.loads(tool_results[0]["content"])
            assert tool_result["success"] is False
            assert tool_result.get("permission_denied") is True
