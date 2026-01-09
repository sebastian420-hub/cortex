"""Dynamic Tool Registry with plugin support"""

from typing import Dict, Any, List, Optional, Type, Callable
from pathlib import Path
import importlib
import logging

from .base import Tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Dynamic tool registry supporting:
    - Tool registration/unregistration
    - Enable/disable tools via config
    - Plugin loading from external modules
    - Namespace support for tool organization
    """

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}  # name -> {class, schema, enabled, ...}
        self._namespaces: Dict[str, List[str]] = {}  # namespace -> [tool_names]
        self._initialized = False

    def register(
        self,
        name: str,
        tool_class: Type[Tool],
        schema: Dict[str, Any],
        namespace: str = "builtin",
        enabled: bool = True
    ) -> None:
        """
        Register a tool with the registry.

        Args:
            name: Tool name (e.g., "read_file")
            tool_class: The Tool subclass
            schema: Tool schema in function calling format
            namespace: Tool namespace (default: "builtin")
            enabled: Whether tool is enabled (default: True)
        """
        # Use namespaced name for non-builtin tools
        full_name = f"{namespace}:{name}" if namespace != "builtin" else name

        self._tools[full_name] = {
            "class": tool_class,
            "schema": schema,
            "namespace": namespace,
            "enabled": enabled,
            "short_name": name
        }

        # Track namespace membership
        if namespace not in self._namespaces:
            self._namespaces[namespace] = []
        if full_name not in self._namespaces[namespace]:
            self._namespaces[namespace].append(full_name)

        logger.debug(f"Registered tool: {full_name} (enabled={enabled})")

    def unregister(self, name: str) -> bool:
        """
        Unregister a tool.

        Args:
            name: Tool name to unregister

        Returns:
            True if tool was unregistered, False if not found
        """
        if name not in self._tools:
            return False

        namespace = self._tools[name]["namespace"]
        if namespace in self._namespaces and name in self._namespaces[namespace]:
            self._namespaces[namespace].remove(name)

        del self._tools[name]
        logger.debug(f"Unregistered tool: {name}")
        return True

    def get_tool_class(self, name: str) -> Optional[Type[Tool]]:
        """
        Get tool class by name.

        Args:
            name: Tool name

        Returns:
            Tool class if found and enabled, None otherwise
        """
        tool_info = self._tools.get(name)
        if tool_info and tool_info["enabled"]:
            return tool_info["class"]
        return None

    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get tool schema by name.

        Args:
            name: Tool name

        Returns:
            Tool schema if found and enabled, None otherwise
        """
        tool_info = self._tools.get(name)
        if tool_info and tool_info["enabled"]:
            return tool_info["schema"]
        return None

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """
        Get all enabled tool schemas.

        Returns:
            List of tool schemas for enabled tools
        """
        return [
            tool["schema"]
            for tool in self._tools.values()
            if tool["enabled"]
        ]

    def enable(self, name: str) -> bool:
        """
        Enable a tool.

        Args:
            name: Tool name to enable

        Returns:
            True if tool was enabled, False if not found
        """
        if name in self._tools:
            self._tools[name]["enabled"] = True
            logger.debug(f"Enabled tool: {name}")
            return True
        return False

    def disable(self, name: str) -> bool:
        """
        Disable a tool.

        Args:
            name: Tool name to disable

        Returns:
            True if tool was disabled, False if not found
        """
        if name in self._tools:
            self._tools[name]["enabled"] = False
            logger.debug(f"Disabled tool: {name}")
            return True
        return False

    def is_enabled(self, name: str) -> bool:
        """Check if a tool is enabled."""
        tool_info = self._tools.get(name)
        return tool_info["enabled"] if tool_info else False

    def list_tools(self, namespace: Optional[str] = None, include_disabled: bool = False) -> List[str]:
        """
        List registered tools.

        Args:
            namespace: Filter by namespace (None for all)
            include_disabled: Include disabled tools (default: False)

        Returns:
            List of tool names
        """
        if namespace:
            tools = self._namespaces.get(namespace, [])
        else:
            tools = list(self._tools.keys())

        if not include_disabled:
            tools = [t for t in tools if self._tools.get(t, {}).get("enabled", False)]

        return tools

    def list_namespaces(self) -> List[str]:
        """List all registered namespaces."""
        return list(self._namespaces.keys())

    def create_instance(
        self,
        name: str,
        project_dir: Path,
        permission_mode: str,
        console,
        **extra_kwargs
    ) -> Tool:
        """
        Create a tool instance.

        Args:
            name: Tool name
            project_dir: Project directory path
            permission_mode: Permission mode string
            console: Console instance for output
            **extra_kwargs: Additional kwargs to pass to tool constructor

        Returns:
            Tool instance

        Raises:
            ValueError: If tool not found or disabled
        """
        tool_class = self.get_tool_class(name)
        if not tool_class:
            raise ValueError(f"Unknown or disabled tool: {name}")

        return tool_class(project_dir, permission_mode, console, **extra_kwargs)

    def register_builtins(self) -> None:
        """Register all built-in tools."""
        if self._initialized:
            return

        # Import tool classes
        from .file_tools import ReadFileTool, WriteFileTool
        from .command_tools import ExecuteCommandTool
        from .search_tools import ListFilesTool, SearchFilesTool
        from .git_tools import GitStatusTool, GitDiffTool, GitCommitTool, GitLogTool
        from .test_tools import RunTestsTool

        # Tool class mapping
        builtin_tools = {
            "read_file": ReadFileTool,
            "write_file": WriteFileTool,
            "execute_command": ExecuteCommandTool,
            "list_files": ListFilesTool,
            "search_files": SearchFilesTool,
            "git_status": GitStatusTool,
            "git_diff": GitDiffTool,
            "git_commit": GitCommitTool,
            "git_log": GitLogTool,
            "run_tests": RunTestsTool,
        }

        # Tool schemas (inline definitions)
        builtin_schemas = {
            "read_file": {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file. Use this when the user explicitly asks to read a file, or when you need to read code to answer a question about it.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative path to the file from project root"
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            "write_file": {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write or overwrite a file with new content. Always read the file first if it exists.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative path to the file"
                            },
                            "content": {
                                "type": "string",
                                "description": "Complete file content to write"
                            }
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            "execute_command": {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "Execute a shell command. Use for git, npm, pip, pytest, etc. Be cautious with destructive commands.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The shell command to execute"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Brief explanation of why this command is needed"
                            }
                        },
                        "required": ["command", "reason"]
                    }
                }
            },
            "list_files": {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in a directory or search for files matching a pattern.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Directory path to list (default: current directory)"
                            },
                            "pattern": {
                                "type": "string",
                                "description": "Optional glob pattern to filter files (e.g., '*.py')"
                            }
                        },
                        "required": []
                    }
                }
            },
            "search_files": {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search for text content across files in the project. Similar to grep.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Text to search for"
                            },
                            "file_pattern": {
                                "type": "string",
                                "description": "Limit search to files matching pattern (e.g., '*.py')"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            "git_status": {
                "type": "function",
                "function": {
                    "name": "git_status",
                    "description": "Show git status and uncommitted changes.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            "git_diff": {
                "type": "function",
                "function": {
                    "name": "git_diff",
                    "description": "Show git diff for a file or all changes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "File path (optional, shows all changes if omitted)"
                            }
                        },
                        "required": []
                    }
                }
            },
            "git_commit": {
                "type": "function",
                "function": {
                    "name": "git_commit",
                    "description": "Commit changes with a message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "Commit message"
                            }
                        },
                        "required": ["message"]
                    }
                }
            },
            "git_log": {
                "type": "function",
                "function": {
                    "name": "git_log",
                    "description": "Show recent git commits.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Number of commits to show (default: 10)"
                            }
                        },
                        "required": []
                    }
                }
            },
            "run_tests": {
                "type": "function",
                "function": {
                    "name": "run_tests",
                    "description": "Run test suite or specific tests. Auto-detects pytest or unittest.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Test pattern (e.g., 'test_auth.py')"
                            },
                            "verbose": {
                                "type": "boolean",
                                "description": "Verbose output"
                            }
                        },
                        "required": []
                    }
                }
            }
        }

        # Register all builtin tools
        for name, tool_class in builtin_tools.items():
            schema = builtin_schemas.get(name)
            if schema:
                self.register(name, tool_class, schema, namespace="builtin")

        self._initialized = True
        logger.info(f"Registered {len(builtin_tools)} built-in tools")

    def load_plugin(self, plugin_path: str) -> bool:
        """
        Load tools from a plugin module.

        Plugin modules should export a PLUGIN_TOOLS list:
        PLUGIN_TOOLS = [
            {
                "name": "my_tool",
                "class": MyToolClass,
                "schema": {...},
                "namespace": "my_plugin"  # optional
            }
        ]

        Args:
            plugin_path: Python module path (e.g., "my_plugins.custom_tools")

        Returns:
            True if plugin loaded successfully, False otherwise
        """
        try:
            module = importlib.import_module(plugin_path)

            # Look for PLUGIN_TOOLS list
            if hasattr(module, "PLUGIN_TOOLS"):
                for tool_info in module.PLUGIN_TOOLS:
                    self.register(
                        name=tool_info["name"],
                        tool_class=tool_info["class"],
                        schema=tool_info["schema"],
                        namespace=tool_info.get("namespace", "plugin"),
                        enabled=tool_info.get("enabled", True)
                    )
                logger.info(f"Loaded plugin: {plugin_path}")
                return True
            else:
                logger.warning(f"Plugin {plugin_path} has no PLUGIN_TOOLS list")
                return False

        except ImportError as e:
            logger.error(f"Failed to import plugin {plugin_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading plugin {plugin_path}: {e}")
            return False

    def apply_config(self, config: Dict[str, Any]) -> None:
        """
        Apply configuration to the registry.

        Config format:
        {
            "tools": {
                "disabled": ["tool1", "tool2"],
                "enabled": ["tool3"],
                "plugins": ["module.path"]
            }
        }

        Args:
            config: Configuration dictionary
        """
        tools_config = config.get("tools", {})

        # Disable specified tools
        for tool_name in tools_config.get("disabled", []):
            self.disable(tool_name)

        # Enable specified tools (useful for re-enabling defaults)
        for tool_name in tools_config.get("enabled", []):
            self.enable(tool_name)

        # Load plugins
        for plugin_path in tools_config.get("plugins", []):
            self.load_plugin(plugin_path)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "ToolRegistry":
        """
        Create a fully configured registry from config.

        Args:
            config: Configuration dictionary

        Returns:
            Configured ToolRegistry instance
        """
        registry = cls()
        registry.register_builtins()
        registry.apply_config(config)
        return registry


# Global registry instance (lazy initialized)
_global_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """
    Get or create the global tool registry.

    Returns:
        Global ToolRegistry instance with builtins registered
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
        _global_registry.register_builtins()
    return _global_registry


def reset_registry() -> None:
    """Reset the global registry (useful for testing)."""
    global _global_registry
    _global_registry = None
