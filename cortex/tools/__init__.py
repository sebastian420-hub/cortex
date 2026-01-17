"""Tool implementations for Cortex"""

from typing import List, Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path

from .base import Tool
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

# Phase 3 web tools
from .web_tools import WebFetchTool, WebSearchTool, clear_fetch_cache
# Skill tools
from .skill_tools import SkillLoaderTool
from .todo_tool import (
    TodoWriteTool,
    TodoManager,
    TodoItem,
    TodoStatus,
    TODO_TOOL_SCHEMA,
    get_todo_manager,
    set_todo_manager,
    display_todos,
)
from .ask_user_tool import (
    AskUserQuestionTool,
    QuestionOption,
    QuestionAnswer,
    ASK_USER_TOOL_SCHEMA,
)
from .registry import ToolRegistry, get_registry, reset_registry
from ..subagent import TaskTool, TASK_TOOL_SCHEMA
# Planning tools
from .planning_tools import (
    CREATE_PLAN_SCHEMA,
    EXECUTE_PLAN_SCHEMA,
    MONITOR_PLAN_SCHEMA,
    UPDATE_PLAN_SCHEMA,
)
# Delegation tools for model orchestration
from .delegation_tools import (
    DelegateToModelTool,
    ReturnToCoordinatorTool,
    DELEGATE_TO_MODEL_SCHEMA,
    RETURN_TO_COORDINATOR_SCHEMA,
    get_delegation_schemas,
)

if TYPE_CHECKING:
    from ..agent import Cortex
    from ..utils.timeouts import TimeoutConfig
    from ..core.transaction import TransactionManager

