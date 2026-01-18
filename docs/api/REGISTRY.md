# Tool Registry API Reference

The Tool Registry is Cortex's dynamic tool management system that supports registration, discovery, and configuration of tools at runtime.

## Overview

The `ToolRegistry` class provides:
- **Dynamic tool registration/unregistration** - Add/remove tools at runtime
- **Namespace support** - Organize tools into logical groups
- **Enable/disable functionality** - Control tool availability via configuration
- **Plugin system** - Load tools from external modules
- **Configuration integration** - Apply settings from config files

## Core Concepts

### Tool Registration
Tools are registered with a name, class, schema, and optional namespace. The registry maintains metadata about each tool including its enabled state.

### Namespaces
Tools can be organized into namespaces for better organization:
- `builtin` - Core Cortex tools (default)
- `plugin` - External plugin tools
- Custom namespaces for specialized tool sets

### Tool Schema
Each tool must provide a JSON schema in OpenAI function calling format that describes its parameters and usage.

## API Reference

### Class: ToolRegistry

#### Constructor
```python
registry = ToolRegistry()
```

Creates a new tool registry instance.

#### Methods

##### `register(name, tool_class, schema, namespace="builtin", enabled=True)`
Register a tool with the registry.

**Parameters:**
- `name` (str): Tool name (e.g., "read_file")
- `tool_class` (Type[Tool]): The Tool subclass
- `schema` (Dict[str, Any]): Tool schema in function calling format
- `namespace` (str): Tool namespace (default: "builtin")
- `enabled` (bool): Whether tool is enabled (default: True)

**Example:**
```python
registry.register(
    name="my_tool",
    tool_class=MyTool,
    schema={
        "type": "function",
        "function": {
            "name": "my_tool",
            "description": "My custom tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string"}
                },
                "required": ["param1"]
            }
        }
    },
    namespace="custom"
)
```

##### `unregister(name)`
Remove a tool from the registry.

**Parameters:**
- `name` (str): Tool name to unregister

**Returns:**
- `bool`: True if tool was unregistered, False if not found

##### `get_tool_class(name)`
Get the tool class for a registered tool.

**Parameters:**
- `name` (str): Tool name

**Returns:**
- `Type[Tool]`: Tool class if found and enabled, None otherwise

##### `get_schema(name)`
Get the schema for a registered tool.

**Parameters:**
- `name` (str): Tool name

**Returns:**
- `Dict[str, Any]`: Tool schema if found and enabled, None otherwise

##### `get_all_schemas()`
Get schemas for all enabled tools.

**Returns:**
- `List[Dict[str, Any]]`: List of tool schemas for enabled tools

##### `enable(name)`
Enable a tool.

**Parameters:**
- `name` (str): Tool name to enable

**Returns:**
- `bool`: True if tool was enabled, False if not found

##### `disable(name)`
Disable a tool.

**Parameters:**
- `name` (str): Tool name to disable

**Returns:**
- `bool`: True if tool was disabled, False if not found

##### `is_enabled(name)`
Check if a tool is enabled.

**Parameters:**
- `name` (str): Tool name

**Returns:**
- `bool`: True if tool is enabled

##### `list_tools(namespace=None, include_disabled=False)`
List registered tools.

**Parameters:**
- `namespace` (str, optional): Filter by namespace (None for all)
- `include_disabled` (bool): Include disabled tools (default: False)

**Returns:**
- `List[str]`: List of tool names

##### `list_namespaces()`
List all registered namespaces.

**Returns:**
- `List[str]`: List of namespace names

##### `create_instance(name, project_dir, permission_mode, console, **extra_kwargs)`
Create a tool instance.

**Parameters:**
- `name` (str): Tool name
- `project_dir` (Path): Project directory path
- `permission_mode` (str): Permission mode string
- `console`: Console instance for output
- `**extra_kwargs`: Additional kwargs for tool constructor

**Returns:**
- `Tool`: Tool instance

**Raises:**
- `ValueError`: If tool not found or disabled

