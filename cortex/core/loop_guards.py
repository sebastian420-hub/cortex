"""Loop guard system to prevent infinite loops and detect stuck states"""

from typing import List, Tuple, Dict, Any, Set, Optional, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .recovery import RecoveryManager, RecoveryAction, RecoveryContext


class LoopGuard:
    """Tracks tool calls and errors to detect infinite loops and stuck states"""

    def __init__(
        self,
        max_repeats: int = 3,
        stuck_threshold: int = 5,
        buffer_size: int = 10,
        recovery_manager: Optional["RecoveryManager"] = None,
        reflection_threshold_iterations: int = 10,
        reflection_threshold_failures: int = 3,
        reflection_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        """
        Initialize loop guard.

        Args:
            max_repeats: Maximum number of times same tool/error can repeat before triggering
            stuck_threshold: Minimum iterations without unique ops before stuck detection
            buffer_size: Size of rolling buffers for tool calls and errors
            recovery_manager: Optional RecoveryManager for intelligent error recovery
        """
        self.tool_call_history: List[Tuple[str, Dict[str, Any]]] = []
        self.error_history: List[Dict[str, Any]] = []
        self.max_repeats = max_repeats
        self.stuck_threshold = stuck_threshold
        self.buffer_size = buffer_size
        self.recovery_manager = recovery_manager
        # Reflection configuration
        self.reflection_threshold_iterations = reflection_threshold_iterations
        self.reflection_threshold_failures = reflection_threshold_failures
        self.reflection_callback = reflection_callback
        # Progress tracking
        self.unique_operations: Set[str] = set()  # Track unique operations
        self.files_read: Set[str] = set()  # Track files read
        self.files_written: Set[str] = set()  # Track files written
        self.iteration_count: int = 0
        self.consecutive_failures: int = 0
        self.last_reflection_iteration: int = 0

    def check_repeated_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """
        Check if same tool called too many times with same arguments.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments (dict or JSON string)

        Returns:
            True if tool called too many times, False otherwise
        """
        # Handle case where arguments might be a string (defensive check)
        if isinstance(arguments, str):
            try:
                import json

                arguments = json.loads(arguments)
            except (json.JSONDecodeError, TypeError):
                arguments = {}  # Fallback to empty dict if parsing fails

        # Check last N calls (where N = max_repeats)
        # Normalize arguments in history for comparison
        recent_calls = []
        for name, args in self.tool_call_history[-self.max_repeats :]:
            # Normalize args if it's a string
            if isinstance(args, str):
                try:
                    import json

                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    args = {}

            if name == tool_name and args == arguments:
                recent_calls.append((name, args))

        return len(recent_calls) >= self.max_repeats

    def check_repeated_error(self, error: Dict[str, Any]) -> bool:
        """
        Check if same error repeated too many times.

        Args:
            error: Error dictionary from tool result

        Returns:
            True if error repeated too many times, False otherwise
        """
        # Extract error message for comparison
        error_msg = error.get("error", "")
        error_type = error.get("error_type", "")

        # Check last N errors
        recent_errors = [
            e
            for e in self.error_history[-self.max_repeats :]
            if e.get("error") == error_msg and e.get("error_type") == error_type
        ]
        return len(recent_errors) >= self.max_repeats

    def record_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        """
        Record a tool call in history.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments (dict or JSON string)
        """
        # Handle case where arguments might be a string (defensive check)
        if isinstance(arguments, str):
            try:
                import json

                arguments = json.loads(arguments)
            except (json.JSONDecodeError, TypeError):
                arguments = {}  # Fallback to empty dict if parsing fails

        self.tool_call_history.append((tool_name, arguments))
        # Keep only last N calls to prevent memory growth
        if len(self.tool_call_history) > self.buffer_size:
            self.tool_call_history.pop(0)

    def record_error(self, error: Dict[str, Any]) -> None:
        """
        Record an error in history.

        Args:
            error: Error dictionary from tool result
        """
        self.error_history.append(error)
        # Keep only last N errors to prevent memory growth
        if len(self.error_history) > self.buffer_size:
            self.error_history.pop(0)
        
        # Track consecutive failures for reflection
        self.consecutive_failures += 1
        self._check_reflection_triggers()

    def check_stuck_state(self) -> bool:
        """
        Detect if agent is stuck (no progress in recent iterations).

        Returns:
            True if stuck, False otherwise
        """
        # If we've done many iterations but no unique operations, we're stuck
        # Having at least one unique operation indicates progress
        if self.iteration_count > self.stuck_threshold and len(self.unique_operations) == 0:
            return True
        return False

    def check_progress(self) -> bool:
        """
        Check if making progress toward goal.

        Returns:
            True if making progress, False otherwise
        """
        # Progress indicators:
        # - New files read/written
        # - New unique operations
        # - Decreasing error rate
        return len(self.unique_operations) > 0

    def _check_reflection_triggers(self) -> None:
        """
        Check if reflection should be triggered based on configured thresholds.
        
        Triggers reflection when:
        1. Iteration threshold reached (every N iterations)
        2. Consecutive failure threshold reached
        3. Stuck state detected
        """
        if not self.reflection_callback:
            return
        
        triggers = []
        
        # Check iteration threshold
        if self.reflection_threshold_iterations > 0:
            iterations_since_last_reflection = self.iteration_count - self.last_reflection_iteration
            if iterations_since_last_reflection >= self.reflection_threshold_iterations:
                triggers.append(f"iteration_threshold ({iterations_since_last_reflection} iterations since last reflection)")
        
        # Check consecutive failures threshold
        if self.reflection_threshold_failures > 0 and self.consecutive_failures >= self.reflection_threshold_failures:
            triggers.append(f"failure_threshold ({self.consecutive_failures} consecutive failures)")
        
        # Check stuck state
        if self.check_stuck_state():
            triggers.append("stuck_state (no progress detected)")
        
        # If any triggers, invoke callback
        if triggers:
            reflection_data = {
                "triggers": triggers,
                "iteration_count": self.iteration_count,
                "consecutive_failures": self.consecutive_failures,
                "unique_operations": len(self.unique_operations),
                "files_read": len(self.files_read),
                "files_written": len(self.files_written),
                "stuck_state": self.check_stuck_state(),
                "tool_calls_in_buffer": len(self.tool_call_history),
                "errors_in_buffer": len(self.error_history),
            }
            
            try:
                self.reflection_callback("loop_guard_reflection", reflection_data)
                # Update last reflection iteration to prevent immediate retriggering
                self.last_reflection_iteration = self.iteration_count
            except Exception as e:
                # Don't let reflection callback failures break the loop
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Reflection callback failed: {e}")

    def record_operation(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        """Record a unique operation for progress tracking."""
        # Handle case where arguments might still be a string (defensive check)
        if isinstance(arguments, str):
            try:
                import json

                arguments = json.loads(arguments)
            except (json.JSONDecodeError, TypeError):
                arguments = {}  # Fallback to empty dict if parsing fails

        op_key = f"{tool_name}:{str(sorted(arguments.items()))}"
        self.unique_operations.add(op_key)

        # Track file operations
        if tool_name == "read_file" and "path" in arguments:
            self.files_read.add(arguments["path"])
        elif tool_name == "write_file" and "path" in arguments:
            self.files_written.add(arguments["path"])
        
        # Reset consecutive failures on successful operation
        self.consecutive_failures = 0

    def increment_iteration(self) -> None:
        """Increment iteration counter and check for reflection triggers."""
        self.iteration_count += 1
        self._check_reflection_triggers()

    def reset(self) -> None:
        """Reset guard history (useful for testing or new conversation)"""
        self.tool_call_history.clear()
        self.error_history.clear()
        self.unique_operations.clear()
        self.files_read.clear()
        self.files_written.clear()
        self.iteration_count = 0
        self.consecutive_failures = 0
        self.last_reflection_iteration = 0
        if self.recovery_manager:
            self.recovery_manager.reset()

    def get_recovery_action(
        self, error: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]
    ) -> Optional["RecoveryAction"]:
        """
        Get recovery action for an error.

        Args:
            error: Error dictionary from tool result
            tool_name: Name of the tool that failed
            arguments: Arguments passed to the tool

        Returns:
            RecoveryAction if recovery manager is configured, None otherwise
        """
        if not self.recovery_manager:
            return None

        from .recovery import RecoveryContext

        context = RecoveryContext(
            error_type=error.get("error_type", "unknown"),
            error_message=error.get("error", "Unknown error"),
            tool_name=tool_name,
            arguments=arguments,
            attempt_count=self._count_similar_errors(error),
            similar_errors=self._get_similar_errors(error),
        )

        action = self.recovery_manager.determine_recovery_action(context)
        self.recovery_manager.record_recovery_attempt(context)
        return action

    def _count_similar_errors(self, error: Dict[str, Any]) -> int:
        """Count similar errors in history."""
        error_msg = error.get("error", "")
        error_type = error.get("error_type", "")
        return sum(
            1
            for e in self.error_history
            if e.get("error") == error_msg and e.get("error_type") == error_type
        )

    def _get_similar_errors(self, error: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get similar errors from history."""
        error_type = error.get("error_type", "")
        return [e for e in self.error_history if e.get("error_type") == error_type]

    def get_stats(self) -> Dict[str, Any]:
        """Get loop guard statistics."""
        stats = {
            "iteration_count": self.iteration_count,
            "unique_operations": len(self.unique_operations),
            "files_read": len(self.files_read),
            "files_written": len(self.files_written),
            "tool_calls_in_buffer": len(self.tool_call_history),
            "errors_in_buffer": len(self.error_history),
            "max_repeats": self.max_repeats,
            "stuck_threshold": self.stuck_threshold,
            "buffer_size": self.buffer_size,
            "consecutive_failures": self.consecutive_failures,
            "last_reflection_iteration": self.last_reflection_iteration,
            "reflection_threshold_iterations": self.reflection_threshold_iterations,
            "reflection_threshold_failures": self.reflection_threshold_failures,
            "has_reflection_callback": self.reflection_callback is not None,
            "stuck_state": self.check_stuck_state(),
        }
        if self.recovery_manager:
            stats["recovery"] = self.recovery_manager.get_stats()
        return stats
