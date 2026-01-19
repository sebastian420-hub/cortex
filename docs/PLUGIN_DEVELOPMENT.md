# Cortex Plugin Development Guide

This guide explains how to create custom tools (plugins) for Cortex.

## Table of Contents
1. [Quick Start](#quick-start)
2. [Tool Interface](#tool-interface)
3. [Schema Format](#schema-format)
4. [Creating a Plugin Module](#creating-a-plugin-module)
5. [Loading Plugins](#loading-plugins)
6. [Best Practices](#best-practices)
7. [Examples](#examples)
8. [Testing Plugins](#testing-plugins)

---

## Quick Start

Here's a minimal plugin in 30 lines:

```python
# my_plugin.py
from pathlib import Path
from typing import Dict, Any
from cortex.tools.base import Tool

class HelloTool(Tool):
    """A simple greeting tool."""

    def execute(self, name: str = "World") -> Dict[str, Any]:
        greeting = f"Hello, {name}!"
        return {"success": True, "message": greeting}

# Export for registry
PLUGIN_TOOLS = [
    {
        "name": "hello",
        "class": HelloTool,
        "schema": {
            "type": "function",
            "function": {
                "name": "hello",
                "description": "Greet someone by name",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name to greet"}
                    },
                    "required": []
                }
            }
        }
    }
]
```

---

## Tool Interface

All tools inherit from `cortex.tools.base.Tool`:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

class Tool(ABC):
    """Base class for all tools."""

    # Timeout settings
    default_timeout: int = 30        # Default timeout in seconds
    timeout_category: str = "default" # Category for timeout lookup

    def __init__(
        self,
        project_dir: Path,           # Current project directory
        permission_mode: str,         # "normal", "auto", or "plan"
        console=None,                 # Rich console for output
        timeout_config=None,          # Timeout configuration
        transaction_manager=None,     # For file backup/recovery
        **kwargs,
    ):
        ...

    @abstractmethod
    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute the tool. Must be implemented by subclasses."""
        pass
```

### Available Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `self.project_dir` | `Path` | Root directory of current project |
| `self.permission_mode` | `str` | Current permission mode |
| `self.console` | `Console` | Rich console for output (may be None) |

### Helper Methods

| Method | Description |
|--------|-------------|
| `self._create_success(**data)` | Create success response |
| `self._create_error(msg, type, **ctx)` | Create error response |
| `self._create_permission_denial(reason, action)` | Create permission denial |
| `self._validate_arguments(required, **kwargs)` | Validate required args |
| `self.get_timeout(operation=None)` | Get timeout for operation |
| `self.backup_file(path, operation)` | Backup file before modification |
| `self.check_permission(action)` | Check if action is allowed |

---

## Schema Format

Tool schemas follow the OpenAI function calling format:

```python
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "tool_name",           # Unique tool name (snake_case)
        "description": "What this tool does. Be specific and helpful.",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",  # string, integer, number, boolean, array, object
                    "description": "Clear description of parameter"
                },
                "param2": {
                    "type": "integer",
                    "description": "Another parameter",
                    "default": 10      # Optional default value
                },
                "options": {
                    "type": "string",
                    "enum": ["option1", "option2", "option3"],  # Allowed values
                    "description": "Choose from predefined options"
                }
            },
            "required": ["param1"]     # List of required parameters
        }
    }
}
```

### Parameter Types

| Type | Python | Description |
|------|--------|-------------|
| `string` | `str` | Text value |
| `integer` | `int` | Whole number |
| `number` | `float` | Decimal number |
| `boolean` | `bool` | True/False |
| `array` | `list` | List of items |
| `object` | `dict` | Dictionary/object |

---

## Creating a Plugin Module

### Directory Structure

```
my_cortex_plugins/
├── __init__.py
├── my_tools.py
└── tests/
    └── test_my_tools.py
```

### Plugin Module Format

```python
# my_cortex_plugins/my_tools.py
"""Custom tools for Cortex."""

from pathlib import Path
from typing import Dict, Any, List, Optional
from cortex.tools.base import Tool
from cortex.utils.errors import create_error_response, create_success_response, ErrorType


class WeatherTool(Tool):
    """Get weather information for a location."""

    timeout_category = "network"
    default_timeout = 30

    def execute(
        self,
        location: str,
        units: str = "celsius"
    ) -> Dict[str, Any]:
        """
        Get weather for a location.

        Args:
            location: City name or coordinates
            units: Temperature units (celsius/fahrenheit)

        Returns:
            Weather data or error response
        """
        # Validate arguments
        error = self._validate_arguments(["location"], location=location)
        if error:
            return error

        # Validate units
        if units not in ["celsius", "fahrenheit"]:
            return self._create_error(
                f"Invalid units: {units}. Use 'celsius' or 'fahrenheit'.",
                "validation",
                provided_units=units
            )

        # Display progress (if console available)
        if self.console:
            self.console.print(f"[cyan]Fetching weather for:[/cyan] {location}")

        try:
            # Your implementation here
            weather_data = self._fetch_weather(location, units)
            return self._create_success(
                location=location,
                temperature=weather_data["temp"],
                conditions=weather_data["conditions"],
                units=units
            )
        except Exception as e:
            return self._create_error(
                f"Failed to fetch weather: {e}",
                "execution",
                location=location
            )

    def _fetch_weather(self, location: str, units: str) -> dict:
        """Internal method to fetch weather data."""
        # Implementation...
        pass


class CalculatorTool(Tool):
    """Perform mathematical calculations."""

    def execute(
        self,
        expression: str,
        precision: int = 2
    ) -> Dict[str, Any]:
        """Evaluate a mathematical expression."""
        try:
            # Safe evaluation (limited operations)
            allowed_chars = set("0123456789+-*/().% ")
            if not all(c in allowed_chars for c in expression):
                return self._create_error(
                    "Expression contains invalid characters",
                    "validation",
                    expression=expression
                )

            result = eval(expression)  # Note: Use safer evaluation in production
            return self._create_success(
                expression=expression,
                result=round(result, precision)
            )
        except Exception as e:
            return self._create_error(f"Calculation failed: {e}", "execution")


# ============================================
# PLUGIN EXPORT - Required for registry
# ============================================

PLUGIN_TOOLS = [
    {
        "name": "weather",
        "class": WeatherTool,
        "schema": {
            "type": "function",
            "function": {
                "name": "weather",
                "description": "Get current weather information for a location. Returns temperature and conditions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name (e.g., 'London') or coordinates (e.g., '51.5,-0.1')"
                        },
                        "units": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "Temperature units (default: celsius)"
                        }
                    },
                    "required": ["location"]
                }
            }
        },
        "namespace": "custom",  # Optional: organize tools by namespace
        "enabled": True         # Optional: default is True
    },
    {
        "name": "calculator",
        "class": CalculatorTool,
        "schema": {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "Evaluate mathematical expressions. Supports +, -, *, /, and parentheses.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate (e.g., '2 + 2 * 3')"
                        },
                        "precision": {
                            "type": "integer",
                            "description": "Decimal places for result (default: 2)"
                        }
                    },
                    "required": ["expression"]
                }
            }
        },
        "namespace": "custom"
    }
]
```

---

## Loading Plugins

### Method 1: Programmatic Loading

```python
from cortex.tools.registry import get_registry

# Get the global registry
registry = get_registry()

# Load your plugin module
registry.load_plugin("my_cortex_plugins.my_tools")

# Verify tools are loaded
print(registry.list_tools())  # Should include your tools
```

### Method 2: Direct Registration

```python
from cortex.tools.registry import get_registry
from my_cortex_plugins.my_tools import WeatherTool

registry = get_registry()

# Register a single tool
registry.register(
    name="weather",
    tool_class=WeatherTool,
    schema={
        "type": "function",
        "function": {
            "name": "weather",
            "description": "Get weather information",
            "parameters": {...}
        }
    },
    namespace="custom",
    enabled=True
)
```

### Method 3: Configuration File (Future)

```yaml
# config/plugins.yaml
plugins:
  - my_cortex_plugins.my_tools
  - another_plugin.tools

disabled:
  - web_search  # Disable built-in tool
```

---

## Best Practices

### 1. Error Handling

Always return standardized responses:

```python
def execute(self, path: str) -> Dict[str, Any]:
    # Validate inputs
    if not path:
        return self._create_error(
            "Path is required",
            "validation",
            hint="Provide a valid file path"
        )

    try:
        # Your logic
        result = do_something(path)
        return self._create_success(result=result)
    except FileNotFoundError:
        return self._create_error(
            f"File not found: {path}",
            "not_found",
            path=path,
            retryable=True  # Indicate if operation can be retried
        )
    except PermissionError:
        return self._create_error(
            f"Permission denied: {path}",
            "security",
            path=path
        )
    except Exception as e:
        return self._create_error(
            f"Unexpected error: {e}",
            "execution",
            path=path
        )
```

### 2. Permission Modes

Respect permission modes:

```python
def execute(self, path: str, content: str) -> Dict[str, Any]:
    from cortex.models import PermissionMode

    # Check for plan mode (read-only)
    if self.permission_mode == PermissionMode.PLAN:
        if self.console:
            self.console.print(f"[yellow]PLAN MODE:[/yellow] Would write to {path}")
        return self._create_permission_denial(
            "Plan mode - no writes allowed",
            "write_file"
        )

    # For normal mode, ask for confirmation
    if self.permission_mode == PermissionMode.NORMAL and self.console:
        from rich.prompt import Confirm
        if not Confirm.ask(f"Write to {path}?"):
            return self._create_permission_denial("Cancelled by user", "write_file")

    # AUTO_APPROVE mode proceeds without asking
    # ... perform write
```

### 3. Console Output

Use Rich console for formatted output:

```python
def execute(self, query: str) -> Dict[str, Any]:
    if self.console:
        self.console.print(f"[cyan]Searching:[/cyan] {query}")

        # Show progress
        with self.console.status("[bold green]Processing..."):
            results = self._do_search(query)

        # Display results
        from rich.panel import Panel
        self.console.print(Panel(
            "\n".join(results[:5]),
            title=f"Found {len(results)} results",
            border_style="cyan"
        ))

    return self._create_success(results=results, count=len(results))
```

### 4. File Operations

Use backup for file modifications:

```python
def execute(self, path: str, content: str) -> Dict[str, Any]:
    full_path = self.project_dir / path

    # Backup before modification
    self.backup_file(full_path, "write")

    # Write file
    full_path.write_text(content)

    return self._create_success(bytes_written=len(content))
```

### 5. Timeouts

Set appropriate timeouts:

```python
class SlowAPITool(Tool):
    """Tool that calls slow external API."""

    timeout_category = "network"
    default_timeout = 60  # 60 seconds for slow operations

    def execute(self, endpoint: str) -> Dict[str, Any]:
        timeout = self.get_timeout()  # Uses timeout_category or default
        # ... use timeout in API call
```

---

## Examples

### Example 1: Simple Tool (No Dependencies)

```python
class UUIDTool(Tool):
    """Generate UUIDs."""

    def execute(self, version: int = 4, count: int = 1) -> Dict[str, Any]:
        import uuid

        if version not in [1, 4]:
            return self._create_error("Version must be 1 or 4", "validation")

        uuids = []
        for _ in range(min(count, 100)):  # Limit to 100
            if version == 1:
                uuids.append(str(uuid.uuid1()))
            else:
                uuids.append(str(uuid.uuid4()))

        return self._create_success(uuids=uuids, count=len(uuids))
```

### Example 2: File Processing Tool

```python
class JSONValidatorTool(Tool):
    """Validate JSON files."""

    def execute(self, path: str) -> Dict[str, Any]:
        import json
        from cortex.core.security import validate_path, SecurityError

        try:
            full_path = validate_path(self.project_dir, path)
        except SecurityError as e:
            return self._create_error(str(e), "security")

        if not full_path.exists():
            return self._create_error(f"File not found: {path}", "not_found")

        try:
            content = full_path.read_text()
            data = json.loads(content)

            return self._create_success(
                valid=True,
                keys=list(data.keys()) if isinstance(data, dict) else None,
                type=type(data).__name__
            )
        except json.JSONDecodeError as e:
            return self._create_success(
                valid=False,
                error=str(e),
                line=e.lineno,
                column=e.colno
            )
```

### Example 3: Async External API Tool

```python
import asyncio
import aiohttp

class AsyncAPITool(Tool):
    """Fetch data from external API asynchronously."""

    timeout_category = "network"
    default_timeout = 30

    def execute(self, url: str, method: str = "GET") -> Dict[str, Any]:
        # Run async code in sync context
        return asyncio.run(self._async_fetch(url, method))

    async def _async_fetch(self, url: str, method: str) -> Dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=self.get_timeout())

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method, url) as response:
                    data = await response.text()
                    return self._create_success(
                        status=response.status,
                        content=data[:1000],  # Truncate large responses
                        headers=dict(response.headers)
                    )
        except asyncio.TimeoutError:
            return self._create_error(
                f"Request timed out after {self.get_timeout()}s",
                "timeout"
            )
        except Exception as e:
            return self._create_error(f"Request failed: {e}", "execution")
```

---

## Testing Plugins

### Basic Test Structure

```python
# tests/test_my_tools.py
import pytest
from pathlib import Path
from my_cortex_plugins.my_tools import WeatherTool, CalculatorTool


@pytest.fixture
def project_dir(tmp_path):
    """Create a temporary project directory."""
    return tmp_path


@pytest.fixture
def calculator(project_dir):
    """Create CalculatorTool instance."""
    return CalculatorTool(
        project_dir=project_dir,
        permission_mode="auto"
    )


class TestCalculatorTool:
    def test_basic_addition(self, calculator):
        result = calculator.execute(expression="2 + 2")
        assert result["success"] is True
        assert result["result"] == 4

    def test_complex_expression(self, calculator):
        result = calculator.execute(expression="(10 + 5) * 2")
        assert result["success"] is True
        assert result["result"] == 30

    def test_precision(self, calculator):
        result = calculator.execute(expression="10 / 3", precision=4)
        assert result["success"] is True
        assert result["result"] == 3.3333

    def test_invalid_characters(self, calculator):
        result = calculator.execute(expression="import os")
        assert result["success"] is False
        assert result["error_type"] == "validation"


class TestWeatherTool:
    def test_missing_location(self, project_dir):
        tool = WeatherTool(project_dir=project_dir, permission_mode="auto")
        result = tool.execute()  # No location provided
        assert result["success"] is False

    def test_invalid_units(self, project_dir):
        tool = WeatherTool(project_dir=project_dir, permission_mode="auto")
        result = tool.execute(location="London", units="kelvin")
        assert result["success"] is False
        assert "units" in result.get("error", "").lower()
```

### Testing with Mocks

```python
from unittest.mock import patch, MagicMock


class TestWeatherToolWithMocks:
    @patch.object(WeatherTool, '_fetch_weather')
    def test_successful_fetch(self, mock_fetch, project_dir):
        mock_fetch.return_value = {
            "temp": 20,
            "conditions": "Sunny"
        }

        tool = WeatherTool(project_dir=project_dir, permission_mode="auto")
        result = tool.execute(location="London")

        assert result["success"] is True
        assert result["temperature"] == 20
        mock_fetch.assert_called_once_with("London", "celsius")
```

---

## Response Format Reference

### Success Response

```python
{
    "success": True,
    "key1": "value1",
    "key2": "value2",
    # ... your data
}
```

### Error Response

```python
{
    "success": False,
    "error": "Human-readable error message",
    "error_type": "validation",  # or "security", "execution", "not_found", "timeout"
    "retryable": True,           # Optional: can operation be retried?
    "hint": "Helpful suggestion", # Optional
    "context": {...}             # Optional: additional context
}
```

### Permission Denial Response

```python
{
    "success": False,
    "error": "Plan mode - no writes allowed",
    "error_type": "permission_denied",
    "permission_denied": True,
    "action": "write_file",
    "context": {...}
}
```

---

## Troubleshooting

### Plugin Not Loading

1. Check module path is correct
2. Verify `PLUGIN_TOOLS` is exported
3. Check for import errors in your module

```python
# Debug loading
try:
    registry.load_plugin("my_plugin")
    print("Loaded successfully")
except Exception as e:
    print(f"Load failed: {e}")
```

### Tool Not Appearing

1. Verify schema format is correct
2. Check tool is enabled (`enabled: True`)
3. Verify no naming conflicts

```python
# Check registered tools
print(registry.list_tools())
print(registry.get_schema("my_tool"))
```

### Runtime Errors

1. Check all required arguments are provided
2. Verify return format is correct
3. Check permission mode handling

---

## API Reference

### ToolRegistry Methods

| Method | Description |
|--------|-------------|
| `register(name, tool_class, schema, namespace, enabled)` | Register a tool |
| `unregister(name)` | Remove a tool |
| `get_tool_class(name)` | Get tool class |
| `get_schema(name)` | Get tool schema |
| `get_all_schemas()` | Get all enabled schemas |
| `enable(name)` / `disable(name)` | Toggle tool |
| `list_tools(namespace, include_disabled)` | List tools |
| `create_instance(name, project_dir, ...)` | Create tool instance |
| `load_plugin(plugin_path)` | Load plugin module |

### ErrorType Constants

```python
from cortex.utils.errors import ErrorType

ErrorType.VALIDATION      # Invalid input
ErrorType.SECURITY        # Security violation
ErrorType.EXECUTION       # Runtime error
ErrorType.NOT_FOUND       # Resource not found
ErrorType.TIMEOUT         # Operation timed out
ErrorType.PERMISSION      # Permission denied
```

---

*Last updated: 2026-01-17*
