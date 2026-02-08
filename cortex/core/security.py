"""Security utilities for path validation and safety checks"""

import re
import shlex
from pathlib import Path
from typing import Optional, List


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


def _parse_command(command: str) -> List[str]:
    """
    Parse command into tokens, handling quotes and escapes.

    Args:
        command: Command string to parse

    Returns:
        List of command tokens
    """
    try:
        # Use shlex to properly handle quotes, escapes, etc.
        return shlex.split(command)
    except ValueError:
        # If parsing fails, fall back to simple split
        return command.split()


def _check_dangerous_paths(tokens: List[str]) -> bool:
    """
    Check if command contains dangerous paths.

    Args:
        tokens: Parsed command tokens

    Returns:
        True if dangerous paths detected
    """
    dangerous_paths = [
        "/",  # Root directory
        "/*",  # Root with wildcard
        "/./",  # Path traversal attempt
        "//",  # Double slash
        "/etc",  # System config
        "/usr",  # System binaries
        "/bin",  # System binaries
        "/sbin",  # System binaries
        "/sys",  # System files
        "/proc",  # Process files
        "/dev",  # Device files
        "C:\\",  # Windows root
        "C:/",  # Windows root (forward slash)
    ]

    command_str = " ".join(tokens).lower()

    # Check for dangerous paths
    # First, check if command is read-only (cat, less, head, tail, grep, etc.)
    read_only_commands = [
        "cat",
        "less",
        "more",
        "head",
        "tail",
        "grep",
        "find",
        "ls",
        "stat",
        "file",
    ]
    is_read_only = tokens[0].lower() in read_only_commands if tokens else False

    for path in dangerous_paths:
        if path.lower() in command_str:
            # Skip dangerous path check for read-only commands
            if is_read_only:
                continue

            # Additional check: make sure it's not part of a safe path
            # e.g., "/tmp" is okay, but "/" or "/etc" is not
            if path == "/" or path == "/*":
                # Check if it's a standalone root reference (not /tmp, /home, etc.)
                if re.search(r"\b/\s*$", command_str) or re.search(r"\b/\s+[^a-z]", command_str):
                    return True
            elif path.lower() in command_str:
                # For paths like /etc, /usr, etc., check they're not part of safe paths
                # Allow /tmp, /home, /var (common safe directories)
                safe_paths = ["/tmp", "/home", "/var", "/opt"]
                is_safe = any(safe in command_str for safe in safe_paths)
                if not is_safe:
                    return True

    # Check for path traversal attempts
    # But allow relative paths like ./tmp or ../project (single level)
    if ".." in command_str:
        # Count consecutive ".." patterns (multiple levels = dangerous)
        if re.search(r"\.\./\.\.", command_str) or re.search(r"\.\.\\\.\.", command_str):
            return True
        # Also check for .. followed by dangerous paths
        if re.search(r"\.\./\.\./etc", command_str) or re.search(r"\.\./\.\./usr", command_str):
            return True

    return False


def _check_dangerous_flags(tokens: List[str]) -> bool:
    """
    Check if command contains dangerous flags.

    Args:
        tokens: Parsed command tokens

    Returns:
        True if dangerous flags detected
    """
    if not tokens:
        return False

    command = tokens[0].lower()
    all_args = " ".join(tokens[1:]).lower()

    # Only check flags for dangerous commands (rm, del, etc.)
    dangerous_cmd_flags = ["rm", "remove", "del", "delete", "erase"]
    if command not in dangerous_cmd_flags:
        return False

    # Dangerous flag patterns (case-insensitive, handle variations)
    dangerous_flags = [
        r"-rf\b",  # rm -rf
        r"-r\s+-f\b",  # rm -r -f (separate flags)
        r"-f\s+-r\b",  # rm -f -r (reverse order)
        r"--force\b",  # --force
        r"-f\s+--force\b",  # -f --force
        r"/f\b",  # Windows /f flag
        r"/s\b",  # Windows /s flag (recursive)
        r"/q\b",  # Windows /q flag (quiet)
    ]

    # Check for dangerous flag combinations
    for pattern in dangerous_flags:
        if re.search(pattern, all_args, re.IGNORECASE):
            return True

    return False


