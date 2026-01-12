"""Task tool for delegating work to subagents"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from pathlib import Path
import uuid
import logging

from ..tools.base import Tool
from ..models import PermissionMode
from ..utils.errors import create_error_response, create_success_response, ErrorType
from .context import SubagentContext

if TYPE_CHECKING:
    from ..agent import Cortex
    from ..utils.timeouts import TimeoutConfig

logger = logging.getLogger(__name__)

# Agent type configurations
AGENT_TYPES = {
    "explore": {
        "description": "Codebase exploration and understanding",
        "default_tools": ["read_file", "list_files", "grep", "glob"],
        "max_iterations": 15,
    },
    "search": {
        "description": "Find specific code or patterns",
        "default_tools": ["grep", "glob", "read_file"],
        "max_iterations": 10,
    },
    "analyze": {
        "description": "Analyze code structure and relationships",
        "default_tools": ["read_file", "grep", "glob", "list_files"],
        "max_iterations": 12,
    },
    "general": {
        "description": "General purpose subtask",
        "default_tools": ["read_file", "list_files", "grep", "glob"],
        "max_iterations": 10,
    },
}

# Tool schema for registration
TASK_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "task",
        "description": (
            "Delegate a task to a specialized subagent. Use for complex multi-step tasks, "
            "codebase exploration, or focused investigation. The subagent works independently "
            "and returns results. Use agent_type='explore' for understanding codebases."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Clear, specific description of the subtask to accomplish",
                },
                "agent_type": {
                    "type": "string",
                    "enum": ["explore", "search", "analyze", "general"],
                    "description": (
                        "Type of agent: 'explore' for codebase understanding, "
                        "'search' for finding code, 'analyze' for code analysis, "
                        "'general' for other tasks. Default: 'general'"
                    ),
                },
                "allowed_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Override default tools. If not specified, uses agent_type defaults. "
                        "Available: read_file, list_files, grep, glob, git_status, git_log"
                    ),
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum iterations (default varies by agent_type)",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context to provide to the subagent",
                },
            },
            "required": ["description"],
        },
    },
}


class TaskTool(Tool):
    """
    Tool for spawning subagents to handle complex tasks.

    Subagents run with isolated context, allowing them to focus on
    specific tasks without polluting the main conversation.

    Supports specialized agent types:
    - explore: For understanding codebases
    - search: For finding specific code/patterns
    - analyze: For code analysis
    - general: For general tasks
    """

    def __init__(
        self,
        project_dir: Path,
        permission_mode: str,
        console,
        parent_agent: Optional["Cortex"] = None,
        timeout_config: Optional["TimeoutConfig"] = None,
    ):
        """
        Initialize TaskTool.

        Args:
            project_dir: Project directory path
            permission_mode: Permission mode string
            console: Console for output
            parent_agent: Reference to the parent agent (optional)
            timeout_config: Timeout configuration (optional)
        """
        super().__init__(project_dir, permission_mode, console, timeout_config)
        self.parent_agent = parent_agent
        self.active_tasks: Dict[str, SubagentContext] = {}

    def execute(
        self,
        description: str,
        agent_type: str = "general",
        allowed_tools: Optional[List[str]] = None,
        max_iterations: Optional[int] = None,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Spawn a subagent to handle a task.

        Args:
            description: Task description for the subagent
            agent_type: Type of agent (explore, search, analyze, general)
            allowed_tools: Override default tools for the agent type
            max_iterations: Override default max iterations
            context: Additional context to provide

        Returns:
            Result dictionary with task outcome
        """
        # Validate agent type
        if agent_type not in AGENT_TYPES:
            agent_type = "general"

        agent_config = AGENT_TYPES[agent_type]

        # Generate task ID
        task_id = str(uuid.uuid4())[:8]

        if self.console:
            self.console.print(f"[cyan]Starting {agent_type} task:[/cyan] {task_id}")
            self.console.print(
                f"[dim]{description[:100]}...[/dim]"
                if len(description) > 100
                else f"[dim]{description}[/dim]"
            )

        # Use agent type defaults, allow overrides
        if allowed_tools is None:
            allowed_tools = agent_config["default_tools"]
        if max_iterations is None:
            max_iterations = agent_config["max_iterations"]

        # Create subagent context
        subagent_context = SubagentContext(
            task_id=task_id,
            task_description=description,
            parent_context={
                "project_dir": str(self.project_dir),
                "permission_mode": self.permission_mode,
                "additional_context": context,
                "agent_type": agent_type,
            },
            allowed_tools=allowed_tools,
            max_iterations=max_iterations,
            working_directory=self.project_dir,
        )

        # Track active task
        self.active_tasks[task_id] = subagent_context

        try:
            # Start execution
            subagent_context.start()

            # Create and run subagent
            result = self._run_subagent(subagent_context)

            # Mark as complete
            subagent_context.complete(result)

            if self.console:
                self.console.print(f"[green]Subtask {task_id} completed[/green]")

            return create_success_response(
                {
                    "task_id": task_id,
                    "result": result.get("final_response", ""),
                    "iterations_used": subagent_context.iterations_used,
                    "tools_called": subagent_context.tools_called,
                    "duration_seconds": subagent_context.duration_seconds,
                }
            )

        except Exception as e:
            logger.error(f"Subtask {task_id} failed: {e}")
            subagent_context.fail(str(e))

            if self.console:
                self.console.print(f"[red]Subtask {task_id} failed:[/red] {e}")

            return create_error_response(
                f"Subtask failed: {e}", ErrorType.EXECUTION, {"task_id": task_id}
            )

        finally:
            # Clean up
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]

    def _run_subagent(self, context: SubagentContext) -> Dict[str, Any]:
        """
        Run a subagent with the given context.

        Args:
            context: SubagentContext with task details

        Returns:
            Result dictionary from subagent execution
        """
        # Import here to avoid circular imports
        from ..agent import Cortex
        from ..config import AgentConfig
        from ..hooks import HookManager, PermissionHook

        # Create restricted config for subagent
        subagent_config = AgentConfig(
            max_iterations=context.max_iterations,
            max_tokens=50000,  # Smaller context for subagents
        )

        # Determine model - use parent's model if available
        model = "llama3.2"
        if self.parent_agent:
            model = self.parent_agent.model

        # Create hook manager with tool restrictions
        subagent_hooks = HookManager()

        # Add PermissionHook to enforce allowed_tools whitelist
        # This ensures the subagent can ONLY use tools in allowed_tools list
        permission_hook = PermissionHook(allowed=context.allowed_tools)
        subagent_hooks.register(permission_hook)

        logger.debug(f"Subagent tools restricted to: {context.allowed_tools}")

        # Create subagent with isolated context
        # Use PLAN mode by default for safety (read-only)
        subagent = Cortex(
            model=model,
            project_dir=str(context.working_directory or self.project_dir),
            permission_mode=PermissionMode.PLAN,
            config=subagent_config,
            hook_manager=subagent_hooks,  # Hook manager with tool restrictions
        )

        # Override system prompt for focused task
        subagent.conversation.history[0]["content"] = self._get_subagent_prompt(context)

        # Process the task
        # Note: We're calling _process_message directly which populates conversation
        subagent._process_message(context.task_description)

        # Collect results
        context.conversation_history = subagent.get_conversation_history()
        context.iterations_used = len(
            [m for m in context.conversation_history if m.get("role") == "assistant"]
        )
        context.tools_called = subagent._tools_used.copy()

        # Extract final response
        final_messages = [
            msg
            for msg in context.conversation_history
            if msg.get("role") == "assistant" and msg.get("content")
        ]

        final_response = ""
        if final_messages:
            final_response = final_messages[-1].get("content", "")

        return {
            "final_response": final_response,
            "messages_count": len(context.conversation_history),
        }

    def _get_subagent_prompt(self, context: SubagentContext) -> str:
        """
        Generate focused system prompt for subagent based on agent type.

        Args:
            context: SubagentContext with task details

        Returns:
            System prompt string
        """
        tools_list = ", ".join(context.allowed_tools)
        additional_context = context.parent_context.get("additional_context", "")
        agent_type = context.parent_context.get("agent_type", "general")

        # Base prompt
        base = f"""You are a specialized {agent_type} agent working in: {context.working_directory}

## Your Task
{context.task_description}

{f"## Additional Context{chr(10)}{additional_context}" if additional_context else ""}

## Available Tools
{tools_list}
"""

        # Agent-type specific instructions
        if agent_type == "explore":
            return (
                base
                + """
## Exploration Strategy

You are exploring a codebase to understand its structure and answer questions.

### Steps to Follow

1. **Start with structure** - Use `glob(pattern="**/*.py")` to find all source files
2. **Identify key files** - Look for main.py, app.py, index.py, __init__.py, etc.
3. **Search for patterns** - Use `grep` to find classes, functions, imports
4. **Read relevant files** - Once you find relevant files, read them for details
5. **Summarize findings** - Provide clear, organized findings

### Tool Usage Tips

```
glob(pattern="**/*.py")                    # Find all Python files
glob(pattern="src/**/*.ts")                # TypeScript in src/
grep(pattern="class.*Service")             # Find service classes
grep(pattern="def main", file_type="py")   # Find main functions
read_file(path="found_file.py")            # Read specific files
```

### Output Format

Provide a structured summary:
1. **Overview**: What the codebase/component does
2. **Key Files**: Important files and their purposes
3. **Architecture**: How components relate
4. **Findings**: Direct answers to any questions asked

Be thorough but concise. Reference files with `file.py:line` format."""
            )

        elif agent_type == "search":
            return (
                base
                + """
## Search Strategy

You are searching for specific code patterns or definitions.

### Steps to Follow

1. **Direct search first** - Use `grep` with the exact pattern
2. **Broaden if needed** - Try variations or regex patterns
3. **Read matches** - Read files that match to verify findings
4. **Report locations** - Provide file paths and line numbers

### Tool Usage Tips

```
grep(pattern="def function_name")          # Find function definitions
grep(pattern="class ClassName")            # Find class definitions
grep(pattern="pattern", output_mode="content")  # Show matching lines
```

### Output Format

Report findings as:
- **Found in**: file.py:42
- **Context**: Brief description of what's there
- List all relevant matches"""
            )

        elif agent_type == "analyze":
            return (
                base
                + """
## Analysis Strategy

You are analyzing code structure, relationships, and patterns.

### Steps to Follow

1. **Map dependencies** - Find imports and relationships
2. **Identify patterns** - Look for design patterns, code organization
3. **Check for issues** - Look for potential problems if relevant
4. **Summarize structure** - Provide clear architectural overview

### Tool Usage Tips

```
grep(pattern="^import|^from", file_type="py")  # Find all imports
grep(pattern="class.*\\(.*\\):")               # Find class inheritance
read_file(path="file.py")                      # Detailed analysis
```

### Output Format

Provide:
1. **Structure Overview**: How code is organized
2. **Dependencies**: Key imports and relationships
3. **Patterns**: Design patterns used
4. **Observations**: Notable findings or concerns"""
            )

        else:  # general
            return (
                base
                + """
## Guidelines

1. **Focus**: Work ONLY on the assigned task
2. **Efficiency**: Complete in as few steps as possible
3. **Clarity**: Provide clear, concise findings
4. **Completion**: Summarize when done

### Output Format

1. Brief summary of what you found/accomplished
2. Key findings or results
3. Relevant code snippets or file references"""
            )

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a task by ID.

        Args:
            task_id: Task ID to check

        Returns:
            Task status dictionary, or None if not found
        """
        if task_id in self.active_tasks:
            return self.active_tasks[task_id].to_dict()
        return None

    def list_active_tasks(self) -> List[str]:
        """
        List all active task IDs.

        Returns:
            List of active task IDs
        """
        return list(self.active_tasks.keys())
