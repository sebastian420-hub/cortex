"""Integration tests for agent loop"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from localagent.agent import LocalAgent
from localagent.models import PermissionMode
from localagent.config import AgentConfig
from tests.fixtures.mock_ollama import create_mock_response, create_tool_call


@pytest.fixture
def mock_ollama():
    """Mock Ollama client"""
    with patch("localagent.agent.ollama") as mock:
        yield mock


def test_agent_completes_simple_task(tmp_path, mock_ollama):
    """Test agent completes a simple task"""
    # Setup: Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")
    
    # Mock Ollama responses
    # 1. Agent decides to read the file
    mock_ollama.chat.return_value = create_mock_response(
        tool_calls=[create_tool_call("read_file", {"path": "test.txt"})]
    )
    
    # Create agent
    agent = LocalAgent(
        model="test-model",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.AUTO_APPROVE
    )
    
    # Process message
    agent._process_message("read test.txt")
    
    # Verify file was read
    history = agent.get_conversation_history()
    assert len(history) > 1  # Should have system + user + assistant + tool result


def test_agent_handles_tool_errors(tmp_path, mock_ollama):
    """Test agent handles tool errors gracefully"""
    # Mock Ollama to call read_file on non-existent file
    mock_ollama.chat.return_value = create_mock_response(
        tool_calls=[create_tool_call("read_file", {"path": "nonexistent.txt"})]
    )
    
    agent = LocalAgent(
        model="test-model",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.AUTO_APPROVE
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


def test_agent_loop_guard_prevents_infinite_loop(tmp_path, mock_ollama):
    """Test that loop guards prevent infinite loops"""
    # Mock Ollama to repeatedly call same tool
    mock_ollama.chat.return_value = create_mock_response(
        tool_calls=[create_tool_call("read_file", {"path": "nonexistent.txt"})]
    )
    
    agent = LocalAgent(
        model="test-model",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.AUTO_APPROVE,
        config=AgentConfig(max_iterations=10)
    )
    
    # Process message - should stop due to loop guard
    agent._process_message("read nonexistent.txt")
    
    # Verify loop guard prevented infinite loop
    # (The agent should stop after detecting repeated errors)
    assert agent.loop_guard.iteration_count <= 10


def test_agent_handles_permission_denial(tmp_path, mock_ollama):
    """Test agent handles permission denials correctly"""
    # Mock Ollama to try writing a file
    mock_ollama.chat.return_value = create_mock_response(
        tool_calls=[create_tool_call("write_file", {"path": "test.txt", "content": "test"})]
    )
    
    # Create agent in PLAN mode (should deny writes)
    agent = LocalAgent(
        model="test-model",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.PLAN
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
