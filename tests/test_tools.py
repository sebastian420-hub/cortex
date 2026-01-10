"""Tests for tool implementations"""

import pytest
from pathlib import Path
from cortex.tools import create_tool_instance
from cortex.models import PermissionMode


def test_read_file_tool(tmp_path, monkeypatch):
    """Test read_file tool"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    from cortex.ui.console import console
    tool = create_tool_instance("read_file", tmp_path, PermissionMode.NORMAL, console)
    result = tool.execute(path="test.txt")

    assert result["success"] is True
    # Content now includes line numbers (cat -n style)
    assert "Hello, World!" in result["content"]
    assert result["total_lines"] == 1


def test_write_file_tool(tmp_path, monkeypatch):
    """Test write_file tool"""
    from cortex.ui.console import console
    
    tool = create_tool_instance("write_file", tmp_path, PermissionMode.AUTO_APPROVE, console)
    result = tool.execute(path="test.txt", content="Test content")
    
    assert result["success"] is True
    assert (tmp_path / "test.txt").read_text() == "Test content"


def test_write_file_plan_mode(tmp_path):
    """Test that write_file is blocked in plan mode"""
    from cortex.ui.console import console
    
    tool = create_tool_instance("write_file", tmp_path, PermissionMode.PLAN, console)
    result = tool.execute(path="test.txt", content="Test content")
    
    assert result["success"] is False
    assert result["permission_denied"] is True
    assert "Plan mode" in result["reason"]
    assert result["action"] == "write_file"


def test_read_file_not_found(tmp_path):
    """Test read_file returns proper error format for missing file"""
    from cortex.ui.console import console
    from cortex.utils.errors import ErrorType
    
    tool = create_tool_instance("read_file", tmp_path, PermissionMode.NORMAL, console)
    result = tool.execute(path="nonexistent.txt")
    
    assert result["success"] is False
    assert result["error_type"] == ErrorType.NOT_FOUND
    assert "error" in result
    assert "retryable" in result
    assert result["retryable"] is False


def test_write_file_permission_denied(tmp_path):
    """Test write_file returns permission denial format"""
    from cortex.ui.console import console
    from cortex.utils.errors import ErrorType
    
    tool = create_tool_instance("write_file", tmp_path, PermissionMode.PLAN, console)
    result = tool.execute(path="test.txt", content="Test")
    
    assert result["success"] is False
    assert result["permission_denied"] is True
    assert result["error_type"] == ErrorType.PERMISSION
    assert result["action"] == "write_file"
    assert "reason" in result


def test_tool_result_validation(tmp_path):
    """Test that tool results have proper structure"""
    from cortex.ui.console import console
    
    tool = create_tool_instance("read_file", tmp_path, PermissionMode.NORMAL, console)
    
    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello")
    
    result = tool.execute(path="test.txt")
    
    # Success response should have success=True
    assert result["success"] is True
    assert "content" in result
    
    # Test error response structure
    result = tool.execute(path="nonexistent.txt")
    assert result["success"] is False
    assert "error" in result
    assert "error_type" in result
    assert "retryable" in result


def test_execute_command_retryable_error(tmp_path):
    """Test that execution errors are marked as retryable"""
    from cortex.ui.console import console
    from cortex.utils.errors import ErrorType
    
    tool = create_tool_instance("execute_command", tmp_path, PermissionMode.AUTO_APPROVE, console)
    # Use a command that will fail
    result = tool.execute(command="nonexistent_command_xyz", reason="test")
    
    assert result["success"] is False
    assert result["error_type"] in [ErrorType.EXECUTION, ErrorType.NOT_FOUND]
    assert result.get("retryable", False) is True


def test_list_files_tool(tmp_path):
    """Test list_files tool"""
    # Create some test files
    (tmp_path / "file1.txt").write_text("test")
    (tmp_path / "file2.py").write_text("test")
    (tmp_path / ".hidden").write_text("test")
    
    from cortex.ui.console import console
    tool = create_tool_instance("list_files", tmp_path, PermissionMode.NORMAL, console)
    result = tool.execute(path=".")
    
    assert result["success"] is True
    assert result["count"] == 2  # .hidden should be excluded
    assert "file1.txt" in result["files"]
    assert "file2.py" in result["files"]


def test_git_status_tool(tmp_path, monkeypatch):
    """Test git_status tool"""
    import subprocess
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "test.txt"], cwd=tmp_path, capture_output=True)
    
    from cortex.ui.console import console
    tool = create_tool_instance("git_status", tmp_path, PermissionMode.NORMAL, console)
    result = tool.execute()
    
    assert result["success"] is True
    assert "test.txt" in result["output"]

