"""Todo tracking tool for task management during sessions."""

import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from .base import Tool
from ..models import PermissionMode
from ..utils.errors import ErrorType, create_error_response, create_success_response

logger = logging.getLogger(__name__)


class TodoStatus(Enum):
    """Status of a todo item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class TodoItem:
    """A single todo item."""

    content: str
    status: TodoStatus
    active_form: str  # Present continuous form (e.g., "Running tests")
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "content": self.content,
            "status": self.status.value,
            "activeForm": self.active_form,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TodoItem":
        """Create from dictionary format."""
        return cls(
            content=data["content"],
            status=TodoStatus(data["status"]),
            active_form=data.get("activeForm", data["content"]),
        )


class TodoManager:
    """
    Manages the todo list for a session.

    Features:
    - Track tasks with status (pending, in_progress, completed)
    - Display callback for UI updates
    - Progress statistics
    - Only one task can be in_progress at a time
    """

    def __init__(self, display_callback: Optional[Callable[[List[TodoItem]], None]] = None):
        self.todos: List[TodoItem] = []
        self._display_callback = display_callback

    def set_display_callback(self, callback: Callable[[List[TodoItem]], None]) -> None:
        """Set callback for displaying todo updates."""
        self._display_callback = callback

    def update(self, todos_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update the entire todo list.

        Args:
            todos_data: List of todo items with content, status, activeForm

        Returns:
            Dict with success status and validation errors if any
        """
        # Validate: only one in_progress at a time
        in_progress_count = sum(1 for t in todos_data if t.get("status") == "in_progress")
        if in_progress_count > 1:
            return create_error_response(
                "Only one task can be in_progress at a time",
                ErrorType.VALIDATION,
                context={"in_progress_count": in_progress_count},
            )

        new_todos = []
        for item in todos_data:
            try:
                status = TodoStatus(item["status"])
            except (ValueError, KeyError):
                return create_error_response(
                    f"Invalid status: {item.get('status')}. Must be pending, in_progress, or completed",
                    ErrorType.VALIDATION,
                    context={"invalid_status": item.get("status")},
                )

            # Find existing item to preserve timestamps
            existing = self._find_by_content(item["content"])

            if existing:
                todo = TodoItem(
                    content=item["content"],
                    status=status,
                    active_form=item.get("activeForm", item["content"]),
                    created_at=existing.created_at,
                )
                # Mark completion time if newly completed
                if status == TodoStatus.COMPLETED and existing.status != TodoStatus.COMPLETED:
                    todo.completed_at = datetime.now()
                elif existing.completed_at:
                    todo.completed_at = existing.completed_at
            else:
                todo = TodoItem(
                    content=item["content"],
                    status=status,
                    active_form=item.get("activeForm", item["content"]),
                )
                if status == TodoStatus.COMPLETED:
                    todo.completed_at = datetime.now()

            new_todos.append(todo)

        self.todos = new_todos
        self._display()

        return create_success_response({})

    def _find_by_content(self, content: str) -> Optional[TodoItem]:
        """Find existing todo by content."""
        for todo in self.todos:
            if todo.content == content:
                return todo
        return None

    def _display(self) -> None:
        """Display current todo state via callback."""
        if self._display_callback:
            try:
                self._display_callback(self.todos)
            except Exception as e:
                logger.warning(f"Todo display callback error: {e}")

    def get_current_task(self) -> Optional[TodoItem]:
        """Get the currently in-progress task."""
        for todo in self.todos:
            if todo.status == TodoStatus.IN_PROGRESS:
                return todo
        return None

    def get_progress(self) -> Dict[str, int]:
        """Get progress statistics."""
        return {
            "total": len(self.todos),
            "pending": sum(1 for t in self.todos if t.status == TodoStatus.PENDING),
            "in_progress": sum(1 for t in self.todos if t.status == TodoStatus.IN_PROGRESS),
            "completed": sum(1 for t in self.todos if t.status == TodoStatus.COMPLETED),
        }

    def get_todos_as_dicts(self) -> List[Dict[str, Any]]:
        """Get all todos as list of dicts."""
        return [todo.to_dict() for todo in self.todos]

    def clear(self) -> None:
        """Clear all todos."""
        self.todos = []
        self._display()