# Tool definitions matching Anthropic's function calling format
# NOTE: This list is kept for backward compatibility.
# New code should use get_registry().get_all_schemas() instead.
TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Supports reading large files in chunks with offset and limit. Use this when you need to read code or file contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from project root",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Line number to start reading from (0-indexed). Useful for large files.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to read. Default: 2000 lines.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite a file with new content. Always read the file first if it exists. Use this when the user explicitly requests creating or modifying a file. Do NOT use this for greetings, questions, or casual conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to the file"},
                    "content": {"type": "string", "description": "Complete file content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a shell command. Use this ONLY when the user explicitly requests running a command (e.g., 'install dependencies', 'run tests', 'git status'). Use for git, npm, pip, pytest, etc. Be cautious with destructive commands. Do NOT use this for greetings, questions, or casual conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"},
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of why this command is needed",
                    },
                },
                "required": ["command", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory or search for files matching a pattern. Use this when the user explicitly requests listing files or exploring the project structure. Do NOT use this for greetings, general questions, or casual conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list (default: current directory)",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g., '*.py')",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "[DEPRECATED - Use 'grep' instead] Basic text search. The 'grep' tool is more powerful.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to search for"},
                    "file_pattern": {
                        "type": "string",
                        "description": "Limit search to files matching pattern (e.g., '*.py')",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Powerful regex search tool. Searches for patterns in files with multiple output modes. Use this to find code, text, or patterns across the codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for (e.g., 'def.*async', 'class\\s+\\w+')",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory or file to search in (default: current directory)",
                    },
                    "glob": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '*.py', '*.{ts,tsx}')",
                    },
                    "file_type": {
                        "type": "string",
                        "description": "File type to search (e.g., 'py', 'js', 'rust', 'go')",
                    },
                    "output_mode": {
                        "type": "string",
                        "enum": ["files_with_matches", "content", "count"],
                        "description": "Output mode: 'files_with_matches' (default), 'content' (show matches), 'count' (match counts)",
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "Case insensitive search (default: false)",
                    },
                    "context": {
                        "type": "integer",
                        "description": "Lines of context before and after matches",
                    },
                    "multiline": {
                        "type": "boolean",
                        "description": "Enable multiline matching (default: false)",
                    },
                    "head_limit": {
                        "type": "integer",
                        "description": "Limit number of results (default: 50)",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Fast file pattern matching. Find files by glob patterns like '**/*.py'. Results sorted by modification time (newest first).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match (e.g., '**/*.py', 'src/**/*.ts', '*.md')",
                    },
                    "path": {
                        "type": "string",
                        "description": "Base directory to search from (default: current directory)",
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Include hidden files/directories (default: false)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 500)",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "Surgical file editing - replace exact strings. More precise than rewriting entire files. The old_string must match exactly (including whitespace/indentation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file to edit"},
                    "old_string": {
                        "type": "string",
                        "description": "Exact text to replace (must be unique in file unless using replace_all)",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Text to replace it with (must be different from old_string)",
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences (default: false, requires unique match)",
                    },
                },
                "required": ["file_path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show git status and uncommitted changes. Use this when the user explicitly requests git status or wants to see what files have changed. Do NOT use this for greetings, general questions, or casual conversation.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show git diff for a file or all changes. Use this when the user explicitly requests to see differences or changes. Do NOT use this for greetings, general questions, or casual conversation.",
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
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commit changes with a message. Use this when the user explicitly requests to commit changes. Do NOT use this for greetings, general questions, or casual conversation.",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string", "description": "Commit message"}},
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Show recent git commits. Use this when the user explicitly requests to see commit history. Do NOT use this for greetings, general questions, or casual conversation.",
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
    {
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
                        "description": "The action to perform: 'list', 'create', or 'delete'. Defaults to 'list'.",
                    },
                    "branch_name": {
                        "type": "string",
                        "description": "The name of the branch for 'create' or 'delete' actions.",
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force deletion of the branch. Use with caution. Defaults to false.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": "Push commits to a remote repository. This is a high-risk operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {
                        "type": "string",
                        "description": "The name of the remote to push to. Defaults to 'origin'.",
                    },
                    "branch": {
                        "type": "string",
                        "description": "The local branch to push. If not specified, Git's default behavior is used.",
                    },
                },
                "required": [],
            },
        },
    },
    {
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
    {
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
    {
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
    {
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
    {
        "type": "function",
        "function": {
            "name": "git_fetch",
            "description": "Fetch changes from a remote repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {
                        "type": "string",
                        "description": "The name of the remote to fetch from. Defaults to 'origin'.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_pull",
            "description": "Fetch from and integrate with another repository or a local branch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {
                        "type": "string",
                        "description": "The name of the remote to pull from. Defaults to 'origin'.",
                    },
                    "branch": {
                        "type": "string",
                        "description": "The remote branch to pull. If not specified, Git's default behavior is used.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_add",
            "description": "Stage changes for the next commit. Use to add specific files or all changes.",
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
                        "description": "Stage all changes in the repository (equivalent to 'git add --all').",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run test suite or specific tests. Auto-detects pytest or unittest. Use this when the user explicitly requests running tests. Do NOT use this for greetings, general questions, or casual conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Test pattern (e.g., 'test_auth.py' or 'tests/test_auth.py')",
                    },
                    "verbose": {"type": "boolean", "description": "Verbose output"},
                },
                "required": [],
            },
        },
    },
    # Phase 3 Web tools
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch content from a URL and convert to markdown. Use this to read documentation, web pages, or API responses. Includes 15-minute cache.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch (e.g., 'https://docs.python.org/3/library/json.html')",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Optional: What to extract/analyze from the content",
                    },
                    "max_content_length": {
                        "type": "integer",
                        "description": "Maximum content length to return (default: 50000)",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information. Returns titles, URLs, and snippets. Use to find documentation, examples, or solutions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'python requests library documentation')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
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
    {
        "type": "function",
        "function": {
            "name": "skill_loader",
            "description": "Load and manage development skills for common tasks like TDD, refactoring, debugging, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "load", "suggest", "get"],
                        "description": "Action to perform: 'list' (list skills), 'load' (load specific skill), 'suggest' (suggest skills for task), 'get' (get skill details)"
                    },
                    "skill_name": {
                        "type": "string",
                        "description": "Name of skill (for load/get actions)"
                    },
                    "task_description": {
                        "type": "string",
                        "description": "Task description (for suggest action)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of skills to return (for list/suggest)"
                    }
                },
                "required": ["action"],
            },
        },
    },
    # Task tool for subagent delegation
    TASK_TOOL_SCHEMA,
    # Todo tracking tool
    TODO_TOOL_SCHEMA,
    # Ask user questions tool
    ASK_USER_TOOL_SCHEMA,
    # Planning tools for enhanced agent
    CREATE_PLAN_SCHEMA,
    EXECUTE_PLAN_SCHEMA,
    MONITOR_PLAN_SCHEMA,
    UPDATE_PLAN_SCHEMA,
    # Delegation tools for model orchestration
    DELEGATE_TO_MODEL_SCHEMA,
    RETURN_TO_COORDINATOR_SCHEMA,
]


