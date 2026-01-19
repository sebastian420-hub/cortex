# Plugin Best Practices

This guide covers best practices for developing high-quality Cortex plugins.

## Table of Contents
1. [Design Principles](#design-principles)
2. [Error Handling](#error-handling)
3. [Permission Handling](#permission-handling)
4. [Performance](#performance)
5. [Testing](#testing)
6. [Security](#security)
7. [Documentation](#documentation)

---

## Design Principles

### Single Responsibility

Each tool should do one thing well:

```python
# Good: Focused tool
class JSONValidatorTool(Tool):
    """Validates JSON files."""
    def execute(self, path: str) -> Dict[str, Any]:
        # Only validates JSON
        pass

# Avoid: Multi-purpose tool
class FileProcessorTool(Tool):
    """Validates, formats, and transforms files."""
    # Too many responsibilities
```

### Predictable Behavior

Tools should behave consistently:

```python
class MyTool(Tool):
    def execute(self, path: str, create: bool = False) -> Dict[str, Any]:
        # Always validate path first
        try:
            full_path = validate_path(self.project_dir, path)
        except SecurityError as e:
            return self._create_error(str(e), "security")

        # Check existence
        if not full_path.exists():
            if create:
                # Document this behavior clearly
                full_path.touch()
            else:
                return self._create_error(f"File not found: {path}", "not_found")

        # Proceed with main logic...
```

### Fail Fast

Validate inputs early:

```python
def execute(self, url: str, timeout: int = 30) -> Dict[str, Any]:
    # Validate URL format first
    if not url.startswith(('http://', 'https://')):
        return self._create_error(
            "URL must start with http:// or https://",
            "validation",
            url=url,
        )

    # Validate timeout range
    if not 1 <= timeout <= 300:
        return self._create_error(
            "Timeout must be between 1 and 300 seconds",
            "validation",
            timeout=timeout,
        )

    # Now proceed with operation...
```

---

## Error Handling

### Use Standardized Responses

Always use the helper methods:

```python
# Good: Use helper methods
def execute(self, path: str) -> Dict[str, Any]:
    if not path:
        return self._create_error("Path is required", "validation")

    try:
        result = process_file(path)
        return self._create_success(result=result)
    except FileNotFoundError:
        return self._create_error(f"File not found: {path}", "not_found")

# Avoid: Manual dict construction
def execute(self, path: str) -> Dict[str, Any]:
    return {"error": "Something went wrong"}  # Missing required fields
```

### Provide Helpful Context

Include actionable information in errors:

```python
def execute(self, pattern: str) -> Dict[str, Any]:
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return self._create_error(
            f"Invalid regex pattern: {e}",
            "validation",
            pattern=pattern,
            error_position=e.pos,
            hint="Check for unescaped special characters",
            examples=[".*\\.py$", "class\\s+\\w+"],
        )
```

### Categorize Errors Correctly

Use appropriate error types:

```python
from cortex.utils.errors import ErrorType

# Validation errors (bad input)
return self._create_error("Invalid format", ErrorType.VALIDATION)

# Security errors (path traversal, etc.)
return self._create_error("Access denied", ErrorType.SECURITY)

# Not found errors (missing resource)
return self._create_error("File not found", ErrorType.NOT_FOUND)

# Execution errors (runtime failures)
return self._create_error("Operation failed", ErrorType.EXECUTION)

# Timeout errors
return self._create_error("Operation timed out", ErrorType.TIMEOUT)
```

### Handle Partial Success

When processing multiple items:

```python
def execute(self, paths: List[str]) -> Dict[str, Any]:
    results = []
    errors = []

    for path in paths:
        try:
            result = process_file(path)
            results.append({"path": path, "result": result})
        except Exception as e:
            errors.append({"path": path, "error": str(e)})

    return self._create_success(
        results=results,
        errors=errors,
        total=len(paths),
        succeeded=len(results),
        failed=len(errors),
    )
```

---

## Permission Handling

### Respect Permission Modes

Always check permission mode for write operations:

```python
from cortex.models import PermissionMode

def execute(self, path: str, content: str) -> Dict[str, Any]:
    # Plan mode: read-only
    if self.permission_mode == PermissionMode.PLAN:
        if self.console:
            self.console.print(f"[yellow]PLAN MODE:[/yellow] Would write to {path}")
        return self._create_permission_denial(
            "Plan mode - no writes allowed",
            "write_file",
            path=path,
        )

    # Normal mode: ask for confirmation
    if self.permission_mode == PermissionMode.NORMAL and self.console:
        from rich.prompt import Confirm
        if not Confirm.ask(f"Write to {path}?"):
            return self._create_permission_denial(
                "Cancelled by user",
                "write_file",
                path=path,
            )

    # Auto mode: proceed without asking
    # ... perform write
```

### Backup Before Modification

Use the transaction manager:

```python
def execute(self, path: str, content: str) -> Dict[str, Any]:
    full_path = self.project_dir / path

    # Create backup before modifying
    if full_path.exists():
        self.backup_file(full_path, "write")

    # Now safe to modify
    full_path.write_text(content)

    return self._create_success(written=True)
```

---

## Performance

### Use Appropriate Timeouts

Set timeouts based on expected operation duration:

```python
class FastTool(Tool):
    """Quick local operation."""
    timeout_category = "default"
    default_timeout = 10

class NetworkTool(Tool):
    """Network operation that may be slow."""
    timeout_category = "network"
    default_timeout = 60

class LongRunningTool(Tool):
    """Complex processing that takes time."""
    timeout_category = "long"
    default_timeout = 300
```

### Cache Expensive Operations

```python
class MyTool(Tool):
    # Class-level cache
    _cache: Dict[str, Any] = {}
    _cache_lock = threading.Lock()

    def execute(self, key: str) -> Dict[str, Any]:
        with self._cache_lock:
            if key in self._cache:
                return self._create_success(result=self._cache[key], cached=True)

        # Expensive operation
        result = expensive_computation(key)

        with self._cache_lock:
            self._cache[key] = result

        return self._create_success(result=result, cached=False)
```

### Limit Output Size

Prevent memory issues with large outputs:

```python
def execute(self, path: str) -> Dict[str, Any]:
    content = read_file(path)

    # Truncate large content
    MAX_SIZE = 100000
    if len(content) > MAX_SIZE:
        content = content[:MAX_SIZE]
        truncated = True
    else:
        truncated = False

    return self._create_success(
        content=content,
        truncated=truncated,
        original_size=len(content),
    )
```

---

## Testing

### Test Structure

```python
import pytest
from pathlib import Path
from my_plugin import MyTool

@pytest.fixture
def tool(tmp_path):
    """Create tool instance with temp directory."""
    return MyTool(
        project_dir=tmp_path,
        permission_mode="auto",
    )

class TestMyTool:
    def test_basic_operation(self, tool, tmp_path):
        """Test normal operation."""
        # Setup
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        # Execute
        result = tool.execute(path="test.txt")

        # Assert
        assert result["success"] is True
        assert "hello" in result["content"]

    def test_file_not_found(self, tool):
        """Test error handling for missing file."""
        result = tool.execute(path="nonexistent.txt")

        assert result["success"] is False
        assert result["error_type"] == "not_found"

    def test_validation_error(self, tool):
        """Test input validation."""
        result = tool.execute(path="")

        assert result["success"] is False
        assert result["error_type"] == "validation"
```

### Test Edge Cases

```python
def test_empty_file(self, tool, tmp_path):
    """Test handling of empty files."""
    (tmp_path / "empty.txt").touch()
    result = tool.execute(path="empty.txt")
    assert result["success"] is True

def test_binary_file(self, tool, tmp_path):
    """Test handling of binary files."""
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02")
    result = tool.execute(path="binary.bin")
    # Should handle gracefully

def test_unicode_content(self, tool, tmp_path):
    """Test handling of unicode content."""
    (tmp_path / "unicode.txt").write_text("Hello 世界 🌍")
    result = tool.execute(path="unicode.txt")
    assert result["success"] is True
```

### Test Permission Modes

```python
def test_plan_mode_blocks_writes(self, tmp_path):
    """Test that plan mode prevents write operations."""
    tool = MyWriteTool(
        project_dir=tmp_path,
        permission_mode="plan",
    )

    result = tool.execute(path="output.txt", content="test")

    assert result["success"] is False
    assert result.get("permission_denied") is True
```

---

## Security

### Validate All Paths

Always use the security module:

```python
from cortex.core.security import validate_path, SecurityError

def execute(self, path: str) -> Dict[str, Any]:
    try:
        full_path = validate_path(self.project_dir, path)
    except SecurityError as e:
        return self._create_error(str(e), "security", path=path)

    # Path is now safe to use
```

### Sanitize Inputs

Be careful with user inputs used in commands:

```python
import shlex

def execute(self, filename: str) -> Dict[str, Any]:
    # Bad: Direct string interpolation
    # os.system(f"process {filename}")  # DANGEROUS!

    # Good: Use proper escaping
    safe_filename = shlex.quote(filename)

    # Better: Use subprocess with list arguments
    subprocess.run(["process", filename], check=True)
```

### Limit Resource Usage

Prevent denial of service:

```python
def execute(self, data: str) -> Dict[str, Any]:
    # Limit input size
    MAX_INPUT = 1_000_000  # 1MB
    if len(data) > MAX_INPUT:
        return self._create_error(
            f"Input too large (max {MAX_INPUT} bytes)",
            "validation",
        )

    # Limit processing time
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError("Processing timeout")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)  # 30 second timeout

    try:
        result = process(data)
    finally:
        signal.alarm(0)

    return self._create_success(result=result)
```

---

## Documentation

### Docstrings

Use Google-style docstrings:

```python
class MyTool(Tool):
    """
    Short description of what the tool does.

    Longer description explaining the tool's purpose,
    behavior, and any important details.

    Attributes:
        timeout_category: Category for timeout lookup
        default_timeout: Default timeout in seconds
    """

    def execute(
        self,
        path: str,
        format: str = "json",
        validate: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a file and return results.

        Args:
            path: Path to the file to process
            format: Output format ("json", "yaml", "text")
            validate: Whether to validate before processing

        Returns:
            Dictionary containing:
            - success: Whether operation succeeded
            - result: Processed data (if successful)
            - error: Error message (if failed)

        Raises:
            SecurityError: If path is outside project directory

        Example:
            >>> tool = MyTool(project_dir=Path("."))
            >>> result = tool.execute(path="data.json", format="yaml")
            >>> print(result["success"])
            True
        """
```

### Schema Documentation

Write clear schema descriptions:

```python
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": (
            "Process files and extract structured data. "
            "Supports JSON, YAML, and XML formats. "
            "Returns the extracted data in the specified output format."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path to the file to process, relative to project root. "
                        "Example: 'src/data/config.json'"
                    ),
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "yaml", "text"],
                    "description": (
                        "Output format for results. "
                        "Default: 'json'"
                    ),
                },
            },
            "required": ["path"],
        },
    },
}
```

---

## Quick Reference

### Do's

- Use `_create_success()`, `_create_error()`, `_create_permission_denial()`
- Validate paths with `validate_path()`
- Check `permission_mode` before writes
- Use `backup_file()` before modifications
- Set appropriate `timeout_category` and `default_timeout`
- Write comprehensive tests
- Document with Google-style docstrings

### Don'ts

- Don't construct response dicts manually
- Don't use `os.system()` or `eval()`
- Don't ignore permission modes
- Don't load unbounded data into memory
- Don't expose sensitive information in errors
- Don't skip input validation

---

*Last updated: 2026-01-17*
