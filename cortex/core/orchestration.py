"""
Orchestration System for Self-Orchestrating Multi-Model System.

This module provides:
- DelegationTracker: Prevents infinite delegation loops
- DelegationContext: Context passed during model handoffs
- OrchestrationManager: Coordinates model switching
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Default maximum delegations per user request
MAX_DELEGATIONS_PER_REQUEST = 5


@dataclass
class DelegationRecord:
    """Record of a single delegation event."""
    from_model: str
    to_model: str
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)
    delegation_number: int = 0


class DelegationTracker:
    """
    Tracks delegations to prevent infinite loops.

    Enforces a maximum number of delegations per user request.
    When the quota is exhausted, the current model must complete
    the task without further delegation.
    """

    def __init__(self, max_delegations: int = MAX_DELEGATIONS_PER_REQUEST):
        """
        Initialize the tracker.

        Args:
            max_delegations: Maximum allowed delegations per request
        """
        self.max_delegations = max_delegations
        self.delegation_count = 0
        self.delegation_history: List[DelegationRecord] = []
        self._started_at = datetime.now()

    def can_delegate(self) -> bool:
        """Check if delegation is still allowed."""
        return self.delegation_count < self.max_delegations

    def record_delegation(self, from_model: str, to_model: str, reason: str) -> DelegationRecord:
        """
        Record a delegation event.

        Args:
            from_model: Model that is delegating
            to_model: Model receiving the delegation
            reason: Why delegation is happening

        Returns:
            The created DelegationRecord
        """
        self.delegation_count += 1
        record = DelegationRecord(
            from_model=from_model,
            to_model=to_model,
            reason=reason,
            delegation_number=self.delegation_count,
        )
        self.delegation_history.append(record)

        logger.info(
            f"Delegation {self.delegation_count}/{self.max_delegations}: "
            f"{from_model} -> {to_model} ({reason})"
        )

        return record

    def get_remaining(self) -> int:
        """Get remaining delegation quota."""
        return max(0, self.max_delegations - self.delegation_count)

    def get_history(self) -> List[DelegationRecord]:
        """Get delegation history."""
        return self.delegation_history.copy()

    def get_summary(self) -> str:
        """Get a human-readable summary of delegations."""
        if not self.delegation_history:
            return "No delegations in this request."

        lines = [
            f"Delegations: {self.delegation_count}/{self.max_delegations}",
            "",
        ]

        for record in self.delegation_history:
            lines.append(
                f"  {record.delegation_number}. {record.from_model} -> {record.to_model}"
            )
            lines.append(f"     Reason: {record.reason[:50]}...")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset the tracker for a new request."""
        self.delegation_count = 0
        self.delegation_history = []
        self._started_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "max_delegations": self.max_delegations,
            "delegation_count": self.delegation_count,
            "remaining": self.get_remaining(),
            "history": [
                {
                    "from": r.from_model,
                    "to": r.to_model,
                    "reason": r.reason,
                    "number": r.delegation_number,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in self.delegation_history
            ],
        }


@dataclass
class DelegationContext:
    """
    Context passed when delegating to another model.

    Contains everything the receiving model needs to continue the work.
    """
    from_model: str
    to_model: str
    task: str
    handoff_notes: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    state_summary: Dict[str, Any] = field(default_factory=dict)
    delegation_tracker: Optional[DelegationTracker] = None

    def get_remaining_delegations(self) -> int:
        """Get remaining delegation quota."""
        if self.delegation_tracker:
            return self.delegation_tracker.get_remaining()
        return MAX_DELEGATIONS_PER_REQUEST

    def to_system_context(self) -> str:
        """
        Generate system prompt context for the receiving model.

        This is injected into the model's system prompt to inform it
        about the delegation context.
        """
        sections = [
            "## Delegation Context",
            "",
            f"You were delegated this task by: **{self.from_model}**",
            "",
            "### Your Task",
            "",
            self.task,
            "",
        ]

        if self.handoff_notes:
            sections.extend([
                "### Handoff Notes",
                "",
                self.handoff_notes,
                "",
            ])

        files_read = self.state_summary.get("files_read", [])
        if files_read:
            sections.extend([
                "### Files Already Examined",
                "",
            ])
            for f in files_read[:10]:
                sections.append(f"- `{f}`")
            if len(files_read) > 10:
                sections.append(f"- ... and {len(files_read) - 10} more")
            sections.append("")

        decisions = self.state_summary.get("decisions", [])
        if decisions:
            sections.extend([
                "### Decisions Made",
                "",
            ])
            for d in decisions:
                sections.append(f"- {d}")
            sections.append("")

        remaining = self.get_remaining_delegations()
        sections.extend([
            "### Delegation Quota",
            "",
            f"**Remaining delegations:** {remaining}",
            "",
        ])

        if remaining <= 2:
            sections.append(
                "**Warning:** Delegation quota is low. Consider completing the task "
                "yourself rather than delegating further."
            )
        elif remaining == 0:
            sections.append(
                "**Quota exhausted:** You must complete this task yourself. "
                "No further delegation is possible."
            )

        return "\n".join(sections)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "from_model": self.from_model,
            "to_model": self.to_model,
            "task": self.task,
            "handoff_notes": self.handoff_notes,
            "state_summary": self.state_summary,
            "remaining_delegations": self.get_remaining_delegations(),
        }


