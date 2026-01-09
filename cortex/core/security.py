"""Security utilities for path validation and safety checks"""

from pathlib import Path
from typing import Optional


class SecurityError(Exception):
    """Security-related error"""
    pass


def validate_path(project_dir: Path, path: str) -> Path:
    """
    Validate that a path is within the project directory.
    
    Args:
        project_dir: The project root directory
        path: Relative path string to validate
        
    Returns:
        Resolved Path object if valid
        
    Raises:
        SecurityError: If path is outside project directory
    """
    try:
        # Resolve the full path
        full_path = (project_dir / path).resolve()
        project_root = project_dir.resolve()
        
        # Check if the resolved path is within the project directory
        if not full_path.is_relative_to(project_root):
            raise SecurityError(f"Access denied: path '{path}' is outside project directory")
        
        return full_path
    except (ValueError, RuntimeError) as e:
        raise SecurityError(f"Invalid path: {path}") from e


def is_dangerous_command(command: str) -> bool:
    """
    Check if a command is potentially dangerous.
    
    Args:
        command: Command string to check
        
    Returns:
        True if command is dangerous
    """
    dangerous_patterns = [
        'rm -rf /',
        'rm -rf ~',
        'sudo rm',
        'mkfs',
        'dd if=',
        ':(){ :|:& };:',  # Fork bomb
        'format c:',
        'del /f /s /q',
    ]
    
    command_lower = command.lower()
    return any(pattern in command_lower for pattern in dangerous_patterns)

