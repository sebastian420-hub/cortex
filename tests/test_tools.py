"""Tests for tool implementations"""

import pytest
from pathlib import Path
from localagent.tools import create_tool_instance
from localagent.models import PermissionMode


def test_read_file_tool(tmp_path, monkeypatch):
    """Test read_file tool"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")
    
    from localagent.ui.console import console
    tool = create_tool_instance("read_file", tmp_path, PermissionMode.NORMAL, console)
    result = tool.execute(path="test.txt")
    
    assert result["success"] is True
    assert result["content"] == "Hello, World!"
    assert result["lines"] == 1


def test_write_file_tool(tmp_path, monkeypatch):
    """Test write_file tool"""
    from localagent.ui.console import console
    
    tool = create_tool_instance("write_file", tmp_path, PermissionMode.AUTO_APPROVE, console)
    result = tool.execute(path="test.txt", content="Test content")
    
    assert result["success"] is True
    assert (tmp_path / "test.txt").read_text() == "Test content"


def test_write_file_plan_mode(tmp_path):
    """Test that write_file is blocked in plan mode"""
    from localagent.ui.console import console
    
    tool = create_tool_instance("write_file", tmp_path, PermissionMode.PLAN, console)
    result = tool.execute(path="test.txt", content="Test content")
    
    assert result["success"] is False
    assert "Plan mode" in result["message"]


def test_list_files_tool(tmp_path):
    """Test list_files tool"""
    # Create some test files
    (tmp_path / "file1.txt").write_text("test")
    (tmp_path / "file2.py").write_text("test")
    (tmp_path / ".hidden").write_text("test")
    
    from localagent.ui.console import console
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
    
    from localagent.ui.console import console
    tool = create_tool_instance("git_status", tmp_path, PermissionMode.NORMAL, console)
    result = tool.execute()
    
    assert result["success"] is True
    assert "test.txt" in result["output"]

