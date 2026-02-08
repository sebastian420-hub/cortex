"""Error recovery strategies for Cortex"""

import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Available recovery strategies."""

    SUGGEST = "suggest"  # Inject guidance for model to try alternative
    ESCALATE = "escalate"  # Stop and ask user
    CONTINUE = "continue"  # Continue with warning


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
        """Recovery for not_found errors with enhanced debugging."""
        path = context.arguments.get("path", "unknown")

        # Extract filename from path for search suggestions
        filename = path.split("/")[-1].split("\\")[-1] if path != "unknown" else ""
        filename_base = filename.rsplit(".", 1)[0] if "." in filename else filename

        if context.tool_name in ("read_file", "write_file", "edit"):
            return RecoveryAction(
                strategy=RecoveryStrategy.SUGGEST,
                message="File not found - initiating file discovery",
                suggested_prompt=(
                    f"DEBUG: File '{path}' was not found.\n\n"
                    f"**Self-Debugging Steps:**\n"
                    f"1. Search for similar filenames:\n"
                    f'   glob(pattern="**/*{filename_base}*")\n\n'
                    f"2. List the parent directory to check path:\n"
                    f"   list_files(path=\"{'/'.join(path.split('/')[:-1]) or '.'}\")\n\n"
                    f"3. Search for related content:\n"
                    f'   grep(pattern="{filename_base}", output_mode="files_with_matches")\n\n'
                    f"4. Check case sensitivity - the file might exist with different casing.\n\n"
                    f"**Before asking user:** Try at least one of these searches first."
                ),
            )
        elif context.tool_name == "grep":
            return RecoveryAction(
                strategy=RecoveryStrategy.SUGGEST,
                message="Search path not found",
                suggested_prompt=(
                    f"DEBUG: Search path '{path}' not found.\n\n"
                    f"**Self-Debugging Steps:**\n"
                    f"1. Verify the directory exists:\n"
                    f'   list_files(path=".")\n\n'
                    f"2. Search from project root instead:\n"
                    f"   grep(pattern=\"{context.arguments.get('pattern', '')}\", path=\".\")\n\n"
                    f"3. Use glob to find relevant directories:\n"
                    f'   glob(pattern="**/")\n'
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
                "operations or using more specific parameters to reduce scope.",
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
        """Recovery for execution errors with enhanced debugging."""
        error_msg = context.error_message.lower()

        # Detect common error patterns and provide specific guidance
        specific_guidance = ""

        if "command not found" in error_msg or "not recognized" in error_msg:
            cmd = (
                context.arguments.get("command", "").split()[0]
                if context.arguments.get("command")
                else ""
            )
            specific_guidance = (
                f"**Command Not Found Debug:**\n"
                f"The command '{cmd}' is not available.\n"
                f"1. Check if it needs to be installed (pip install, npm install, etc.)\n"
                f"2. Check if it's a platform-specific command (use Python equivalent)\n"
                f"3. For Windows: Use PowerShell syntax or Python scripts instead\n\n"
            )
        elif "permission denied" in error_msg or "access denied" in error_msg:
            specific_guidance = (
                "**Permission Debug:**\n"
                "Access was denied.\n"
                "1. Check if the file/directory is read-only\n"
                "2. Check if another process has the file locked\n"
                "3. Try a different approach that doesn't require elevated access\n\n"
            )
        elif "syntax error" in error_msg or "invalid syntax" in error_msg:
            specific_guidance = (
                "**Syntax Error Debug:**\n"
                "There's a syntax issue in the code or command.\n"
                "1. Review the exact error message for line number/position\n"
                "2. Check for mismatched quotes, brackets, or parentheses\n"
                "3. Read the file and examine the problematic area\n\n"
            )
        elif "import" in error_msg or "module" in error_msg:
            specific_guidance = (
                f"**Import/Module Debug:**\n"
                f"A module couldn't be imported.\n"
                f"1. Check if the package is installed in the environment\n"
                f"2. Check for typos in the import path\n"
                f"3. Verify the module exists: glob(pattern=\"**/{context.arguments.get('command', '').split()[-1] if 'import' in error_msg else '*'}.py\")\n\n"
            )
        elif "test" in context.tool_name.lower() or "test" in error_msg:
            specific_guidance = (
                "**Test Failure Debug:**\n"
                "Tests are failing.\n"
                "1. Read the failing test file to understand expectations\n"
                "2. Check the test output for assertion details\n"
                "3. Run a single test to isolate the issue\n"
                "4. Check if test fixtures or setup is correct\n\n"
            )

        return RecoveryAction(
            strategy=RecoveryStrategy.SUGGEST,
            message="Execution error - initiating self-debugging",
            suggested_prompt=(
                f"DEBUG: {context.tool_name} failed: {context.error_message}\n\n"
                f"{specific_guidance}"
                f"**General Debug Steps:**\n"
                f"1. Analyze the exact error message above\n"
                f"2. Check prerequisites (dependencies, environment)\n"
                f"3. Try a simpler version of the operation first\n"
                f"4. Break complex operations into smaller steps\n\n"
                f"**Before escalating to user:** Try to diagnose and fix the issue yourself."
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
