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
    from ..agent import LocalAgent

logger = logging.getLogger(__name__)

# Tool schema for registration
TASK_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "task",
        "description": (
            "Delegate a complex subtask to a focused subagent. Use this when a task "
            "requires multiple steps, focused investigation, or would benefit from "
            "isolated context. The subagent will work independently and return results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Clear, specific description of the subtask to accomplish"
                },
                "allowed_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of tools the subagent can use. Defaults to read-only tools: "
                        "['read_file', 'list_files', 'search_files']"
                    )
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum iterations for the subagent (default: 10)"
                },
                "context": {
                    "type": "string",
                    "description": "Additional context to provide to the subagent"
                }
            },
            "required": ["description"]
        }
    }
}


class TaskTool(Tool):
    """
    Tool for spawning subagents to handle complex tasks.

    Subagents run with isolated context, allowing them to focus on
    specific tasks without polluting the main conversation.
    """

    def __init__(
        self,
        project_dir: Path,
        permission_mode: str,
        console,
        parent_agent: Optional["LocalAgent"] = None,
    ):
        """
        Initialize TaskTool.

        Args:
            project_dir: Project directory path
            permission_mode: Permission mode string
            console: Console for output
            parent_agent: Reference to the parent agent (optional)
        """
        super().__init__(project_dir, permission_mode, console)
        self.parent_agent = parent_agent
        self.active_tasks: Dict[str, SubagentContext] = {}

    def execute(
        self,
        description: str,
        allowed_tools: Optional[List[str]] = None,
        max_iterations: int = 10,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Spawn a subagent to handle a task.

        Args:
            description: Task description for the subagent
            allowed_tools: List of tools the subagent can use
            max_iterations: Maximum iterations for the subagent
            context: Additional context to provide

        Returns:
            Result dictionary with task outcome
        """
        # Generate task ID
        task_id = str(uuid.uuid4())[:8]

        if self.console:
            self.console.print(f"[cyan]Starting subtask:[/cyan] {task_id}")
            self.console.print(f"[dim]{description[:100]}...[/dim]" if len(description) > 100 else f"[dim]{description}[/dim]")

        # Set default allowed tools (read-only by default)
        if allowed_tools is None:
            allowed_tools = ["read_file", "list_files", "search_files"]

        # Create subagent context
        subagent_context = SubagentContext(
            task_id=task_id,
            task_description=description,
            parent_context={
                "project_dir": str(self.project_dir),
                "permission_mode": self.permission_mode,
                "additional_context": context,
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

            return create_success_response({
                "task_id": task_id,
                "result": result.get("final_response", ""),
                "iterations_used": subagent_context.iterations_used,
                "tools_called": subagent_context.tools_called,
                "duration_seconds": subagent_context.duration_seconds,
            })

        except Exception as e:
            logger.error(f"Subtask {task_id} failed: {e}")
            subagent_context.fail(str(e))

            if self.console:
                self.console.print(f"[red]Subtask {task_id} failed:[/red] {e}")

            return create_error_response(
                f"Subtask failed: {e}",
                ErrorType.EXECUTION,
                {"task_id": task_id}
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
        from ..agent import LocalAgent
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
        subagent = LocalAgent(
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
        context.iterations_used = len([
            m for m in context.conversation_history
            if m.get("role") == "assistant"
        ])
        context.tools_called = subagent._tools_used.copy()

        # Extract final response
        final_messages = [
            msg for msg in context.conversation_history
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
        Generate focused system prompt for subagent.

        Args:
            context: SubagentContext with task details

        Returns:
            System prompt string
        """
        tools_list = ", ".join(context.allowed_tools)
        additional_context = context.parent_context.get("additional_context", "")

        return f"""You are a focused task agent working on a specific subtask.

## Your Task
{context.task_description}

## Additional Context
{additional_context if additional_context else "No additional context provided."}

## Working Directory
{context.working_directory}

## Available Tools
You have access to these tools: {tools_list}

## Guidelines

1. **Focus**: Work ONLY on the assigned task. Do not explore beyond what's needed.
2. **Efficiency**: Complete the task in as few steps as possible.
3. **Clarity**: Provide clear, concise findings in your final response.
4. **Scope**: Do not go beyond the scope of the task.
5. **Completion**: When done, provide a summary of your findings or results.

## Output Format

When you complete the task, provide:
1. A brief summary of what you found or accomplished
2. Key findings or results
3. Any relevant code snippets or file references

Remember: You are a focused agent. Complete the task and report back."""

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
