"""Tool implementations for LocalAgent"""

from typing import List, Dict, Any
from pathlib import Path

from .base import Tool
from .file_tools import ReadFileTool, WriteFileTool
from .command_tools import ExecuteCommandTool
from .search_tools import ListFilesTool, SearchFilesTool
from .git_tools import GitStatusTool, GitDiffTool, GitCommitTool, GitLogTool
from .test_tools import RunTestsTool
from .registry import ToolRegistry, get_registry, reset_registry

# Tool definitions matching Anthropic's function calling format
# NOTE: This list is kept for backward compatibility.
# New code should use get_registry().get_all_schemas() instead.
TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Use this when the user explicitly asks to read a file, or when you need to read code to answer a question about it. Do NOT use this for greetings, general questions, or casual conversation.",
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
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite a file with new content. Always read the file first if it exists. Use this when the user explicitly requests creating or modifying a file. Do NOT use this for greetings, questions, or casual conversation.",
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
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a shell command. Use this ONLY when the user explicitly requests running a command (e.g., 'install dependencies', 'run tests', 'git status'). Use for git, npm, pip, pytest, etc. Be cautious with destructive commands. Do NOT use this for greetings, questions, or casual conversation.",
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
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for text content across files in the project. Similar to grep. Use this when the user explicitly requests searching for code or text, or when you need to find where something is used. Do NOT use this for greetings, general questions, or casual conversation.",
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
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show git status and uncommitted changes. Use this when the user explicitly requests git status or wants to see what files have changed. Do NOT use this for greetings, general questions, or casual conversation.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
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
                        "description": "File path (optional, shows all changes if omitted)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commit changes with a message. Use this when the user explicitly requests to commit changes. Do NOT use this for greetings, general questions, or casual conversation.",
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
                        "description": "Number of commits to show (default: 10)"
                    }
                },
                "required": []
            }
        }
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
                        "description": "Test pattern (e.g., 'test_auth.py' or 'tests/test_auth.py')"
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
]


def create_tool_instance(tool_name: str, project_dir: Path, permission_mode: str, console) -> Tool:
    """
    Create a tool instance by name.

    This function delegates to the global ToolRegistry for tool creation.
    It maintains backward compatibility while supporting the new registry system.

    Args:
        tool_name: Name of the tool to create
        project_dir: Project directory path
        permission_mode: Permission mode string
        console: Console instance for output

    Returns:
        Tool instance

    Raises:
        ValueError: If tool is not found or disabled
    """
    return get_registry().create_instance(tool_name, project_dir, permission_mode, console)


__all__ = [
    # Tool schemas (backward compatible)
    "TOOLS",
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
    "RunTestsTool",
    # Factory function (backward compatible)
    "create_tool_instance",
    # Registry (new)
    "ToolRegistry",
    "get_registry",
    "reset_registry",
]