def create_tool_instance(
    tool_name: str,
    project_dir: Path,
    permission_mode: str,
    console,
    parent_agent: Optional["Cortex"] = None,
    timeout_config: Optional["TimeoutConfig"] = None,
    transaction_manager: Optional["TransactionManager"] = None,
) -> Tool:
    """
    Create a tool instance by name.

    This function delegates to the global ToolRegistry for tool creation.
    It maintains backward compatibility while supporting the new registry system.

    Args:
        tool_name: Name of the tool to create
        project_dir: Project directory path
        permission_mode: Permission mode string
        console: Console instance for output
        parent_agent: Parent agent instance (required for task tool)
        timeout_config: Optional timeout configuration for tool operations
        transaction_manager: Optional transaction manager for file operations

    Returns:
        Tool instance

    Raises:
        ValueError: If tool is not found or disabled
    """
    # Special handling for task tool which needs parent_agent
    if tool_name == "task":
        return TaskTool(
            project_dir=project_dir,
            permission_mode=permission_mode,
            console=console,
            parent_agent=parent_agent,
            timeout_config=timeout_config,
        )

    # Special handling for todo_write tool
    if tool_name == "todo_write":
        return TodoWriteTool(
            project_dir=project_dir,
            permission_mode=permission_mode,
            console=console,
            timeout_config=timeout_config,
        )

    # Special handling for ask_user_question tool
    if tool_name == "ask_user_question":
        return AskUserQuestionTool(
            project_dir=project_dir,
            permission_mode=permission_mode,
            console=console,
            timeout_config=timeout_config,
        )

    # Special handling for delegation tools (model orchestration)
    if tool_name == "delegate_to_model":
        from .delegation_tools import DelegateToModelTool
        delegation_tracker = None
        model_registry = None
        current_model = None
        if parent_agent:
            delegation_tracker = getattr(parent_agent, "_delegation_tracker", None)
            model_registry = getattr(parent_agent, "_model_registry", None)
            current_model = getattr(parent_agent, "model", None)
        return DelegateToModelTool(
            project_dir=project_dir,
            permission_mode=permission_mode,
            console=console,
            timeout_config=timeout_config,
            delegation_tracker=delegation_tracker,
            model_registry=model_registry,
            current_model=current_model,
        )

    if tool_name == "return_to_coordinator":
        from .delegation_tools import ReturnToCoordinatorTool
        delegation_tracker = None
        current_model = None
        coordinator_model = "mimo-v2-flash"
        if parent_agent:
            delegation_tracker = getattr(parent_agent, "_delegation_tracker", None)
            current_model = getattr(parent_agent, "model", None)
            orchestration = getattr(parent_agent, "_orchestration", None)
            if orchestration:
                coordinator_model = orchestration.default_coordinator
        return ReturnToCoordinatorTool(
            project_dir=project_dir,
            permission_mode=permission_mode,
            console=console,
            timeout_config=timeout_config,
            delegation_tracker=delegation_tracker,
            current_model=current_model,
            coordinator_model=coordinator_model,
        )

    return get_registry().create_instance(
        tool_name,
        project_dir,
        permission_mode,
        console,
        timeout_config=timeout_config,
        transaction_manager=transaction_manager,
        parent_agent=parent_agent,
    )


__all__ = [
    # Tool schemas (backward compatible)
    "TOOLS",
    "TASK_TOOL_SCHEMA",
    "TODO_TOOL_SCHEMA",
    "ASK_USER_TOOL_SCHEMA",
    "CREATE_PLAN_SCHEMA",
    "EXECUTE_PLAN_SCHEMA",
    "MONITOR_PLAN_SCHEMA",
    "UPDATE_PLAN_SCHEMA",
    "DELEGATE_TO_MODEL_SCHEMA",
    "RETURN_TO_COORDINATOR_SCHEMA",
    # Base class
    "Tool",
    # Tool implementations
    "ReadFileTool",
    "WriteFileTool",
    "ExecuteCommandTool",
    "ListFilesTool",
    "SearchFilesTool",
    "GitStatusTool",
    "GitDiffTool",
    "GitCommitTool",
    "GitLogTool",
    "GitAddTool",
    "GitBranchTool",
    "GitPushTool",
    "GitRemoteTool",
    "GitShowTool",
    "GitCheckoutTool",
    "GitResetTool",
    "GitFetchTool",
    "GitPullTool",
    "RunTestsTool",
    "TaskTool",
    "TodoWriteTool",
    "AskUserQuestionTool",
    # Delegation tools for model orchestration
    "DelegateToModelTool",
    "ReturnToCoordinatorTool",
    "get_delegation_schemas",
    # New Phase 1 tools
    "GrepTool",
    "GlobTool",
    "EditTool",
    # Phase 3 web tools
    "WebFetchTool",
    "WebSearchTool",
    "clear_fetch_cache",
    # Skill tools
    "SkillLoaderTool",
    # Todo management
    "TodoManager",
    "TodoItem",
    "TodoStatus",
    "get_todo_manager",
    "set_todo_manager",
    "display_todos",
    # Ask user question helpers
    "QuestionOption",
    "QuestionAnswer",
    # Factory function (backward compatible)
    "create_tool_instance",
    # Registry (new)
    "ToolRegistry",
    "get_registry",
    "reset_registry",
]
