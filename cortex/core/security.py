"""Security utilities for path validation and safety checks"""

import posixpath
import re
import shlex
from pathlib import Path
from typing import List, Optional, Tuple


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
                safe_paths = ["/tmp", "/home", "/var", "/opt"]  # nosec B108
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


# ---------------------------------------------------------------------------------------
# Compound commands: split into the individual commands that will run, then judge each one.
# ---------------------------------------------------------------------------------------

_MAX_NESTING = 3  # how deep to follow `sh -c '...'`

_SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
_INTERPRETERS = _SHELLS | {"python", "python2", "python3", "perl", "ruby", "node", "php"}
_FETCHERS = {"curl", "wget", "fetch", "aria2c"}
# Commands that run another command: judge what they run
_WRAPPERS = {
    "sudo", "doas", "env", "nohup", "time", "nice", "ionice", "command", "exec", "xargs",
    "stdbuf", "timeout", "setsid",
}  # fmt: skip
_TOP_LEVEL_DIRS = {
    "/bin", "/boot", "/dev", "/etc", "/lib", "/lib32", "/lib64", "/proc", "/root", "/sbin",
    "/sys", "/usr",
}  # fmt: skip
_CONTAINER_DIRS = {"/var", "/opt", "/home", "/srv", "/mnt", "/media"}
_HOME_ALIASES = {"~", "$HOME", "${HOME}"}


def _split_commands(command: str) -> List[Tuple[str, str]]:
    """Split a command line on unquoted ``; && || | &`` and newlines.

    Returns ``(segment, operator_before_it)`` pairs; the operator is "" for the first one.
    """
    segments: List[Tuple[str, str]] = []
    current: List[str] = []
    operator = ""
    quote = ""
    i = 0
    n = len(command)

    def flush(next_operator: str) -> None:
        nonlocal operator
        text = "".join(current).strip()
        if text:
            segments.append((text, operator))
        current.clear()
        operator = next_operator

    while i < n:
        ch = command[i]
        if quote:
            current.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < n:
                current.append(command[i + 1])
                i += 1
            elif ch == quote:
                quote = ""
        elif ch == "\\" and i + 1 < n:
            current.append(ch)
            current.append(command[i + 1])
            i += 1
        elif ch in ("'", '"'):
            quote = ch
            current.append(ch)
        elif ch == "<" and command[i : i + 2] == "<(":
            # process substitution <( ... ): keep it inside the segment
            depth = 0
            while i < n:
                current.append(command[i])
                if command[i] == "(":
                    depth += 1
                elif command[i] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
        elif ch == "$" and command[i : i + 2] == "$(":
            depth = 0
            while i < n:
                current.append(command[i])
                if command[i] == "(":
                    depth += 1
                elif command[i] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
        elif command[i : i + 2] in ("&&", "||"):
            flush(command[i : i + 2])
            i += 1
        elif ch in (";", "|", "&", "\n"):
            # a redirect like 2>&1 or &> is not a separator
            if ch == "&" and (command[i - 1 : i] == ">" or command[i + 1 : i + 2] == ">"):
                current.append(ch)
            else:
                flush("\n" if ch == "\n" else ch)
        else:
            current.append(ch)
        i += 1
    flush("")
    return segments


def _tokens(segment: str) -> List[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def _unwrap(tokens: List[str]) -> List[str]:
    """Drop VAR=value prefixes and wrappers like sudo/env/xargs to reach the real command."""
    tokens = list(tokens)
    while tokens:
        head = posixpath.basename(tokens[0]).lower()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
            tokens.pop(0)
        elif head in _WRAPPERS:
            tokens.pop(0)
            # skip the wrapper's own options and their numeric/assignment arguments
            while tokens and (
                tokens[0].startswith("-")
                or re.fullmatch(r"[0-9.]+[smhd]?", tokens[0])
                or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0])
            ):
                tokens.pop(0)
        else:
            break
    return tokens


def _short_flags(args: List[str]) -> Tuple[set, set]:
    """Single-letter flags (from clusters like -rfv) and long flags, up to a ``--`` marker."""
    short: set = set()
    long_: set = set()
    for arg in args:
        if arg == "--":
            break
        if arg.startswith("--"):
            long_.add(arg.split("=", 1)[0])
        elif arg.startswith("-") and len(arg) > 1:
            short.update(arg[1:])
    return short, long_


def _operands(args: List[str]) -> List[str]:
    """Arguments that are not flags (everything after ``--`` counts as an operand)."""
    result: List[str] = []
    after_marker = False
    for arg in args:
        if after_marker or not arg.startswith("-"):
            result.append(arg)
        elif arg == "--":
            after_marker = True
    return result


