"""Tool implementations for LocalAgent"""

from typing import List, Dict, Any
from pathlib import Path

from .base import Tool
from .file_tools import ReadFileTool, WriteFileTool
from .command_tools import ExecuteCommandTool
from .search_tools import ListFilesTool, SearchFilesTool
from .git_tools import GitStatusTool, GitDiffTool, GitCommitTool, GitLogTool
from .test_tools import RunTestsTool

# Tool definitions matching Anthropic's function calling format
TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Use this to understand existing code before making changes.",
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
    {
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
    {
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
    {
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
    {
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
    {
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
    {
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
    {
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
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run test suite or specific tests. Auto-detects pytest or unittest.",
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
    """Create a tool instance by name"""
    tools_map = {
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
    
    tool_class = tools_map.get(tool_name)
    if not tool_class:
        raise ValueError(f"Unknown tool: {tool_name}")
    
    return tool_class(project_dir, permission_mode, console)


__all__ = [
    "TOOLS",
    "Tool",
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
    "create_tool_instance",
]

