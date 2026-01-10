"""Tests for Cortex class"""

import pytest
from pathlib import Path
from cortex.agent import Cortex
from cortex.models import PermissionMode
from cortex.config import AgentConfig


def test_agent_initialization(tmp_path):
    """Test agent initialization"""
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    assert agent.model == "llama3.2"
    assert agent.project_dir == tmp_path.resolve()
    assert agent.permission_mode == PermissionMode.NORMAL


def test_agent_load_project_context(tmp_path):
    """Test loading project context from AGENT.md"""
    agent_file = tmp_path / "AGENT.md"
    agent_file.write_text("# Project\n\nThis is a test project.")
    
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    assert "Project" in agent.project_context
    assert "test project" in agent.project_context


def test_agent_execute_tool_string_args(tmp_path):
    """Test that tool execution handles string JSON arguments"""
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.AUTO_APPROVE
    )

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello")

    # Test with string arguments (JSON)
    import json
    args_str = json.dumps({"path": "test.txt"})
    result = agent.execute_tool("read_file", args_str)

    assert result["success"] is True
    # Content now includes line numbers (cat -n style)
    assert "Hello" in result["content"]


def test_agent_clear_conversation(tmp_path):
    """Test clearing conversation"""
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    # Add some messages
    agent.conversation.add_user_message("Hello")
    agent.conversation.add_assistant_message("Hi")
    
    # Clear
    agent.clear_conversation()
    
    # Should only have system message
    history = agent.get_conversation_history()
    assert len(history) == 1
    assert history[0]["role"] == "system"

