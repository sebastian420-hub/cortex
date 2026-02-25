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
        enabled: bool = True,
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
            "short_name": name,
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

    def get_all_schemas(self, exclude_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get all enabled tool schemas.

        Args:
            exclude_names: Optional list of tool names to exclude

        Returns:
            List of tool schemas for enabled tools
        """
        schemas = []
        exclude = exclude_names or []
        for name, tool_info in self._tools.items():
            if (
                tool_info["enabled"]
                and name not in exclude
                and tool_info["short_name"] not in exclude
            ):
                schemas.append(tool_info["schema"])
        return schemas

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

    def list_tools(
        self, namespace: Optional[str] = None, include_disabled: bool = False
    ) -> List[str]:
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
        self, name: str, project_dir: Path, permission_mode: str, console, **extra_kwargs
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
        from .git_tools import (
            GitStatusTool,
            GitDiffTool,
            GitCommitTool,
            GitLogTool,
            GitAddTool,
            GitBranchTool,
            GitPushTool,
            GitRemoteTool,
            GitShowTool,
            GitCheckoutTool,
            GitResetTool,
            GitFetchTool,
            GitPullTool,
        )
        from .test_tools import RunTestsTool

        # New Phase 1 tools
        from .grep_tool import GrepTool
        from .glob_tool import GlobTool
        from .edit_tool import EditTool

        # Metacognition tools
        from .metacognition import MetacognitiveReflectorTool, REFLECT_SCHEMA

        # Phase 3 web tools
        from .web_tools import WebFetchTool, WebSearchTool

        # Skill tools
        from .skill_tools import SkillLoaderTool

        # Planning tools
        from .planning_tools import (
            CreatePlanTool,
            ExecutePlanTool,
            MonitorPlanTool,
            UpdatePlanTool,
            CreateAndExecutePlanTool,
            CREATE_PLAN_SCHEMA,
            EXECUTE_PLAN_SCHEMA,
            MONITOR_PLAN_SCHEMA,
            UPDATE_PLAN_SCHEMA,
            CREATE_AND_EXECUTE_PLAN_SCHEMA,
        )

        # Delegation tools (for model orchestration)
        from .delegation_tools import (
            DelegateToModelTool,
            ReturnToCoordinatorTool,
            DELEGATE_TO_MODEL_SCHEMA,
            RETURN_TO_COORDINATOR_SCHEMA,
        )

        # User interaction tools
        from .ask_user_tool import (
            AskUserQuestionTool,
            ASK_USER_TOOL_SCHEMA,
        )

        # Todo/task management tools
        from .todo_tool import (
            TodoWriteTool,
            TODO_TOOL_SCHEMA,
        )

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
            "git_add": GitAddTool,
            "git_branch": GitBranchTool,
            "git_push": GitPushTool,
            "git_remote": GitRemoteTool,
            "git_show": GitShowTool,
            "git_checkout": GitCheckoutTool,
            "git_reset": GitResetTool,
            "git_fetch": GitFetchTool,
            "git_pull": GitPullTool,
            "run_tests": RunTestsTool,
            # New Phase 1 tools
            "grep": GrepTool,
            "glob": GlobTool,
            "edit": EditTool,
            "metacognitive_reflect": MetacognitiveReflectorTool,
            # Phase 3 web tools
            "web_fetch": WebFetchTool,
            "web_search": WebSearchTool,
            # Skill tools
            "skill_loader": SkillLoaderTool,
            # Planning tools
            "create_plan": CreatePlanTool,
            "execute_plan": ExecutePlanTool,
            "monitor_plan": MonitorPlanTool,
            "update_plan": UpdatePlanTool,
            "create_and_execute_plan": CreateAndExecutePlanTool,
            # Delegation tools (model orchestration)
            "delegate_to_model": DelegateToModelTool,
            "return_to_coordinator": ReturnToCoordinatorTool,
            # User interaction tools
            "ask_user_question": AskUserQuestionTool,
            # Todo/task management tools
            "todo_write": TodoWriteTool,
        }

        # Tool schemas (inline definitions)
        builtin_schemas = {
            "read_file": {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file. Supports reading large files in chunks with offset and limit.",  # noqa: E501
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative path to the file from project root",
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Line number to start reading from (0-indexed)",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of lines to read",
                            },
                        },
                        "required": ["path"],
                    },
                },
            },
            "write_file": {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write or overwrite a file with new content. Always read the file first if it exists.",  # noqa: E501
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path to the file"},
                            "content": {
                                "type": "string",
                                "description": "Complete file content to write",
                            },
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            "execute_command": {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "Execute a shell command. Use for git, npm, pip, pytest, etc. Be cautious with destructive commands.",  # noqa: E501
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The shell command to execute",
                            },
                            "reason": {
                                "type": "string",
                                "description": "Brief explanation of why this command is needed",
                            },
                        },
                        "required": ["command", "reason"],
                    },
                },
            },
            "list_files": {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in a directory or search for files matching a pattern.",  # noqa: E501
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Directory path to list (default: current directory)",  # noqa: E501
                            },
                            "pattern": {
                                "type": "string",
                                "description": "Optional glob pattern to filter files (e.g., '*.py')",  # noqa: E501
                            },
                        },
                        "required": [],
                    },
                },
            },
            "search_files": {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search for text content across files in the project. Similar to grep.",  # noqa: E501
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Text to search for"},
                            "file_pattern": {
                                "type": "string",
                                "description": "Limit search to files matching pattern (e.g., '*.py')",  # noqa: E501
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            "git_status": {
                "type": "function",
                "function": {
                    "name": "git_status",
                    "description": "Show git status and uncommitted changes.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
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
                                "description": "File path (optional, shows all changes if omitted)",
                            }
                        },
                        "required": [],
                    },
                },
            },
            "git_commit": {
                "type": "function",
                "function": {
                    "name": "git_commit",
                    "description": "Commit changes with a message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "Commit message"}
                        },
                        "required": ["message"],
                    },
                },
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
                                "description": "Number of commits to show (default: 10)",
                            }
                        },
                        "required": [],
                    },
                },
            },
            "git_add": {
                "type": "function",
                "function": {
                    "name": "git_add",
                    "description": "Stage changes for the next commit. Use to add specific files or all changes.",  # noqa: E501
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "A list of specific file paths to stage.",
                            },
                            "add_all": {
                                "type": "boolean",
                                "description": "Stage all changes in the repository (equivalent to 'git add --all').",  # noqa: E501
                            },
                        },
                        "required": [],
                    },
                },
            },
            "git_branch": {
                "type": "function",
                "function": {
                    "name": "git_branch",
                    "description": "List, create, or delete branches. Default action is 'list'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["list", "create", "delete"],
                                "description": "The action to perform: 'list', 'create', or 'delete'. Defaults to 'list'.",  # noqa: E501
                            },
                            "branch_name": {
                                "type": "string",
                                "description": "The name of the branch for 'create' or 'delete' actions.",  # noqa: E501
                            },
                            "force": {
                                "type": "boolean",
                                "description": "Force deletion of the branch. Use with caution. Defaults to false.",  # noqa: E501
                            },
                        },
                        "required": [],
                    },
                },
            },
            "git_push": {
                "type": "function",
                "function": {
                    "name": "git_push",
                    "description": "Push commits to a remote repository. This is a high-risk operation.",  # noqa: E501
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "remote": {
                                "type": "string",
                                "description": "The name of the remote to push to. Defaults to 'origin'.",  # noqa: E501
                            },
                            "branch": {
                                "type": "string",
                                "description": "The local branch to push. If not specified, Git's default behavior is used.",  # noqa: E501
                            },
                        },
                        "required": [],
                    },
                },
            },
            "git_remote": {
                "type": "function",
                "function": {
                    "name": "git_remote",
                    "description": "List git remotes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "verbose": {
                                "type": "boolean",
                                "description": "Show remote URLs. Defaults to false.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            "git_show": {
                "type": "function",
                "function": {
                    "name": "git_show",
                    "description": "Show details of a git object (commit, tag, etc.).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ref": {
                                "type": "string",
                                "description": "The git reference to show. Defaults to 'HEAD'.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            "git_checkout": {
                "type": "function",
                "function": {
                    "name": "git_checkout",
                    "description": "Switch branches or create a new one.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "branch": {
                                "type": "string",
                                "description": "The name of the branch to checkout or create.",
                            },
                            "new_branch": {
                                "type": "boolean",
                                "description": "If true, creates a new branch. Defaults to false.",
                            },
                        },
                        "required": ["branch"],
                    },
                },
            },
            "git_reset": {
                "type": "function",
                "function": {
                    "name": "git_reset",
                    "description": "Unstage files from the index (the opposite of 'git add').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "A list of specific file paths to unstage.",
                            },
                        },
                        "required": ["files"],
                    },
                },
            },
            "git_fetch": {
                "type": "function",
                "function": {
                    "name": "git_fetch",
                    "description": "Fetch changes from a remote repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "remote": {
                                "type": "string",
                                "description": "The name of the remote to fetch from. Defaults to 'origin'.",  # noqa: E501
                            },
                        },
                        "required": [],
                    },
                },
            },
            "git_pull": {
                "type": "function",
                "function": {
                    "name": "git_pull",
                    "description": "Fetch from and integrate with another repository or a local branch.",  # noqa: E501
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "remote": {
                                "type": "string",
                                "description": "The name of the remote to pull from. Defaults to 'origin'.",  # noqa: E501
                            },
                            "branch": {
                                "type": "string",
                                "description": "The remote branch to pull. If not specified, Git's default behavior is used.",  # noqa: E501
                            },
                        },
                        "required": [],
                    },
                },
            },
            "run_tests": {
                "type": "function",
                "function": {
                    "name": "run_tests",
                    "description": "Run test suite or specific tests. Auto-detects pytest or unittest.",  # noqa: E501
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Test pattern (e.g., 'test_auth.py')",
                            },
                            "verbose": {"type": "boolean", "description": "Verbose output"},
                        },
                        "required": [],
                    },
                },
            },
            # New Phase 1 tools
            "grep": {
                "type": "function",
                "function": {
                    "name": "grep",
                    "description": "Powerful regex search tool. Searches for patterns in files with multiple output modes.",  # noqa: E501
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Regex pattern to search for",
                            },
                            "path": {
                                "type": "string",
                                "description": "Directory or file to search in",
                            },
                            "glob": {
                                "type": "string",
                                "description": "Glob pattern to filter files",
                            },
                            "file_type": {
                                "type": "string",
                                "description": "File type to search (e.g., 'py', 'js')",
                            },
                            "output_mode": {
                                "type": "string",
                                "description": "Output mode: files_with_matches, content, count",
                            },
                            "case_insensitive": {
                                "type": "boolean",
                                "description": "Case insensitive search",
                            },
                            "context": {"type": "integer", "description": "Lines of context"},
                            "multiline": {
                                "type": "boolean",
                                "description": "Enable multiline matching",
                            },
                            "head_limit": {
                                "type": "integer",
                                "description": "Limit number of results",
                            },
                        },
                        "required": ["pattern"],
                    },
                },
            },
            "glob": {
                "type": "function",
                "function": {
                    "name": "glob",
                    "description": "Fast file pattern matching. Find files by glob patterns.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Glob pattern to match (e.g., '**/*.py')",
                            },
                            "path": {
                                "type": "string",
                                "description": "Base directory to search from",
                            },
                            "include_hidden": {
                                "type": "boolean",
                                "description": "Include hidden files",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results",
                            },
                        },
                        "required": ["pattern"],
                    },
                },
            },
            "edit": {
                "type": "function",
                "function": {
                    "name": "edit",
                    "description": "Surgical file editing - replace exact strings.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file to edit",
                            },
                            "old_string": {
                                "type": "string",
                                "description": "Exact text to replace",
                            },
                            "new_string": {
                                "type": "string",
                                "description": "Text to replace it with",
                            },
                            "replace_all": {
                                "type": "boolean",
                                "description": "Replace all occurrences",
                            },
                        },
                        "required": ["file_path", "old_string", "new_string"],
                    },
                },
            },
            "metacognitive_reflect": REFLECT_SCHEMA,
            # Phase 3 web tools
            "web_fetch": {
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "description": "Fetch content from a URL and convert to markdown.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "The URL to fetch"},
                            "prompt": {
                                "type": "string",
                                "description": "What to extract/analyze from the content",
                            },
                            "max_content_length": {
                                "type": "integer",
                                "description": "Maximum content length (default: 50000)",
                            },
                        },
                        "required": ["url"],
                    },
                },
            },
            "web_search": {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum results (default: 10)",
                            },
                            "allowed_domains": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Only include results from these domains",
                            },
                            "blocked_domains": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Exclude results from these domains",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            "skill_loader": {
                "type": "function",
                "function": {
                    "name": "skill_loader",
                    "description": "Load and manage development skills for common tasks like TDD, refactoring, debugging, etc.",  # noqa: E501
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["list", "load", "suggest", "get"],
                                "description": "Action to perform: 'list' (list skills), 'load' (load specific skill), 'suggest' (suggest skills for task), 'get' (get skill details)",  # noqa: E501
                            },
                            "skill_name": {
                                "type": "string",
                                "description": "Name of skill (for load/get actions)",
                            },
                            "task_description": {
                                "type": "string",
                                "description": "Task description (for suggest action)",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of skills to return (for list/suggest)",  # noqa: E501
                            },
                        },
                        "required": ["action"],
                    },
                },
            },
            "create_plan": CREATE_PLAN_SCHEMA,
            "execute_plan": EXECUTE_PLAN_SCHEMA,
            "monitor_plan": MONITOR_PLAN_SCHEMA,
            "update_plan": UPDATE_PLAN_SCHEMA,
            "create_and_execute_plan": CREATE_AND_EXECUTE_PLAN_SCHEMA,
            # Delegation tools (model orchestration)
            "delegate_to_model": DELEGATE_TO_MODEL_SCHEMA,
            "return_to_coordinator": RETURN_TO_COORDINATOR_SCHEMA,
            # User interaction tools
            "ask_user_question": ASK_USER_TOOL_SCHEMA,
            # Todo/task management tools
            "todo_write": TODO_TOOL_SCHEMA,
        }

        # Register all builtin tools
        for name, tool_class in builtin_tools.items():
            schema = builtin_schemas.get(name)
            if schema:
                self.register(name, tool_class, schema, namespace="builtin")

        # Register AST tools if available
        try:
            from .ast.integration import register_ast_tools, is_ast_available

            if is_ast_available():
                register_ast_tools(self)
                logger.info("AST tools registered successfully")
            else:
                logger.info("AST parsing not available, skipping AST tools")
        except ImportError as e:
            logger.warning(f"Failed to import AST tools: {e}")

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
                        enabled=tool_info.get("enabled", True),
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
