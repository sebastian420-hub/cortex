"""Built-in hook implementations"""

from typing import Any, Dict, List, Optional, Set
import logging
import re
from datetime import datetime

from .base import BaseHook, HookEvent, HookResult, HookAction
from .events import (
    EVENT_PRE_TOOL_USE,
    EVENT_POST_TOOL_USE,
    EVENT_STOP,
    EVENT_USER_PROMPT_SUBMIT,
    EVENT_SESSION_START,
    EVENT_SESSION_END,
)


class LoggingHook(BaseHook):
    """
    Hook that logs all events for debugging and auditing.

    Can be configured to log to a file or use Python's logging system.
    """

    handles = ["*"]  # Handle all events
    priority = 10  # Run early to capture everything
    name = "LoggingHook"

    def __init__(
        self,
        log_file: Optional[str] = None,
        log_level: str = "INFO",
        include_arguments: bool = True,
        include_results: bool = True,
    ):
        """
        Initialize logging hook.

        Args:
            log_file: Optional file path to write logs
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            include_arguments: Include tool arguments in logs
            include_results: Include tool results in logs
        """
        super().__init__()
        self.log_file = log_file
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.include_arguments = include_arguments
        self.include_results = include_results

        # Set up logger
        self.logger = logging.getLogger("localagent.hooks")
        if log_file:
            handler = logging.FileHandler(log_file)
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self.logger.addHandler(handler)

    def execute(self, event: HookEvent) -> HookResult:
        """Log the event and continue."""
        timestamp = datetime.now().isoformat()

        if event.event_type == EVENT_PRE_TOOL_USE:
            msg = f"[{timestamp}] PRE_TOOL_USE: {event.data.get('tool_name')}"
            if self.include_arguments:
                msg += f" args={event.data.get('arguments')}"
            self.logger.log(self.log_level, msg)

        elif event.event_type == EVENT_POST_TOOL_USE:
            success = "SUCCESS" if event.data.get("success") else "FAILED"
            msg = f"[{timestamp}] POST_TOOL_USE: {event.data.get('tool_name')} - {success}"
            if self.include_results and not event.data.get("success"):
                msg += f" error={event.data.get('result', {}).get('error')}"
            self.logger.log(self.log_level, msg)

        elif event.event_type == EVENT_USER_PROMPT_SUBMIT:
            prompt = event.data.get("prompt", "")[:100]  # Truncate long prompts
            msg = f"[{timestamp}] USER_PROMPT: {prompt}..."
            self.logger.log(self.log_level, msg)

        elif event.event_type == EVENT_STOP:
            msg = f"[{timestamp}] STOP: iteration={event.data.get('iteration')}"
            self.logger.log(self.log_level, msg)

        elif event.event_type == EVENT_SESSION_START:
            msg = f"[{timestamp}] SESSION_START: model={event.data.get('model')}"
            self.logger.log(self.log_level, msg)

        elif event.event_type == EVENT_SESSION_END:
            msg = f"[{timestamp}] SESSION_END: messages={event.data.get('messages_count')}"
            self.logger.log(self.log_level, msg)

        else:
            msg = f"[{timestamp}] {event.event_type}: {event.data}"
            self.logger.log(self.log_level, msg)

        return HookResult.continue_execution()


class PermissionHook(BaseHook):
    """
    Hook that enforces tool-level permissions.

    Can require approval for specific tools or block them entirely.
    """

    handles = [EVENT_PRE_TOOL_USE]
    priority = 50  # Run before most other hooks
    name = "PermissionHook"

    def __init__(
        self,
        require_approval: Optional[List[str]] = None,
        blocked: Optional[List[str]] = None,
        allowed: Optional[List[str]] = None,
    ):
        """
        Initialize permission hook.

        Args:
            require_approval: Tools that require explicit approval
            blocked: Tools that are completely blocked
            allowed: If set, only these tools are allowed (whitelist mode)
        """
        super().__init__()
        self.require_approval: Set[str] = set(require_approval or [])
        self.blocked: Set[str] = set(blocked or [])
        self.allowed: Optional[Set[str]] = set(allowed) if allowed else None

    def execute(self, event: HookEvent) -> HookResult:
        """Check permissions for tool execution."""
        tool_name = event.data.get("tool_name", "")

        # Check if tool is blocked
        if tool_name in self.blocked:
            return HookResult.abort_operation(
                f"Tool '{tool_name}' is blocked by permission policy"
            )

        # Check whitelist if enabled
        if self.allowed is not None and tool_name not in self.allowed:
            return HookResult.abort_operation(
                f"Tool '{tool_name}' is not in the allowed list"
            )

        # Check if approval is required
        if tool_name in self.require_approval:
            # In a real implementation, this would prompt the user
            # For now, we just add metadata to indicate approval is needed
            return HookResult(
                action=HookAction.CONTINUE,
                metadata={"requires_approval": True, "tool_name": tool_name}
            )

        return HookResult.continue_execution()


