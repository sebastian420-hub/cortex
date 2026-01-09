"""Hook system for LocalAgent - Event-driven extensibility"""

from .base import HookAction, HookEvent, HookResult, BaseHook
from .events import (
    PreToolUseEvent,
    PostToolUseEvent,
    StopEvent,
    UserPromptSubmitEvent,
    SessionStartEvent,
    SessionEndEvent,
    # Event type constants
    EVENT_PRE_TOOL_USE,
    EVENT_POST_TOOL_USE,
    EVENT_STOP,
    EVENT_USER_PROMPT_SUBMIT,
    EVENT_SESSION_START,
    EVENT_SESSION_END,
)
from .manager import HookManager
from .builtin import (
    LoggingHook,
    PermissionHook,
    CommandBlockerHook,
    IterationLimitHook,
    MetricsHook,
)

__all__ = [
    # Base classes
    "HookAction",
    "HookEvent",
    "HookResult",
    "BaseHook",
    # Events
    "PreToolUseEvent",
    "PostToolUseEvent",
    "StopEvent",
    "UserPromptSubmitEvent",
    "SessionStartEvent",
    "SessionEndEvent",
    # Event type constants
    "EVENT_PRE_TOOL_USE",
    "EVENT_POST_TOOL_USE",
    "EVENT_STOP",
    "EVENT_USER_PROMPT_SUBMIT",
    "EVENT_SESSION_START",
    "EVENT_SESSION_END",
    # Manager
    "HookManager",
    # Built-in hooks
    "LoggingHook",
    "PermissionHook",
    "CommandBlockerHook",
    "IterationLimitHook",
    "MetricsHook",
]
