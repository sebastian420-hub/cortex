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


# ============================================================================
# SECURITY TESTS - File Erasure Vulnerability Fixes
# ============================================================================

def test_write_file_empty_content(tmp_path):
    """Test that write_file rejects empty content (prevents file erasure)"""
    from cortex.ui.console import console
    from cortex.utils.errors import ErrorType
    
    tool = create_tool_instance("write_file", tmp_path, PermissionMode.AUTO_APPROVE, console)
    result = tool.execute(path="test.txt", content="")
    
    assert result["success"] is False
    assert result["error_type"] == ErrorType.VALIDATION
    assert "empty" in result["error"].lower()


def test_write_file_whitespace_only_content(tmp_path):
    """Test that write_file rejects whitespace-only content"""
    from cortex.ui.console import console
    from cortex.utils.errors import ErrorType
    
    tool = create_tool_instance("write_file", tmp_path, PermissionMode.AUTO_APPROVE, console)
    
    # Test with spaces
    result = tool.execute(path="test.txt", content="   ")
    assert result["success"] is False
    assert "empty" in result["error"].lower() or "whitespace" in result["error"].lower()
    
    # Test with newlines
    result = tool.execute(path="test.txt", content="\n\n\n")
    assert result["success"] is False
    assert "empty" in result["error"].lower() or "whitespace" in result["error"].lower()
    
    # Test with tabs
    result = tool.execute(path="test.txt", content="\t\t")
    assert result["success"] is False


def test_execute_command_python_truncate(tmp_path):
    """Test that dangerous Python patterns like truncate() are blocked"""
    from cortex.ui.console import console
    from cortex.utils.errors import ErrorType
    
    tool = create_tool_instance("execute_command", tmp_path, PermissionMode.AUTO_APPROVE, console)
    
    # Test truncate() pattern
    result = tool.execute(command='python -c "open(\'file.py\').truncate()"')
    assert result["success"] is False
    assert result["error_type"] == ErrorType.SECURITY
    assert "dangerous" in result["error"].lower() or "pattern" in result["error"].lower()
    assert "truncate" in result["error"].lower()


def test_execute_command_python_write_empty(tmp_path):
    """Test that Python write('') pattern is blocked"""
    from cortex.ui.console import console
    from cortex.utils.errors import ErrorType
    
    tool = create_tool_instance("execute_command", tmp_path, PermissionMode.AUTO_APPROVE, console)
    
    # Test write('') pattern
    result = tool.execute(command="python -c \"open('file.py', 'w').write('')\"")
    assert result["success"] is False
    assert result["error_type"] == ErrorType.SECURITY
    assert "dangerous" in result["error"].lower() or "pattern" in result["error"].lower()


def test_execute_command_python_remove(tmp_path):
    """Test that Python .remove() pattern is blocked"""
    from cortex.ui.console import console
    from cortex.utils.errors import ErrorType
    
    tool = create_tool_instance("execute_command", tmp_path, PermissionMode.AUTO_APPROVE, console)
    
    # Test .remove() pattern
    result = tool.execute(command="python -c \"import pathlib; pathlib.Path('file.py').remove()\"")
    assert result["success"] is False
    assert result["error_type"] == ErrorType.SECURITY


def test_execute_command_python_unlink(tmp_path):
    """Test that Python .unlink() pattern is blocked"""
    from cortex.ui.console import console
    from cortex.utils.errors import ErrorType
    
    tool = create_tool_instance("execute_command", tmp_path, PermissionMode.AUTO_APPROVE, console)
    
    # Test .unlink() pattern
    result = tool.execute(command="python -c \"import pathlib; pathlib.Path('file.py').unlink()\"")
    assert result["success"] is False
    assert result["error_type"] == ErrorType.SECURITY


def test_execute_command_python_safe(tmp_path):
    """Test that safe Python commands are allowed"""
    from cortex.ui.console import console
    
    tool = create_tool_instance("execute_command", tmp_path, PermissionMode.AUTO_APPROVE, console)
    
    # Test a safe Python command
    result = tool.execute(command='python -c "print(\'hello\')"')
    # Should not be blocked by security check (may fail for other reasons)
    assert result["error_type"] != "security" if not result["success"] else True


def test_edit_tool_replacement_verification(tmp_path):
    """Test that edit_tool verifies replacement actually occurred"""
    from cortex.ui.console import console
    from cortex.utils.errors import ErrorType
    
    # Create a test file
    test_file = tmp_path / "test.py"
    test_file.write_text("def function():\n    pass")
    
    tool = create_tool_instance("edit", tmp_path, PermissionMode.AUTO_APPROVE, console)
    
    # Try to replace with non-matching string
    result = tool.execute(
        file_path="test.py",
        old_string="def nonexistent(): pass",
        new_string="def new_function(): pass"
    )
    
    assert result["success"] is False
    assert result["error_type"] == ErrorType.VALIDATION
    assert "not found" in result["error"].lower()


def test_edit_tool_whitespace_mismatch(tmp_path):
    """Test that edit_tool handles whitespace mismatches properly"""
    from cortex.ui.console import console
    
    # Create a test file with tabs
    test_file = tmp_path / "test.py"
    test_file.write_text("def function():\n\tpass")  # Tab indentation
    
    tool = create_tool_instance("edit", tmp_path, PermissionMode.AUTO_APPROVE, console)
    
    # Try to replace with spaces (won't match)
    result = tool.execute(
        file_path="test.py",
        old_string="def function():\n    pass",  # Space indentation
        new_string="def function():\n    return None"
    )
    
    assert result["success"] is False
    assert "whitespace" in result["context"].get("hint", "").lower() or "not found" in result["error"].lower()


def test_write_file_checksum_validation(tmp_path):
    """Test that write_file verifies written content matches intended content"""
    from cortex.ui.console import console
    
    tool = create_tool_instance("write_file", tmp_path, PermissionMode.AUTO_APPROVE, console)
    
    # Write a file with valid content
    result = tool.execute(path="test.txt", content="This is test content")
    
    assert result["success"] is True
    
    # Verify the file was written correctly
    written_content = (tmp_path / "test.txt").read_text()
    assert written_content == "This is test content"


def test_write_file_creates_directories(tmp_path):
    """Test that write_file creates parent directories as needed"""
    from cortex.ui.console import console
    
    tool = create_tool_instance("write_file", tmp_path, PermissionMode.AUTO_APPROVE, console)
    
    # Write to nested path that doesn't exist
    result = tool.execute(path="nested/deep/path/test.txt", content="Test content")
    
    assert result["success"] is True
    assert (tmp_path / "nested/deep/path/test.txt").exists()
    assert (tmp_path / "nested/deep/path/test.txt").read_text() == "Test content"