# Global todo manager instance (will be set by agent)
_todo_manager: Optional[TodoManager] = None


def get_todo_manager() -> Optional[TodoManager]:
    """Get the global todo manager."""
    return _todo_manager


def set_todo_manager(manager: TodoManager) -> None:
    """Set the global todo manager."""
    global _todo_manager
    _todo_manager = manager


class TodoWriteTool(Tool):
    """
    Tool for managing task lists during a session.

    The agent uses this to:
    - Plan complex multi-step tasks
    - Track progress on each step
    - Give users visibility into what's happening

    Rules:
    - Only ONE task can be in_progress at a time
    - Tasks should be marked completed immediately after finishing
    - Use imperative form for content ("Run tests")
    - Use present continuous for activeForm ("Running tests")
    """

    default_timeout = 5  # Quick operation

    def __init__(
        self,
        project_dir: Path,
        permission_mode: str = PermissionMode.NORMAL,
        console=None,
        timeout_config=None,
        todo_manager: Optional[TodoManager] = None,
    ):
        super().__init__(project_dir, permission_mode, console, timeout_config)
        self.todo_manager = todo_manager or get_todo_manager()

    def execute(self, todos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update the todo list.

        Args:
            todos: List of todo items, each with:
                - content: Task description (imperative form)
                - status: "pending" | "in_progress" | "completed"
                - activeForm: Present continuous form for display

        Returns:
            Dict with success status, progress stats, and current task
        """
        if not self.todo_manager:
            # Create a default manager if none exists
            self.todo_manager = TodoManager()
            set_todo_manager(self.todo_manager)
            if self.console:
                self.todo_manager.set_display_callback(
                    lambda todos: display_todos(todos, self.console)
                )

        # Update todos
        result = self.todo_manager.update(todos)

        if not result.get("success", False):
            return result

        # Get progress info
        progress = self.todo_manager.get_progress()
        current = self.todo_manager.get_current_task()

        return create_success_response(
            {
                "progress": progress,
                "current_task": current.active_form if current else None,
                "message": f"Todo list updated: {progress['completed']}/{progress['total']} completed",
            }
        )


def display_todos(todos: List[TodoItem], console) -> None:
    """
    Display todo list in terminal using Rich.

    Args:
        todos: List of TodoItem objects
        console: Rich console instance
    """
    if not todos:
        return

    from rich.table import Table
    from rich.panel import Panel

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Status", width=3)
    table.add_column("Task")

    status_icons = {
        TodoStatus.PENDING: "[dim]\u25cb[/dim]",  # ○
        TodoStatus.IN_PROGRESS: "[cyan]\u25d0[/cyan]",  # ◐
        TodoStatus.COMPLETED: "[green]\u25cf[/green]",  # ●
    }

    for todo in todos:
        icon = status_icons.get(todo.status, "[dim]?[/dim]")

        if todo.status == TodoStatus.IN_PROGRESS:
            text = f"[cyan]{todo.active_form}[/cyan]"
        elif todo.status == TodoStatus.COMPLETED:
            text = f"[dim strikethrough]{todo.content}[/dim strikethrough]"
        else:
            text = f"[white]{todo.content}[/white]"

        table.add_row(icon, text)

    # Calculate progress
    completed = sum(1 for t in todos if t.status == TodoStatus.COMPLETED)
    total = len(todos)

    panel = Panel(table, title=f"[bold]Tasks ({completed}/{total})[/bold]", border_style="dim")

    console.print(panel)


# Tool schema for function calling
TODO_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "todo_write",
        "description": "Manage and track tasks for the current session. Use this to plan complex multi-step tasks and track progress. Only use when working on tasks with 3+ steps. Mark tasks as in_progress BEFORE starting work, and completed IMMEDIATELY after finishing. Only ONE task can be in_progress at a time.",
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "The complete updated todo list",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Task description (imperative form, e.g., 'Run tests')",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "Current status of the task",
                            },
                            "activeForm": {
                                "type": "string",
                                "description": "Present continuous form (e.g., 'Running tests')",
                            },
                        },
                        "required": ["content", "status", "activeForm"],
                    },
                }
            },
            "required": ["todos"],
        },
    },
}