def _check_dangerous_commands(tokens: List[str]) -> bool:
    """
    Check if command itself is dangerous.

    Args:
        tokens: Parsed command tokens

    Returns:
        True if dangerous command detected
    """
    if not tokens:
        return False

    command = tokens[0].lower()

    # Dangerous commands (with variations)
    dangerous_commands = {
        "rm": ["rm", "remove", "del", "delete", "erase"],
        "format": ["format", "mkfs", "fdisk"],
        "dd": ["dd"],
        "sudo": ["sudo", "su", "runas"],  # Privilege escalation
        "chmod": ["chmod"],  # Permission changes (especially with 777)
        "chown": ["chown"],  # Ownership changes
    }

    # Check if command matches dangerous patterns
    for dangerous_cmd, variations in dangerous_commands.items():
        if command in variations:
            # Additional checks based on command type
            if dangerous_cmd == "rm":
                # Check if rm is combined with dangerous flags/paths
                # But allow relative paths (./ or ../ at start, or no leading /)
                _all_args_str = " ".join(tokens[1:])
                has_relative_path = any(
                    arg.startswith("./")
                    or arg.startswith("../")
                    or (not arg.startswith("/") and not arg.startswith("C:") and ":" not in arg)
                    for arg in tokens[1:]
                    if not arg.startswith("-")
                )

                # If it's a relative path, only check flags (not paths)
                if has_relative_path:
                    if _check_dangerous_flags(tokens):
                        return True
                else:
                    # Absolute paths - check both flags and paths
                    if _check_dangerous_flags(tokens) or _check_dangerous_paths(tokens):
                        return True
            elif dangerous_cmd == "format":
                # Format commands are always dangerous
                return True
            elif dangerous_cmd == "dd":
                # dd with if= is dangerous (disk operations)
                args_str = " ".join(tokens[1:]).lower()
                if "if=" in args_str:
                    return True
            elif dangerous_cmd == "sudo":
                # sudo with dangerous commands is extra dangerous
                if len(tokens) > 1:
                    sub_tokens = _parse_command(" ".join(tokens[1:]))
                    if _check_dangerous_commands(sub_tokens):
                        return True

    # Check for fork bombs and other shell exploits
    command_str = " ".join(tokens)
    fork_bomb_patterns = [
        r":\s*\(\s*\)\s*\{",  # Fork bomb pattern
        r"&\s*&\s*&",  # Multiple background processes
    ]

    for pattern in fork_bomb_patterns:
        if re.search(pattern, command_str):
            return True

    return False


def is_dangerous_command(command: str) -> bool:
    """
    Check if a command is potentially dangerous using comprehensive pattern detection.

    This function parses the command, checks for dangerous patterns in multiple forms,
    and handles common bypass attempts.

    Args:
        command: Command string to check

    Returns:
        True if command is dangerous
    """
    if not command or not command.strip():
        return False

    # Parse command into tokens
    try:
        tokens = _parse_command(command)
    except Exception:
        # If parsing fails, check raw string
        tokens = [command]

    # Handle commands with dots (e.g., mkfs.ext4 -> mkfs)
    if tokens and "." in tokens[0]:
        # Extract base command name before dot
        base_command = tokens[0].split(".")[0]
        tokens[0] = base_command

    # Check for dangerous patterns
    # Note: Order matters - check commands first, then paths, then flags
    # This allows us to be more precise about what's dangerous

    # First check if it's a dangerous command with dangerous flags/paths
    if _check_dangerous_commands(tokens):
        return True

    # Then check paths (but only for destructive commands)
    destructive_commands = [
        "rm",
        "remove",
        "del",
        "delete",
        "erase",
        "format",
        "mkfs",
        "dd",
        "chmod",
        "chown",
    ]
    if tokens and tokens[0].lower() in destructive_commands:
        if _check_dangerous_paths(tokens):
            return True

    # Check flags (only for specific commands)
    if _check_dangerous_flags(tokens):
        return True

    # Additional regex patterns for common bypass attempts
    # Only check these if command is actually dangerous (rm, format, etc.)
    command_lower = command.lower()
    first_token = tokens[0].lower() if tokens else ""

    bypass_patterns = [
        (r"rm\s+.*-.*r.*f\s+/", first_token == "rm"),  # rm with -rf followed by /
        (r"rm\s+.*-.*R.*f\s+/", first_token == "rm"),  # rm with -Rf followed by /
        (r"rm\s+.*--force\s+/", first_token == "rm"),  # rm with --force followed by /
        (r"sudo\s+rm\s+.*-.*r.*f", first_token == "sudo"),  # sudo rm with -rf
        (r"rm\s+-rf\s+/", first_token == "rm"),  # rm -rf /
        (r"rm\s+-rf\s+/\*", first_token == "rm"),  # rm -rf /*
        (r"format\s+c:", first_token == "format"),  # format c: (Windows)
        (r"del\s+/[fsq]+\s+C:", first_token in ["del", "delete"]),  # del /f /s /q C: (Windows)
        (r"mkfs\s+/dev", first_token == "mkfs"),  # mkfs /dev (format)
        (r"dd\s+if=/dev", first_token == "dd"),  # dd if=/dev (disk operations)
    ]

    for pattern, should_check in bypass_patterns:
        if should_check and re.search(pattern, command_lower, re.IGNORECASE):
            return True

    return False
