"""Help content definitions for Cortex."""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class HelpCategory(Enum):
    """Categories for help entries."""

    SESSION = "session"
    FILE = "file"
    SEARCH = "search"
    GIT = "git"
    TEST = "test"
    WEB = "web"
    CONTEXT = "context"
    ADVANCED = "advanced"


@dataclass
class HelpEntry:
    """A single help entry."""

    command: str
    short_desc: str
    long_desc: str
    category: HelpCategory
    examples: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    beginner_friendly: bool = True
    project_types: List[str] = field(default_factory=list)  # Empty = all


# All help entries
HELP_ENTRIES: List[HelpEntry] = [
    # Session Commands
    HelpEntry(
        command="/help",
        short_desc="Show available commands",
        long_desc="Display a list of all available commands and their descriptions. Use /help <topic> for detailed information about a specific topic.",
        category=HelpCategory.SESSION,
        examples=["/help", "/help git", "/help search files"],
        keywords=["help", "commands", "usage", "documentation"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="/clear",
        short_desc="Clear conversation history",
        long_desc="Clears all messages from the current conversation. The system prompt is preserved. Use /reset-context to preserve memory bank as well.",
        category=HelpCategory.SESSION,
        examples=["/clear"],
        related=["/reset-context", "/memory"],
        keywords=["clear", "reset", "conversation", "history"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="/mode",
        short_desc="Change permission mode",
        long_desc="Switch between permission modes:\n- normal: Ask for confirmation before file modifications\n- auto: Auto-approve all actions (dangerous!)\n- plan: Read-only mode for exploration",
        category=HelpCategory.SESSION,
        examples=["/mode normal", "/mode auto", "/mode plan", "/mode"],
        keywords=["mode", "permission", "auto", "plan", "normal", "approve"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="/project",
        short_desc="Show project information",
        long_desc="Display current project details including path, permission mode, model being used, session duration, and token usage.",
        category=HelpCategory.SESSION,
        examples=["/project"],
        keywords=["project", "info", "status", "tokens"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="/save",
        short_desc="Save current session",
        long_desc="Save the current conversation session to a file. Sessions can be loaded later to continue work. If no name is provided, a timestamp-based name is used.",
        category=HelpCategory.SESSION,
        examples=["/save", "/save myproject", "/save feature-auth"],
        related=["/load", "/sessions"],
        keywords=["save", "session", "export", "backup"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="/load",
        short_desc="Load a saved session",
        long_desc="Load a previously saved session to continue work. Use /sessions to see available sessions.",
        category=HelpCategory.SESSION,
        examples=["/load myproject", "/load feature-auth"],
        related=["/save", "/sessions"],
        keywords=["load", "session", "restore", "resume"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="/sessions",
        short_desc="List saved sessions",
        long_desc="Display a list of all saved sessions with their names, dates, and sizes.",
        category=HelpCategory.SESSION,
        examples=["/sessions"],
        related=["/save", "/load"],
        keywords=["sessions", "list", "saved"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="/exit",
        short_desc="Exit Cortex",
        long_desc="Exit the Cortex CLI. You can also use Ctrl+D or Ctrl+C.",
        category=HelpCategory.SESSION,
        examples=["/exit"],
        keywords=["exit", "quit", "close"],
        beginner_friendly=True,
    ),
    # Context Commands
    HelpEntry(
        command="/summary",
        short_desc="Show conversation summary",
        long_desc="Display a summary of the current conversation, highlighting key topics discussed and actions taken.",
        category=HelpCategory.CONTEXT,
        examples=["/summary"],
        related=["/stats", "/memory"],
        keywords=["summary", "conversation", "overview"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="/plan",
        short_desc="Enter planning mode",
        long_desc="Switch to read-only planning mode for exploring code without making changes. Useful for analyzing code before modifications.",
        category=HelpCategory.CONTEXT,
        examples=["/plan"],
        related=["/mode"],
        keywords=["plan", "planning", "read-only", "explore"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="/reset-context",
        short_desc="Clear history, keep memory",
        long_desc="Clear the conversation history but preserve the memory bank. Useful for starting fresh while retaining learned information about the project.",
        category=HelpCategory.CONTEXT,
        examples=["/reset-context"],
        related=["/clear", "/memory"],
        keywords=["reset", "context", "memory", "clear"],
        beginner_friendly=False,
    ),
    HelpEntry(
        command="/focus",
        short_desc="Focus on a directory",
        long_desc="Tell the agent to prioritize a specific directory for future searches and operations. Helpful for large projects.",
        category=HelpCategory.CONTEXT,
        examples=["/focus src/components", "/focus backend/api"],
        keywords=["focus", "directory", "prioritize", "scope"],
        beginner_friendly=False,
    ),
    HelpEntry(
        command="/memory",
        short_desc="Show memory bank",
        long_desc="Display the contents of the memory bank, which stores facts and context learned during the session.",
        category=HelpCategory.CONTEXT,
        examples=["/memory"],
        related=["/stats", "/summary"],
        keywords=["memory", "facts", "context", "learned"],
        beginner_friendly=False,
    ),
    HelpEntry(
        command="/stats",
        short_desc="Show session statistics",
        long_desc="Display detailed statistics about the current session including message counts, token usage, tools used, and context management info.",
        category=HelpCategory.CONTEXT,
        examples=["/stats"],
        related=["/project", "/memory"],
        keywords=["stats", "statistics", "usage", "tokens"],
        beginner_friendly=True,
    ),
    # Display Commands
    HelpEntry(
        command="/thinking",
        short_desc="Toggle thinking display",
        long_desc="Toggle the display of the model's thinking/reasoning process. Some models like DeepSeek-R1 expose their reasoning steps.",
        category=HelpCategory.ADVANCED,
        examples=["/thinking", "/thinking on", "/thinking off"],
        keywords=["thinking", "reasoning", "display", "toggle"],
        beginner_friendly=False,
    ),
    HelpEntry(
        command="/storage",
        short_desc="Show storage statistics",
        long_desc="Display storage statistics for saved sessions, including total size and count limits.",
        category=HelpCategory.ADVANCED,
        examples=["/storage"],
        related=["/cleanup", "/sessions"],
        keywords=["storage", "disk", "space", "sessions"],
        beginner_friendly=False,
    ),
    HelpEntry(
        command="/cleanup",
        short_desc="Clean up old sessions",
        long_desc="Remove old sessions based on age, count, and size limits configured in settings.",
        category=HelpCategory.ADVANCED,
        examples=["/cleanup"],
        related=["/storage", "/sessions"],
        keywords=["cleanup", "delete", "sessions", "space"],
        beginner_friendly=False,
    ),
    HelpEntry(
        command="/cache",
        short_desc="Show or clear file cache",
        long_desc="Display file cache statistics including hit rate and memory usage. Use '/cache clear' to clear the cache.",
        category=HelpCategory.ADVANCED,
        examples=["/cache", "/cache clear"],
        keywords=["cache", "memory", "performance", "clear"],
        beginner_friendly=False,
    ),
    HelpEntry(
        command="/rollback",
        short_desc="Rollback file changes",
        long_desc="Rollback the current transaction, restoring all modified files to their original state. Works with active transactions only.",
        category=HelpCategory.ADVANCED,
        examples=["/rollback"],
        related=["/transactions"],
        keywords=["rollback", "undo", "restore", "revert"],
        beginner_friendly=False,
    ),
    HelpEntry(
        command="/transactions",
        short_desc="Show transaction info",
        long_desc="Display transaction statistics including active transaction status, history count, and backup directory.",
        category=HelpCategory.ADVANCED,
        examples=["/transactions"],
        related=["/rollback"],
        keywords=["transactions", "backup", "history"],
        beginner_friendly=False,
    ),
    # File Operations (these are natural language, not commands)
    HelpEntry(
        command="read file",
        short_desc="Read file contents",
        long_desc="Ask the agent to read a file. It will display the contents with syntax highlighting.",
        category=HelpCategory.FILE,
        examples=["Read the file src/main.py", "Show me config.yaml", "What's in package.json?"],
        keywords=["read", "file", "show", "display", "contents"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="write file",
        short_desc="Create or modify files",
        long_desc="Ask the agent to create a new file or modify an existing one. The agent will show you the changes before applying.",
        category=HelpCategory.FILE,
        examples=[
            "Create a new file called utils.py",
            "Add a function to helpers.js",
            "Update the README",
        ],
        keywords=["write", "create", "modify", "file", "new"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="edit file",
        short_desc="Make precise edits",
        long_desc="Make surgical edits to files by replacing specific strings. More precise than full file writes.",
        category=HelpCategory.FILE,
        examples=[
            "Change the function name from foo to bar",
            "Fix the typo in line 42",
            "Update the import statement",
        ],
        keywords=["edit", "change", "fix", "update", "replace"],
        beginner_friendly=True,
    ),
    # Search Operations
    HelpEntry(
        command="search files",
        short_desc="Search for patterns",
        long_desc="Search for text patterns across files using regex. Find definitions, usages, or any text patterns.",
        category=HelpCategory.SEARCH,
        examples=[
            "Search for 'class User'",
            "Find all TODO comments",
            "Where is the login function defined?",
        ],
        keywords=["search", "find", "grep", "pattern", "regex"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="list files",
        short_desc="List project files",
        long_desc="List files in a directory or find files matching patterns. Useful for exploring project structure.",
        category=HelpCategory.SEARCH,
        examples=[
            "List all Python files",
            "What files are in the src directory?",
            "Find all test files",
        ],
        keywords=["list", "files", "directory", "structure"],
        beginner_friendly=True,
    ),
    # Git Operations
    HelpEntry(
        command="git status",
        short_desc="Show git status",
        long_desc="Show the current git status including staged, modified, and untracked files.",
        category=HelpCategory.GIT,
        examples=["Show git status", "What files have changed?", "What's not committed?"],
        keywords=["git", "status", "changes", "staged"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="git diff",
        short_desc="Show changes",
        long_desc="Show the diff of changes for files. Can show all changes or changes to a specific file.",
        category=HelpCategory.GIT,
        examples=["Show the diff", "What changed in main.py?", "Show me what I modified"],
        keywords=["git", "diff", "changes", "compare"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="git commit",
        short_desc="Commit changes",
        long_desc="Commit staged changes with a message. The agent can help write a good commit message.",
        category=HelpCategory.GIT,
        examples=[
            "Commit these changes",
            "Create a commit for the auth fix",
            "Commit with message 'fix: resolve login bug'",
        ],
        keywords=["git", "commit", "save", "message"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="git log",
        short_desc="Show commit history",
        long_desc="Show recent commits with their messages and authors.",
        category=HelpCategory.GIT,
        examples=["Show recent commits", "What was the last commit?", "Show git history"],
        keywords=["git", "log", "history", "commits"],
        beginner_friendly=True,
    ),
    # Test Operations
    HelpEntry(
        command="run tests",
        short_desc="Run test suite",
        long_desc="Run the test suite using auto-detected test framework (pytest, unittest, etc).",
        category=HelpCategory.TEST,
        examples=["Run the tests", "Run tests for auth module", "Run pytest with verbose output"],
        keywords=["test", "tests", "pytest", "unittest", "run"],
        beginner_friendly=True,
        project_types=["python", "node", "javascript"],
    ),
    # Web Operations
    HelpEntry(
        command="web fetch",
        short_desc="Fetch web content",
        long_desc="Fetch content from a URL and convert it to readable markdown. Useful for reading documentation.",
        category=HelpCategory.WEB,
        examples=[
            "Fetch the React docs for hooks",
            "Get the content from https://example.com",
            "Read the API documentation",
        ],
        keywords=["web", "fetch", "url", "documentation", "http"],
        beginner_friendly=True,
    ),
    HelpEntry(
        command="web search",
        short_desc="Search the web",
        long_desc="Search the web for information using DuckDuckGo. Returns titles, URLs, and snippets.",
        category=HelpCategory.WEB,
        examples=[
            "Search for Python async best practices",
            "Find React hooks documentation",
            "Look up FastAPI tutorial",
        ],
        keywords=["web", "search", "google", "duckduckgo", "internet"],
        beginner_friendly=True,
    ),
    # Tool Reference Help
    HelpEntry(
        command="tool reference",
        short_desc="Complete tool reference guide",
        long_desc="""Detailed reference for all available tools in Cortex:

## File Discovery Tools
- `glob(pattern="**/*.py")` - Find files by glob pattern
- `list_files(path="src")` - Browse directory contents

## Content Search (grep)
- `grep(pattern="class.*Tool")` - Find which files match pattern (files_with_matches mode)
- `grep(pattern="def main", output_mode="content")` - Show matching lines
- `grep(pattern="TODO", output_mode="count")` - Count occurrences

## File Operations
- `read_file(path="main.py")` - Read and understand file contents
- `edit(file_path="x.py", old_string="a", new_string="b")` - Surgical string replacement
- `write_file(path="new.py", content="...")` - Create new file or full rewrite

## Execution Tools
- `execute_command(command="pip install x")` - Run shell commands
- `run_tests(pattern="test_auth.py")` - Run test suite

## Git Operations
- `git_add(files=["a.py", "b.py"])` - Stage changes for commit
- `git_commit(message="Initial commit")` - Commit staged changes
- `git_status()` - Show git status
- `git_diff(path="a.py")` - Show changes
- `git_log(limit=10)` - Show commit history
- `git_branch(action="create", branch_name="feat/new-thing")` - Manage branches
- `git_checkout(branch="feat/new-thing")` - Switch branches
- `git_push(remote="origin", branch="main")` - Push to remote

Use tools efficiently: Start with search (glob/grep) before reading, use edit for small changes, write_file for large changes.""",
        category=HelpCategory.ADVANCED,
        examples=[
            "What tools are available?",
            "How do I search for files?",
            "Show me all git commands",
        ],
        keywords=["tools", "reference", "commands", "git", "files", "search", "glob", "grep"],
        beginner_friendly=False,
    ),
    # Error Recovery Help
    HelpEntry(
        command="error recovery",
        short_desc="Error handling and recovery guidance",
        long_desc="""Guidance for handling tool errors and recovery strategies:

## When Tools Fail
- Check the `error_type` and `retryable` fields in error responses
- Permission errors (retryable: false) - Do NOT retry, permission denied
- Validation errors (retryable: true) - Fix input and retry
- Execution/timeout errors (retryable: true) - May retry once
- Not found errors (retryable: false) - Resource doesn't exist
- Security errors (retryable: false) - Safety violation, do NOT retry

## Common Error Scenarios
### File Not Found
1. Check exact spelling and case
2. Search for similar: `glob(pattern="**/*partial_name*")`
3. List parent directory: `list_files(path="parent_dir")`

### Command Failed
1. Read the exact error message
2. Check if dependencies are installed
3. Try a simpler version of the command
4. Consider platform differences (Windows vs Unix)

### Edit Failed (string not unique)
1. Include more context in old_string
2. Use `replace_all=True` if appropriate
3. Fall back to `write_file` for complex changes

## Recovery Patterns
- If stuck in a loop, try a different approach
- Ask user for clarification if requirements are ambiguous
- Use `/clear` to reset conversation if needed""",
        category=HelpCategory.ADVANCED,
        examples=[
            "How do I handle file not found errors?",
            "What does 'retryable: true' mean?",
            "The edit tool failed, what should I do?",
        ],
        keywords=["error", "recovery", "handling", "debug", "troubleshoot", "retry", "permission"],
        beginner_friendly=False,
    ),
    # CLI Commands Reference
    HelpEntry(
        command="cli commands",
        short_desc="Complete CLI command reference",
        long_desc="""All available CLI commands for Cortex:

## Session Management
- `/help` - Show available commands
- `/clear` - Clear conversation history
- `/mode [normal|auto|plan]` - Change permission mode
- `/project` - Show project info and settings
- `/save <name>` - Save current session
- `/load <name>` - Load saved session
- `/sessions` - List saved sessions
- `/exit` - Exit Cortex

## Context & Memory
- `/summary` - Show conversation summary
- `/plan` - Enter planning (read-only) mode
- `/reset-context` - Clear history, keep memory
- `/focus <path>` - Set focus directory
- `/memory` - Show memory bank contents
- `/stats` - Show session statistics

## Display & Configuration
- `/thinking [on|off]` - Toggle thinking process display
- `/storage` - Show storage statistics
- `/cleanup` - Clean up old sessions
- `/cache` - Show or clear file cache

## Advanced Features
- `/rollback` - Rollback file changes
- `/transactions` - Show transaction info
- `/model <model_name>` - Switch LLM model

## Usage Tips
- Use `/help <topic>` for detailed help on any topic
- Use `/help search <query>` to search all help content
- Use `/help categories` to browse by category""",
        category=HelpCategory.ADVANCED,
        examples=[
            "What commands are available?",
            "How do I save my session?",
            "Show me all session commands",
        ],
        keywords=["cli", "commands", "reference", "session", "context", "mode", "save", "load"],
        beginner_friendly=True,
    ),
]


def get_help_entries_by_category(category: HelpCategory) -> List[HelpEntry]:
    """Get all help entries for a specific category."""
    return [e for e in HELP_ENTRIES if e.category == category]


def get_beginner_entries() -> List[HelpEntry]:
    """Get beginner-friendly help entries."""
    return [e for e in HELP_ENTRIES if e.beginner_friendly]


def get_entry_by_command(command: str) -> Optional[HelpEntry]:
    """Get a help entry by command name."""
    command = command.lower().strip()
    if command.startswith("/"):
        command = command[1:]

    for entry in HELP_ENTRIES:
        entry_cmd = entry.command.lower().strip()
        if entry_cmd.startswith("/"):
            entry_cmd = entry_cmd[1:]
        if entry_cmd == command:
            return entry
    return None
