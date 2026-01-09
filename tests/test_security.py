"""Tests for security features"""

import pytest
from pathlib import Path
from cortex.core.security import validate_path, SecurityError, is_dangerous_command


def test_validate_path_within_project(tmp_path):
    """Test that valid paths within project are allowed"""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    
    test_file = project_dir / "test.txt"
    test_file.write_text("test")
    
    result = validate_path(project_dir, "test.txt")
    assert result == test_file.resolve()


def test_validate_path_outside_project(tmp_path):
    """Test that paths outside project are blocked"""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("test")
    
    with pytest.raises(SecurityError):
        validate_path(project_dir, "../outside.txt")


def test_validate_path_directory_traversal(tmp_path):
    """Test that directory traversal attacks are blocked"""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    
    with pytest.raises(SecurityError):
        validate_path(project_dir, "../../etc/passwd")


def test_is_dangerous_command():
    """Test dangerous command detection"""
    assert is_dangerous_command("rm -rf /") is True
    assert is_dangerous_command("rm -rf ~") is True
    assert is_dangerous_command("sudo rm -rf /") is True
    assert is_dangerous_command("ls -la") is False
    assert is_dangerous_command("git status") is False
    assert is_dangerous_command("format c:") is True