class CommandBlockerHook(BaseHook):
    """
    Hook that blocks dangerous shell commands.

    Uses pattern matching to detect and block potentially harmful commands.
    """

    handles = [EVENT_PRE_TOOL_USE]
    priority = 40  # Run before permission hook
    name = "CommandBlockerHook"

    # Default dangerous patterns
    DEFAULT_BLOCKED_PATTERNS = [
        r"rm\s+-rf\s+/",           # rm -rf /
        r"rm\s+-rf\s+~",           # rm -rf ~
        r"rm\s+-rf\s+\*",          # rm -rf *
        r"sudo\s+rm",              # sudo rm
        r"mkfs\.",                 # mkfs.* (format disk)
        r"dd\s+if=.*of=/dev",      # dd to device
        r">\s*/dev/sd[a-z]",       # Write to disk device
        r":\(\)\s*\{\s*:\|:&\s*\};:",  # Fork bomb
        r"chmod\s+-R\s+777\s+/",   # Chmod 777 root
        r"wget.*\|\s*sh",          # Download and execute
        r"curl.*\|\s*sh",          # Download and execute
        r"curl.*\|\s*bash",        # Download and execute
    ]

    def __init__(
        self,
        blocked_patterns: Optional[List[str]] = None,
        additional_patterns: Optional[List[str]] = None,
        blocked_commands: Optional[List[str]] = None,
    ):
        """
        Initialize command blocker hook.

        Args:
            blocked_patterns: Replace default patterns with these
            additional_patterns: Add these patterns to defaults
            blocked_commands: Exact command strings to block
        """
        super().__init__()

        # Set up patterns
        if blocked_patterns is not None:
            patterns = blocked_patterns
        else:
            patterns = self.DEFAULT_BLOCKED_PATTERNS.copy()
            if additional_patterns:
                patterns.extend(additional_patterns)

        self.patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
        self.blocked_commands: Set[str] = set(blocked_commands or [])

    def execute(self, event: HookEvent) -> HookResult:
        """Check if command should be blocked."""
        tool_name = event.data.get("tool_name", "")

        # Only check execute_command tool
        if tool_name != "execute_command":
            return HookResult.continue_execution()

        arguments = event.data.get("arguments", {})
        command = arguments.get("command", "")

        # Check exact matches
        if command in self.blocked_commands:
            return HookResult.abort_operation(
                f"Command '{command}' is blocked by security policy"
            )

        # Check patterns
        for pattern in self.patterns:
            if pattern.search(command):
                return HookResult.abort_operation(
                    f"Command '{command}' matches blocked pattern and has been blocked for security"
                )

        return HookResult.continue_execution()


class IterationLimitHook(BaseHook):
    """
    Hook that enforces iteration limits to prevent infinite loops.

    Provides more sophisticated control than the basic loop guard.
    """

    handles = [EVENT_STOP]
    priority = 90
    name = "IterationLimitHook"

    def __init__(
        self,
        max_iterations: int = 15,
        warn_at: int = 10,
    ):
        """
        Initialize iteration limit hook.

        Args:
            max_iterations: Maximum iterations before forcing stop
            warn_at: Iteration count to start warning
        """
        super().__init__()
        self.max_iterations = max_iterations
        self.warn_at = warn_at
        self.logger = logging.getLogger("localagent.hooks")

    def execute(self, event: HookEvent) -> HookResult:
        """Check iteration count and decide on stopping."""
        iteration = event.data.get("iteration", 0)
        has_tool_calls = event.data.get("has_tool_calls", False)

        # Force stop if at max iterations
        if iteration >= self.max_iterations:
            return HookResult.abort_operation(
                f"Maximum iterations ({self.max_iterations}) reached"
            )

        # Warn if approaching limit
        if iteration >= self.warn_at:
            remaining = self.max_iterations - iteration
            self.logger.warning(
                f"Approaching iteration limit: {iteration}/{self.max_iterations} "
                f"({remaining} remaining)"
            )

        # Continue if there are more tool calls to process
        if has_tool_calls:
            return HookResult.continue_execution()

        # No more tool calls, allow stopping
        return HookResult.skip_operation("No more tool calls, stopping")


class MetricsHook(BaseHook):
    """
    Hook that collects metrics about agent execution.

    Tracks tool usage, execution times, success rates, etc.
    """

    handles = [EVENT_PRE_TOOL_USE, EVENT_POST_TOOL_USE, EVENT_SESSION_START, EVENT_SESSION_END]
    priority = 5  # Run very early
    name = "MetricsHook"

    def __init__(self):
        """Initialize metrics hook."""
        super().__init__()
        self.reset()

    def reset(self):
        """Reset all metrics."""
        self.tool_calls: Dict[str, int] = {}
        self.tool_successes: Dict[str, int] = {}
        self.tool_failures: Dict[str, int] = {}
        self.total_calls = 0
        self.session_start_time: Optional[datetime] = None

    def execute(self, event: HookEvent) -> HookResult:
        """Collect metrics from events."""
        if event.event_type == EVENT_SESSION_START:
            self.reset()
            self.session_start_time = datetime.now()

        elif event.event_type == EVENT_PRE_TOOL_USE:
            tool_name = event.data.get("tool_name", "unknown")
            self.tool_calls[tool_name] = self.tool_calls.get(tool_name, 0) + 1
            self.total_calls += 1

        elif event.event_type == EVENT_POST_TOOL_USE:
            tool_name = event.data.get("tool_name", "unknown")
            if event.data.get("success"):
                self.tool_successes[tool_name] = self.tool_successes.get(tool_name, 0) + 1
            else:
                self.tool_failures[tool_name] = self.tool_failures.get(tool_name, 0) + 1

        elif event.event_type == EVENT_SESSION_END:
            # Could log summary here
            pass

        return HookResult.continue_execution()

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics as a dictionary."""
        total_successes = sum(self.tool_successes.values())
        total_failures = sum(self.tool_failures.values())
        success_rate = total_successes / self.total_calls if self.total_calls > 0 else 0

        return {
            "total_calls": self.total_calls,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "success_rate": success_rate,
            "tool_calls": dict(self.tool_calls),
            "tool_successes": dict(self.tool_successes),
            "tool_failures": dict(self.tool_failures),
            "session_start": self.session_start_time.isoformat() if self.session_start_time else None,
        }