##### `register_builtins()`
Register all built-in Cortex tools. Called automatically during initialization.

##### `load_plugin(plugin_path)`
Load tools from a plugin module.

Plugin modules should export a `PLUGIN_TOOLS` list:

```python
PLUGIN_TOOLS = [
    {
        "name": "my_tool",
        "class": MyToolClass,
        "schema": {...},
        "namespace": "my_plugin"  # optional
    }
]
```

**Parameters:**
- `plugin_path` (str): Python module path (e.g., "my_plugins.custom_tools")

**Returns:**
- `bool`: True if plugin loaded successfully, False otherwise

##### `apply_config(config)`
Apply configuration to the registry.

Config format:
```yaml
tools:
  disabled: ["tool1", "tool2"]
  enabled: ["tool3"]
  plugins: ["module.path"]
```

**Parameters:**
- `config` (Dict[str, Any]): Configuration dictionary

##### `from_config(config)`
Create a fully configured registry from config.

**Parameters:**
- `config` (Dict[str, Any]): Configuration dictionary

**Returns:**
- `ToolRegistry`: Configured registry instance

## Global Functions

### `get_registry()`
Get or create the global tool registry.

**Returns:**
- `ToolRegistry`: Global registry instance with builtins registered

### `reset_registry()`
Reset the global registry (useful for testing).

## Usage Examples

### Basic Tool Registration
```python
from cortex.tools.registry import get_registry

registry = get_registry()

# Register a custom tool
registry.register(
    name="hello_world",
    tool_class=HelloWorldTool,
    schema={
        "type": "function",
        "function": {
            "name": "hello_world",
            "description": "Say hello",
            "parameters": {"type": "object", "properties": {}}
        }
    }
)

# Check if tool is available
if registry.is_enabled("hello_world"):
    tool_class = registry.get_tool_class("hello_world")
    schema = registry.get_schema("hello_world")
```

### Plugin Loading
```python
# Load a plugin
success = registry.load_plugin("my_plugins.custom_tools")
if success:
    print("Plugin loaded successfully")

# List all tools including plugins
all_tools = registry.list_tools()
plugin_tools = registry.list_tools(namespace="my_plugin")
```

### Configuration
```python
# Apply config to disable tools and load plugins
config = {
    "tools": {
        "disabled": ["web_search", "web_fetch"],
        "plugins": ["company.internal_tools"]
    }
}
registry.apply_config(config)

# Create fully configured registry
registry = ToolRegistry.from_config(config)
```

### Tool Instance Creation
```python
from pathlib import Path

# Create tool instance
tool = registry.create_instance(
    name="read_file",
    project_dir=Path("/project"),
    permission_mode="normal",
    console=my_console
)

# Execute tool
result = tool.execute(path="README.md")
```

## Tool Schema Format

All tools must provide schemas in OpenAI function calling format:

```json
{
  "type": "function",
  "function": {
    "name": "tool_name",
    "description": "Human-readable description",
    "parameters": {
      "type": "object",
      "properties": {
        "param_name": {
          "type": "string|integer|boolean|array|object",
          "description": "Parameter description",
          "enum": ["option1", "option2"]  // optional
        }
      },
      "required": ["param1", "param2"]
    }
  }
}
```

## Built-in Namespaces

- **builtin**: Core Cortex tools (file operations, git, search, etc.)
- **plugin**: External plugin tools
- **ast**: AST analysis tools (when available)

## Error Handling

The registry provides robust error handling:
- Invalid tool names return None/null values
- Plugin loading failures are logged but don't crash
- Configuration errors are handled gracefully
- Tool instantiation validates parameters

## Performance Considerations

- Registry operations are O(1) for most lookups
- Tool schemas are cached in memory
- Plugin loading is lazy (on first access)
- Built-in tools are registered once at startup

## Thread Safety

The registry is not thread-safe for write operations (register/unregister). Read operations are safe for concurrent access. For multi-threaded applications, synchronize registry modifications.
