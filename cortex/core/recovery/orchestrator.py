"""Recovery orchestrator for coordinating session repair and recovery actions."""

import logging
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass

from .checkpoint import CheckpointManager, Checkpoint
from .health import SessionHealthMonitor, HealthReport

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Recovery strategy options."""

    NO_ACTION = "no_action"  # Session is healthy
    AUTO_REPAIR = "auto_repair"  # Fix minor issues automatically
    CHECKPOINT_ROLLBACK = "checkpoint_rollback"  # Roll back to checkpoint
    MANUAL_REPAIR = "manual_repair"  # Require user intervention
    EMERGENCY_RESET = "emergency_reset"  # Start fresh session


@dataclass
class RecoveryAction:
    """A recommended recovery action."""

    strategy: RecoveryStrategy
    message: str
    confidence: float  # 0-1, how confident we are in this action
    requires_user_confirmation: bool = False
    suggested_checkpoint: Optional[Checkpoint] = None
    repair_details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strategy": self.strategy.value,
            "message": self.message,
            "confidence": self.confidence,
            "requires_user_confirmation": self.requires_user_confirmation,
            "suggested_checkpoint_id": (
                self.suggested_checkpoint.id if self.suggested_checkpoint else None
            ),
            "repair_details": self.repair_details,
        }


class RecoveryOrchestrator:
    """
    Orchestrates session recovery operations.

    Analyzes session health, determines appropriate recovery strategies,
    and coordinates execution of recovery actions.
    """

    def __init__(self, checkpoint_manager: CheckpointManager, health_monitor: SessionHealthMonitor):
        """
        Initialize recovery orchestrator.

        Args:
            checkpoint_manager: Checkpoint manager instance
            health_monitor: Health monitor instance
        """
        self.checkpoint_manager = checkpoint_manager
        self.health_monitor = health_monitor
        self.logger = logging.getLogger(__name__)

    def analyze_and_recommend(
        self,
        session_id: str,
        conversation_history: List[Dict[str, Any]],
        recent_errors: Optional[List[Dict[str, Any]]] = None,
    ) -> RecoveryAction:
        """
        Analyze session health and recommend recovery action.

        Args:
            session_id: Session identifier
            conversation_history: Current conversation history
            recent_errors: List of recent error events

        Returns:
            Recommended recovery action
        """
        # Get comprehensive health analysis
        health_report = self.health_monitor.analyze_health(conversation_history, recent_errors)

        # Determine recovery strategy based on health report
        strategy = self._determine_recovery_strategy(health_report, session_id)

        # Create recovery action with details
        action = self._create_recovery_action(strategy, health_report, session_id)

        self.logger.info(
            f"Recovery analysis for session {session_id}: "
            f"health={health_report.overall_score:.2f}, "
            f"strategy={strategy.value}, "
            f"confidence={action.confidence:.2f}"
        )

        return action

    def execute_recovery(
        self, action: RecoveryAction, conversation_history: List[Dict[str, Any]], session_id: str
    ) -> Dict[str, Any]:
        """
        Execute a recovery action.

        Args:
            action: Recovery action to execute
            conversation_history: Current conversation history
            session_id: Session identifier

        Returns:
            Recovery result with new conversation history and status
        """
        self.logger.info(
            f"Executing recovery action: {action.strategy.value} for session {session_id}"
        )

        result = {
            "success": False,
            "strategy": action.strategy.value,
            "message": "",
            "new_history": conversation_history.copy(),
            "checkpoint_created": None,
            "issues_resolved": 0,
        }

        try:
            if action.strategy == RecoveryStrategy.NO_ACTION:
                result["success"] = True
                result["message"] = "No recovery action needed"

            elif action.strategy == RecoveryStrategy.AUTO_REPAIR:
                repair_result = self._execute_auto_repair(
                    conversation_history, action.repair_details
                )
                result.update(repair_result)

            elif action.strategy == RecoveryStrategy.CHECKPOINT_ROLLBACK:
                rollback_result = self._execute_checkpoint_rollback(
                    session_id, action.suggested_checkpoint
                )
                result.update(rollback_result)

            elif action.strategy == RecoveryStrategy.MANUAL_REPAIR:
                repair_result = self._execute_manual_repair(
                    conversation_history, action.repair_details
                )
                result.update(repair_result)

            elif action.strategy == RecoveryStrategy.EMERGENCY_RESET:
                reset_result = self._execute_emergency_reset(session_id)
                result.update(reset_result)

            # Create checkpoint after successful recovery (if significant changes made)
            if result["success"] and len(result["new_history"]) != len(conversation_history):
                checkpoint = self.checkpoint_manager.create_checkpoint(
                    session_id,
                    result["new_history"],
                    metadata={"recovery_action": action.strategy.value},
                )
                result["checkpoint_created"] = checkpoint.id

        except Exception as e:
            self.logger.error(f"Recovery execution failed: {e}")
            result["success"] = False
            result["message"] = f"Recovery failed: {str(e)}"

        return result

    def _determine_recovery_strategy(
        self, health_report: HealthReport, session_id: str
    ) -> RecoveryStrategy:
        """
        Determine the appropriate recovery strategy based on health analysis.

        Uses a decision tree approach considering:
        - Overall health score
        - Critical issue count
        - Available checkpoints
        - Issue types and severity
        """
        score = health_report.overall_score
        critical_issues = [i for i in health_report.issues if i.get("severity") == "critical"]
        _high_issues = [i for i in health_report.issues if i.get("severity") == "high"]

        # Check if checkpoints are available for rollback
        has_checkpoints = len(self.checkpoint_manager.list_checkpoints(session_id)) > 0

        # Decision tree
        if score >= 0.9:
            # Very healthy - no action needed
            return RecoveryStrategy.NO_ACTION

        elif score >= 0.8:
            # Good health - auto-repair minor issues
            if len(critical_issues) == 0:
                return RecoveryStrategy.AUTO_REPAIR

        elif score >= 0.6:
            # Moderate issues - consider repair or rollback
            if len(critical_issues) <= 2:
                return RecoveryStrategy.AUTO_REPAIR
            elif has_checkpoints:
                return RecoveryStrategy.CHECKPOINT_ROLLBACK

        else:
            # Poor health - require manual intervention or emergency reset
            if len(critical_issues) > 5 or not has_checkpoints:
                return RecoveryStrategy.EMERGENCY_RESET
            else:
                return RecoveryStrategy.MANUAL_REPAIR

        # Default fallback
        return RecoveryStrategy.MANUAL_REPAIR

    def _create_recovery_action(
        self, strategy: RecoveryStrategy, health_report: HealthReport, session_id: str
    ) -> RecoveryAction:
        """Create a detailed recovery action based on strategy."""

        if strategy == RecoveryStrategy.NO_ACTION:
            return RecoveryAction(
                strategy=strategy,
                message="Session is healthy - no recovery needed",
                confidence=1.0,
                requires_user_confirmation=False,
            )

        elif strategy == RecoveryStrategy.AUTO_REPAIR:
            repair_details = self._analyze_repair_details(health_report)
            confidence = min(
                0.8, health_report.overall_score + 0.2
            )  # Boost confidence for auto-repair

            return RecoveryAction(
                strategy=strategy,
                message=f"Auto-repair {len(repair_details)} detected issues",
                confidence=confidence,
                requires_user_confirmation=False,
                repair_details=repair_details,
            )

        elif strategy == RecoveryStrategy.CHECKPOINT_ROLLBACK:
            checkpoint = self._select_rollback_checkpoint(session_id, health_report)
            confidence = (
                0.9 if checkpoint and checkpoint.health_score > health_report.overall_score else 0.7
            )

            return RecoveryAction(
                strategy=strategy,
                message=f"Rollback to checkpoint from {checkpoint.timestamp.strftime('%H:%M:%S') if checkpoint else 'unknown'}",  # noqa: E501
                confidence=confidence,
                requires_user_confirmation=True,
                suggested_checkpoint=checkpoint,
            )

        elif strategy == RecoveryStrategy.MANUAL_REPAIR:
            repair_details = self._analyze_repair_details(health_report)

            return RecoveryAction(
                strategy=strategy,
                message=f"Manual repair needed for {len(health_report.issues)} issues",
                confidence=0.6,
                requires_user_confirmation=True,
                repair_details=repair_details,
            )

        elif strategy == RecoveryStrategy.EMERGENCY_RESET:
            return RecoveryAction(
                strategy=strategy,
                message="Emergency reset - start fresh session",
                confidence=0.8,
                requires_user_confirmation=True,
            )

        # Fallback
        return RecoveryAction(
            strategy=RecoveryStrategy.MANUAL_REPAIR,
            message="Manual review recommended",
            confidence=0.5,
            requires_user_confirmation=True,
        )

    def _analyze_repair_details(self, health_report: HealthReport) -> Dict[str, Any]:
        """Analyze what repairs can be made automatically."""
        repairable_issues = []
        manual_issues = []

        for issue in health_report.issues:
            issue_type = issue.get("type", "")

            # Issues that can be auto-repaired
            if issue_type in [
                "invalid_assistant_message",
                "invalid_tool_result",
                "duplicate_content",
            ]:
                repairable_issues.append(issue)
            else:
                manual_issues.append(issue)

        return {
            "repairable_issues": repairable_issues,
            "manual_issues": manual_issues,
            "can_auto_repair": len(repairable_issues) > 0,
            "estimated_fixes": len(repairable_issues),
        }

    def _select_rollback_checkpoint(
        self, session_id: str, health_report: HealthReport
    ) -> Optional[Checkpoint]:
        """Select the best checkpoint for rollback."""
        checkpoints = self.checkpoint_manager.list_checkpoints(session_id)

        if not checkpoints:
            return None

        # Prefer checkpoints with better health scores
        healthy_checkpoints = [
            cp for cp in checkpoints if cp.health_score > health_report.overall_score
        ]

        if healthy_checkpoints:
            # Return most recent healthy checkpoint
            return max(healthy_checkpoints, key=lambda cp: cp.timestamp)

        # Fallback: most recent checkpoint
        return checkpoints[0]

    def _execute_auto_repair(
        self, conversation_history: List[Dict[str, Any]], repair_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute automatic repair of conversation issues."""
        new_history = conversation_history.copy()
        issues_fixed = 0

        repairable_issues = repair_details.get("repairable_issues", [])

        for issue in repairable_issues:
            issue_type = issue.get("type", "")
            index = issue.get("index", -1)

            if index >= 0 and index < len(new_history):
                if issue_type == "invalid_assistant_message":
                    # Fix invalid assistant message
                    msg = new_history[index]
                    if not msg.get("content") and not msg.get("tool_calls"):
                        if msg.get("reasoning_content"):
                            msg["content"] = f"[Repaired: {msg['reasoning_content'][:100]}...]"
                        else:
                            msg["content"] = "[Repaired empty response]"
                        issues_fixed += 1

                elif issue_type == "invalid_tool_result":
                    # Fix invalid tool result
                    msg = new_history[index]
                    if not isinstance(msg.get("content"), str):
                        msg["content"] = (
                            '{"success": false, "error": "Repaired invalid result format"}'
                        )
                        issues_fixed += 1

        return {
            "success": True,
            "message": f"Auto-repaired {issues_fixed} issues",
            "new_history": new_history,
            "issues_resolved": issues_fixed,
        }

    def _execute_checkpoint_rollback(
        self, session_id: str, checkpoint: Checkpoint
    ) -> Dict[str, Any]:
        """Execute checkpoint rollback."""
        if not checkpoint:
            return {
                "success": False,
                "message": "No checkpoint available for rollback",
                "new_history": [],
            }

        try:
            new_history = self.checkpoint_manager.restore_checkpoint(checkpoint)
            return {
                "success": True,
                "message": f"Rolled back to checkpoint {checkpoint.id}",
                "new_history": new_history,
                "checkpoint_used": checkpoint.id,
            }
        except Exception as e:
            return {"success": False, "message": f"Rollback failed: {str(e)}", "new_history": []}

    def _execute_manual_repair(
        self, conversation_history: List[Dict[str, Any]], repair_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare for manual repair (returns suggestions, doesn't modify)."""
        repairable = repair_details.get("repairable_issues", [])
        manual = repair_details.get("manual_issues", [])

        suggestions = []
        for issue in repairable:
            suggestions.append(f"Fix {issue['type']} at message {issue.get('index', 'unknown')}")

        return {
            "success": True,
            "message": f"Manual repair prepared - {len(repairable)} auto-fixable, {len(manual)} manual issues",  # noqa: E501
            "new_history": conversation_history,  # No changes made
            "repair_suggestions": suggestions,
        }

    def _execute_emergency_reset(self, session_id: str) -> Dict[str, Any]:
        """Execute emergency session reset."""
        # Create a checkpoint of current state before reset
        try:
            self.checkpoint_manager.create_checkpoint(
                session_id,
                [],  # Empty history for reset
                health_score=1.0,
                metadata={"emergency_reset": True},
                force=True,
            )
        except Exception as e:
            self.logger.warning(f"Failed to create pre-reset checkpoint: {e}")

        return {
            "success": True,
            "message": "Emergency reset completed - session history cleared",
            "new_history": [],  # Fresh start
            "emergency_reset": True,
        }
