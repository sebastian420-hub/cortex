"""Subagent context management"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime


@dataclass
class SubagentContext:
    """
    Isolated context for a subagent.

    Contains all information needed to run a focused subtask,
    including task description, constraints, and results.
    """

    # Task identification
    task_id: str
    task_description: str

    # Parent context (what the parent agent knows)
    parent_context: Dict[str, Any] = field(default_factory=dict)

    # Constraints
    allowed_tools: List[str] = field(default_factory=lambda: [
        "read_file", "list_files", "search_files"
    ])
    max_iterations: int = 10
    timeout_seconds: int = 300
    working_directory: Optional[Path] = None

    # Execution state
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed: bool = False

    # Results
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)

    # Metrics
    iterations_used: int = 0
    tools_called: List[str] = field(default_factory=list)

    def start(self) -> None:
        """Mark the subagent as started."""
        self.started_at = datetime.now()

    def complete(self, result: Dict[str, Any]) -> None:
        """Mark the subagent as completed with result."""
        self.completed = True
        self.completed_at = datetime.now()
        self.result = result

    def fail(self, error: str) -> None:
        """Mark the subagent as failed with error."""
        self.completed = True
        self.completed_at = datetime.now()
        self.error = error

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "allowed_tools": self.allowed_tools,
            "max_iterations": self.max_iterations,
            "completed": self.completed,
            "result": self.result,
            "error": self.error,
            "iterations_used": self.iterations_used,
            "tools_called": self.tools_called,
            "duration_seconds": self.duration_seconds,
        }