def _is_protected_path(arg: str) -> bool:
    """A system directory, or the root of the home directory (not a folder inside it)."""
    path = arg.strip()
    for suffix in ("/*", "/."):
        while path.endswith(suffix) and len(path) > len(suffix):
            path = path[: -len(suffix)]
    path = path.rstrip("/") if path not in ("/", "") else path
    if path in _HOME_ALIASES or path in ("/", "/*"):
        return True
    if path.startswith("/"):
        path = posixpath.normpath(path)
        if path in _CONTAINER_DIRS:
            return True
        return any(path == d or path.startswith(d + "/") for d in _TOP_LEVEL_DIRS)
    return False


def _git_subcommand(args: List[str]) -> Tuple[str, List[str]]:
    """The git subcommand and its arguments, skipping global options like ``-C dir``."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
            i += 2
        elif arg.startswith("-"):
            i += 1
        else:
            return arg, args[i + 1 :]
    return "", []


def _git_is_destructive(args: List[str]) -> bool:
    sub, rest = _git_subcommand(args)
    short, long_ = _short_flags(rest)
    if sub == "push":
        if "f" in short or long_ & {"--force", "--mirror"}:
            return True
        if any(flag.startswith("--force") for flag in long_):  # --force-with-lease[=...]
            return True
        return any(op.startswith("+") for op in _operands(rest))
    if sub == "reset":
        return "--hard" in long_
    if sub == "clean":
        forced = "f" in short or "--force" in long_
        dry_run = "n" in short or "--dry-run" in long_
        return forced and not dry_run
    return False


def _segment_is_dangerous(
    tokens: List[str], previous: Optional[List[str]], operator: str, depth: int
) -> bool:
    tokens = _unwrap(tokens)
    if not tokens:
        return False
    name = posixpath.basename(tokens[0]).lower()
    args = tokens[1:]
    short, long_ = _short_flags(args)
    targets = _operands(args)

    if name in _SHELLS | {"eval"}:
        # sh -c '<code>' / eval '<code>': judge the code
        if depth < _MAX_NESTING:
            code = []
            if name == "eval":
                code = [" ".join(args)]
            elif "-c" in args and args.index("-c") + 1 < len(args):
                code = [args[args.index("-c") + 1]]
            if any(_is_dangerous_compound(c, depth + 1) for c in code):
                return True
        # sh -c "$(curl ...)"  /  bash <(curl ...)  /  eval "$(wget ...)"
        if re.search(r"(<\(|\$\(|`)\s*(curl|wget)\b", " ".join(args)):
            return True

    if name in ("source", "."):
        if re.search(r"(<\(|\$\(|`)\s*(curl|wget)\b", " ".join(args)):
            return True

    # curl ... | sh   (stdin is run as code: no script, no -c, no -m)
    if operator == "|" and previous:
        previous_name = (
            posixpath.basename(_unwrap(previous)[0]).lower() if _unwrap(previous) else ""
        )
        if previous_name in _FETCHERS and name in _INTERPRETERS:
            reads_stdin = not (targets and targets != ["-"]) and not (short & {"c", "m"})
            if reads_stdin:
                return True

    if name == "rm":
        recursive = bool(short & {"r", "R"}) or "--recursive" in long_
        forced = "f" in short or "--force" in long_
        if recursive and (forced or any(_is_protected_path(t) for t in targets)):
            return True

    if name == "find":
        if "-delete" in args:
            return True
        for flag in ("-exec", "-execdir", "-ok", "-okdir"):
            if flag in args:
                after = args[args.index(flag) + 1 :]
                if after and posixpath.basename(after[0]).lower() in {"rm", "shred", "unlink"}:
                    return True

    if name == "git" and _git_is_destructive(args):
        return True

    if name in ("chmod", "chown", "chgrp"):
        if ("R" in short or "--recursive" in long_) and any(_is_protected_path(t) for t in targets):
            return True

    if name == "dd" and any(a.lower().startswith("of=/dev/") for a in args):
        return True

    return False


def _is_dangerous_compound(command: str, depth: int = 0) -> bool:
    """True when any command inside ``command`` (a pipeline, an && chain, ...) is dangerous."""
    previous: Optional[List[str]] = None
    for segment, operator in _split_commands(command):
        tokens = _tokens(segment)
        if _segment_is_dangerous(tokens, previous, operator, depth):
            return True
        previous = tokens
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

    # Judge each command of a compound line (pipes, &&, ;, sudo/env wrappers, sh -c) on its own
    if _is_dangerous_compound(command):
        return True

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