class OrchestrationManager:
    """
    Manages model orchestration and delegation.

    Coordinates:
    - Model switching during delegation
    - Context preservation across handoffs
    - Delegation tracking and limits
    """

    def __init__(
        self,
        default_coordinator: str = "xiaomi/mimo-v2-flash:free",
        max_delegations: int = MAX_DELEGATIONS_PER_REQUEST,
    ):
        """
        Initialize the orchestration manager.

        Args:
            default_coordinator: Default coordinator model
            max_delegations: Max delegations per request
        """
        self.default_coordinator = default_coordinator
        self.max_delegations = max_delegations
        self.current_model: Optional[str] = None
        self.tracker: Optional[DelegationTracker] = None
        self._delegation_context: Optional[DelegationContext] = None

    def start_request(self, initial_model: Optional[str] = None) -> DelegationTracker:
        """
        Start tracking a new user request.

        Args:
            initial_model: Initial model handling the request

        Returns:
            New DelegationTracker for this request
        """
        self.current_model = initial_model or self.default_coordinator
        self.tracker = DelegationTracker(self.max_delegations)
        self._delegation_context = None
        return self.tracker

    def prepare_delegation(
        self,
        to_model: str,
        task: str,
        handoff_notes: str,
        conversation_history: List[Dict[str, Any]],
        state_summary: Optional[Dict[str, Any]] = None,
    ) -> DelegationContext:
        """
        Prepare context for delegation.

        Args:
            to_model: Target model
            task: Task description
            handoff_notes: Notes from delegating model
            conversation_history: Full conversation history
            state_summary: Summary of current state

        Returns:
            DelegationContext to pass to target model
        """
        context = DelegationContext(
            from_model=self.current_model or self.default_coordinator,
            to_model=to_model,
            task=task,
            handoff_notes=handoff_notes,
            conversation_history=conversation_history,
            state_summary=state_summary or {},
            delegation_tracker=self.tracker,
        )

        self._delegation_context = context
        self.current_model = to_model

        return context

    def get_delegation_context(self) -> Optional[DelegationContext]:
        """Get the current delegation context."""
        return self._delegation_context

    def clear_delegation_context(self) -> None:
        """Clear the delegation context after it's been used."""
        self._delegation_context = None

    def get_tracker(self) -> Optional[DelegationTracker]:
        """Get the current delegation tracker."""
        return self.tracker

    def finish_request(self) -> Dict[str, Any]:
        """
        Finish tracking the current request.

        Returns:
            Summary of the request's delegations
        """
        summary = {
            "total_delegations": self.tracker.delegation_count if self.tracker else 0,
            "history": self.tracker.get_history() if self.tracker else [],
            "final_model": self.current_model,
        }

        # Don't reset here - let the caller decide when to reset
        return summary

    def get_status(self) -> Dict[str, Any]:
        """Get current orchestration status."""
        return {
            "current_model": self.current_model,
            "coordinator": self.default_coordinator,
            "tracker": self.tracker.to_dict() if self.tracker else None,
            "has_delegation_context": self._delegation_context is not None,
        }


# Global orchestration manager instance
_orchestration_manager: Optional[OrchestrationManager] = None


def get_orchestration_manager() -> OrchestrationManager:
    """Get or create the global orchestration manager."""
    global _orchestration_manager
    if _orchestration_manager is None:
        _orchestration_manager = OrchestrationManager()
    return _orchestration_manager


def reset_orchestration_manager() -> None:
    """Reset the global orchestration manager (for testing)."""
    global _orchestration_manager
    _orchestration_manager = None
