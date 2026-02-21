"""
Delegation Tools for Self-Orchestrating Multi-Model System.

These tools allow models to delegate work to specialist models and return
control to the coordinator.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

from .base import Tool
from ..models import PermissionMode

logger = logging.getLogger(__name__)


class DelegateToModelTool(Tool):
    """
    Tool for delegating work to a specialist model.

    When executed, this tool signals the agent to switch to a different model
    while preserving context and conversation history.
    """

    default_timeout = 5  # Quick operation - just signals delegation
    timeout_category = "delegation"

    def __init__(
        self,
        project_dir: Path,
        permission_mode: str = PermissionMode.NORMAL,
        console=None,
        delegation_tracker=None,
        model_registry=None,
        current_model: str = None,
        **kwargs,
    ):
        super().__init__(project_dir, permission_mode, console, **kwargs)
        self.delegation_tracker = delegation_tracker
        self.model_registry = model_registry
        self.current_model = current_model

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute delegation to another model.

        Args:
            model: Target model name to delegate to
            task: Description of what the specialist should do
            handoff_notes: Additional context for the specialist

        Returns:
            Dict containing delegation result or error
        """
        target_model = kwargs.get("model")
        task = kwargs.get("task", "")
        handoff_notes = kwargs.get("handoff_notes", "")

        # Validate required parameters
        if not target_model:
            return {
                "success": False,
                "error": "Missing required parameter: model",
                "action": "none",
            }

        if not task:
            return {
                "success": False,
                "error": "Missing required parameter: task",
                "action": "none",
            }

        # Check if delegation is allowed
        if self.delegation_tracker and not self.delegation_tracker.can_delegate():
            remaining = self.delegation_tracker.get_remaining()
            return {
                "success": False,
                "error": f"Maximum delegations reached ({self.delegation_tracker.max_delegations}). "  # noqa: E501
                f"You must complete this task yourself.",
                "action": "none",
                "remaining_delegations": remaining,
            }

        # Validate target model exists and is available
        if self.model_registry:
            is_valid, reason = self.model_registry.validate_delegation(
                self.current_model or "unknown", target_model
            )
            if not is_valid:
                return {
                    "success": False,
                    "error": reason,
                    "action": "none",
                }

        # Record the delegation
        if self.delegation_tracker:
            self.delegation_tracker.record_delegation(
                from_model=self.current_model or "unknown",
                to_model=target_model,
                reason=task,
            )

        # Return delegation action for the agent to handle
        return {
            "success": True,
            "action": "delegate",
            "target_model": target_model,
            "task": task,
            "handoff_notes": handoff_notes,
            "from_model": self.current_model,
            "remaining_delegations": (
                self.delegation_tracker.get_remaining() if self.delegation_tracker else None
            ),
            "message": f"Delegating to {target_model}: {task}",
        }


class ReturnToCoordinatorTool(Tool):
    """
    Tool for returning control to the coordinator model.

    Used by specialist models when they complete their delegated task.
    """

    default_timeout = 5
    timeout_category = "delegation"

    def __init__(
        self,
        project_dir: Path,
        permission_mode: str = PermissionMode.NORMAL,
        console=None,
        delegation_tracker=None,
        current_model: str = None,
        coordinator_model: str = "mimo-v2-flash",
        **kwargs,
    ):
        super().__init__(project_dir, permission_mode, console, **kwargs)
        self.delegation_tracker = delegation_tracker
        self.current_model = current_model
        self.coordinator_model = coordinator_model

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute return to coordinator.

        Args:
            summary: Summary of what was accomplished
            files_changed: List of files that were modified
            needs_review: Whether changes need review before continuing

        Returns:
            Dict containing return action for agent to handle
        """
        summary = kwargs.get("summary", "")
        files_changed = kwargs.get("files_changed", [])
        needs_review = kwargs.get("needs_review", False)

        if not summary:
            return {
                "success": False,
                "error": "Missing required parameter: summary",
                "action": "none",
            }

        # Record the return (counts as a delegation)
        if self.delegation_tracker:
            if not self.delegation_tracker.can_delegate():
                # Still allow return even if quota exhausted - it's going back
                pass
            self.delegation_tracker.record_delegation(
                from_model=self.current_model or "unknown",
                to_model=self.coordinator_model,
                reason=f"Return: {summary[:50]}...",
            )

        return {
            "success": True,
            "action": "return_to_coordinator",
            "target_model": self.coordinator_model,
            "summary": summary,
            "files_changed": files_changed,
            "needs_review": needs_review,
            "from_model": self.current_model,
            "message": f"Returning to coordinator: {summary}",
        }


# Tool Schemas for registration
DELEGATE_TO_MODEL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "delegate_to_model",
        "description": (
            "Hand off the current task to a specialist model. Use when you need "
            "capabilities outside your specialty. The specialist will receive full "
            "conversation history and context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": (
                        "Target model to delegate to. Options: "
                        "'deepseek-reasoner' (complex planning/reasoning), "
                        "'gpt-5.1-codex-mini' (primary coding/implementation), "
                        "'grok-code-fast-1' (fast coding tasks), "
                        "'hermes-3-405b' (debugging/security analysis), "
                        "'dolphin-24b' (security review), "
                        "'sonar-pro-search' (web research)"
                    ),
                },
                "task": {
                    "type": "string",
                    "description": "Clear description of what the specialist should accomplish",
                },
                "handoff_notes": {
                    "type": "string",
                    "description": (
                        "Context for the specialist: decisions made, files examined, "
                        "any relevant information they need to continue the work"
                    ),
                },
            },
            "required": ["model", "task"],
        },
    },
}

RETURN_TO_COORDINATOR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "return_to_coordinator",
        "description": (
            "Return control to the coordinator model after completing your delegated task. "
            "Use this when your work is done or when you need user input/decision."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Summary of what was accomplished during your task",
                },
                "files_changed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths that were created or modified",
                },
                "needs_review": {
                    "type": "boolean",
                    "description": "Set to true if changes should be reviewed before continuing",
                },
            },
            "required": ["summary"],
        },
    },
}


# Convenience function to get both schemas
def get_delegation_schemas() -> List[Dict[str, Any]]:
    """Get all delegation tool schemas."""
    return [DELEGATE_TO_MODEL_SCHEMA, RETURN_TO_COORDINATOR_SCHEMA]
