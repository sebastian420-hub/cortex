# Simple Plugin Example

This is a minimal example demonstrating how to create Cortex plugins.

## Contents

- `tools.py` - Two example tools: `UUIDTool` and `TextStatsTool`
- `__init__.py` - Package exports

## Tools Included

### generate_uuid

Generates UUIDs (Universally Unique Identifiers).

```python
# Usage
result = tool.execute(version=4, count=5, uppercase=False)
# Returns: {"success": True, "uuids": ["abc-123-...", ...], "count": 5}
```

### text_stats

Analyzes text and returns statistics.

```python
# Usage
result = tool.execute(text="Hello world!", include_frequency=True)
# Returns: {"success": True, "words": 2, "characters": 12, ...}
```

## Loading the Plugin

```python
from cortex.tools.registry import get_registry

# Get the global registry
registry = get_registry()

# Load the plugin
registry.load_plugin("examples.plugins.simple_tool")

# Verify tools are loaded
tools = registry.list_tools(namespace="examples")
print(tools)  # ['examples:generate_uuid', 'examples:text_stats']
```

## Creating Your Own Plugin

1. Copy this directory as a template
2. Modify `tools.py` with your tool implementations
3. Update `PLUGIN_TOOLS` export list
4. Update `__init__.py` exports

See [Plugin Development Guide](/docs/PLUGIN_DEVELOPMENT.md) for detailed instructions.

## Testing

```python
from examples.plugins.simple_tool import UUIDTool, TextStatsTool
from pathlib import Path

# Create tool instance
tool = UUIDTool(project_dir=Path("."), permission_mode="auto")

# Test
result = tool.execute(version=4, count=3)
assert result["success"] is True
assert len(result["uuids"]) == 3
```
