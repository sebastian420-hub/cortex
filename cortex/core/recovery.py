"""Error recovery strategies for Cortex"""

import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Available recovery strategies."""
    SUGGEST = "suggest"           # Inject guidance for model to try alternative
    ESCALATE = "escalate"         # Stop and ask user
    CONTINUE = "continue"         # Continue with warning


@dataclass
class RecoveryContext:
    """Context for recovery decision."""
    error_type: str
    error_message: str
    tool_name: str
    arguments: Dict[str, Any]
    attempt_count: int
    similar_errors: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RecoveryAction:
    """Action to take for recovery."""
    strategy: RecoveryStrategy
    message: str
    suggested_prompt: Optional[str] = None
    alternative_arguments: Optional[Dict[str, Any]] = None


class RecoveryManager:
    """
    Manages error recovery strategies.

    Instead of just stopping when errors repeat, provides intelligent
    recovery suggestions to help the agent find alternative approaches.
    """

    def __init__(
        self,
        default_strategy: RecoveryStrategy = RecoveryStrategy.SUGGEST,
        max_recovery_attempts: int = 2,
    ):
        """
        Initialize recovery manager.

        Args:
            default_strategy: Default recovery strategy to use
            max_recovery_attempts: Maximum recovery attempts per error type/tool
        """
        self.default_strategy = default_strategy
        self.max_recovery_attempts = max_recovery_attempts
        self.recovery_attempts: Dict[str, int] = {}  # error_key -> attempts

    def get_error_key(self, error_type: str, tool_name: str) -> str:
        """Generate unique key for error tracking."""
        return f"{tool_name}:{error_type}"

    def should_attempt_recovery(self, context: RecoveryContext) -> bool:
        """
        Check if recovery should be attempted.

        Args:
            context: Recovery context

        Returns:
            True if recovery should be attempted
        """
        error_key = self.get_error_key(context.error_type, context.tool_name)
        current_attempts = self.recovery_attempts.get(error_key, 0)
        return current_attempts < self.max_recovery_attempts

    def record_recovery_attempt(self, context: RecoveryContext) -> None:
        """Record that recovery was attempted."""
        error_key = self.get_error_key(context.error_type, context.tool_name)
        self.recovery_attempts[error_key] = self.recovery_attempts.get(error_key, 0) + 1

    def determine_recovery_action(self, context: RecoveryContext) -> RecoveryAction:
        """
        Determine appropriate recovery action based on error context.

        Args:
            context: Recovery context with error details

        Returns:
            RecoveryAction to take
        """
        # Check if we should even attempt recovery
        if not self.should_attempt_recovery(context):
            return RecoveryAction(
                strategy=RecoveryStrategy.ESCALATE,
                message=f"Max recovery attempts reached for {context.error_type} in {context.tool_name}",
            )

        # Error-type specific recovery strategies
        recovery_handlers = {
            "not_found": self._recover_not_found,
            "timeout": self._recover_timeout,
            "permission": self._recover_permission,
            "validation": self._recover_validation,
            "execution": self._recover_execution,
            "security": self._recover_security,
        }

        handler = recovery_handlers.get(context.error_type, self._default_recovery)
        return handler(context)

    def _recover_not_found(self, context: RecoveryContext) -> RecoveryAction:
        """Recovery for not_found errors."""
        if context.tool_name in ("read_file", "write_file"):
            path = context.arguments.get("path", "unknown")
            return RecoveryAction(
                strategy=RecoveryStrategy.SUGGEST,
                message="File not found - suggesting alternative approaches",
                suggested_prompt=(
                    f"The file '{path}' was not found. "
                    "Please try one of these alternatives:\n"
                    "1. Use list_files to find the correct file name or location\n"
                    "2. Use search_files to search for content that might be in a different file\n"
                    "3. Check if the path is correct (relative to project root)\n"
                    "4. Ask the user for the correct path if uncertain"
                ),
            )
        return self._default_recovery(context)

    def _recover_timeout(self, context: RecoveryContext) -> RecoveryAction:
        """Recovery for timeout errors."""
        tool_name = context.tool_name

        suggestions = {
            "execute_command": (
                "The command timed out. Consider:\n"
                "1. Breaking the command into smaller operations\n"
                "2. Adding progress indicators or limits to the command\n"
                "3. Running a simpler version of the command first\n"
                "4. Informing the user about the timeout and asking how to proceed"
            ),
            "search_files": (
                "The search timed out. Consider:\n"
                "1. Narrowing the search with a more specific file pattern\n"
                "2. Searching in a specific directory instead of the whole project\n"
                "3. Using a more specific search query\n"
                "4. Listing files first to identify which directories to search"
            ),
            "run_tests": (
                "Tests timed out. Consider:\n"
                "1. Running a specific test file or pattern instead of all tests\n"
                "2. Adding a more restrictive test pattern\n"
                "3. Informing the user about the timeout"
            ),
        }

        return RecoveryAction(
            strategy=RecoveryStrategy.SUGGEST,
            message="Operation timed out - suggesting alternatives",
            suggested_prompt=suggestions.get(
                tool_name,
                f"The {tool_name} operation timed out. Consider breaking it into smaller "
                "operations or using more specific parameters to reduce scope."
            ),
        )

    def _recover_permission(self, context: RecoveryContext) -> RecoveryAction:
        """Recovery for permission errors - these typically need user action."""
        return RecoveryAction(
            strategy=RecoveryStrategy.ESCALATE,
            message="Permission denied - user action required",
            suggested_prompt=(
                f"Permission was denied for {context.tool_name}. "
                "This requires user action. Please inform the user about the "
                "permission issue and ask how they would like to proceed."
            ),
        )

    def _recover_security(self, context: RecoveryContext) -> RecoveryAction:
        """Recovery for security errors - do not retry."""
        return RecoveryAction(
            strategy=RecoveryStrategy.ESCALATE,
            message="Security violation - cannot proceed",
            suggested_prompt=(
                f"A security check blocked the {context.tool_name} operation: "
                f"{context.error_message}. This action is not allowed. "
                "Please inform the user and suggest a safer alternative approach."
            ),
        )

    def _recover_validation(self, context: RecoveryContext) -> RecoveryAction:
        """Recovery for validation errors."""
        return RecoveryAction(
            strategy=RecoveryStrategy.SUGGEST,
            message="Invalid input - suggesting corrections",
            suggested_prompt=(
                f"The input to {context.tool_name} was invalid: {context.error_message}. "
                "Please review the parameters and try again with corrected values. "
                "Check the tool documentation for correct parameter format."
            ),
        )

    def _recover_execution(self, context: RecoveryContext) -> RecoveryAction:
        """Recovery for execution errors."""
        return RecoveryAction(
            strategy=RecoveryStrategy.SUGGEST,
            message="Execution error - analyzing alternatives",
            suggested_prompt=(
                f"The {context.tool_name} execution failed: {context.error_message}. "
                "Consider:\n"
                "1. Checking if all prerequisites are met\n"
                "2. Trying an alternative approach to achieve the same goal\n"
                "3. Breaking the operation into smaller steps\n"
                "4. Informing the user about the failure and asking for guidance"
            ),
        )

    def _default_recovery(self, context: RecoveryContext) -> RecoveryAction:
        """Default recovery for unknown error types."""
        return RecoveryAction(
            strategy=self.default_strategy,
            message=f"Error in {context.tool_name}: {context.error_message}",
            suggested_prompt=(
                f"An error occurred with {context.tool_name}: {context.error_message}. "
                "Please analyze the error and try an alternative approach, "
                "or inform the user about the issue and ask for guidance."
            ),
        )

    def reset(self) -> None:
        """Reset recovery tracking (e.g., for new conversation)."""
        self.recovery_attempts.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        return {
            "total_recovery_attempts": sum(self.recovery_attempts.values()),
            "recovery_attempts_by_error": dict(self.recovery_attempts),
            "max_recovery_attempts": self.max_recovery_attempts,
            "default_strategy": self.default_strategy.value,
        }


def create_recovery_manager_from_config(config: Dict[str, Any]) -> RecoveryManager:
    """
    Create a RecoveryManager from configuration dict.

    Args:
        config: error_recovery configuration dict

    Returns:
        Configured RecoveryManager instance
    """
    strategy_map = {
        "suggest": RecoveryStrategy.SUGGEST,
        "escalate": RecoveryStrategy.ESCALATE,
        "continue": RecoveryStrategy.CONTINUE,
    }

    strategy_name = config.get("recovery_strategy", "suggest")
    default_strategy = strategy_map.get(strategy_name, RecoveryStrategy.SUGGEST)

    return RecoveryManager(
        default_strategy=default_strategy,
        max_recovery_attempts=config.get("max_recovery_attempts", 2),
    )
