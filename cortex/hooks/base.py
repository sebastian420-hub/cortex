"""Base classes for the hook system"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class HookAction(Enum):
    """
    Actions a hook can return to control execution flow.

    CONTINUE: Proceed normally with the operation
    SKIP: Skip this operation but continue the agent loop
    MODIFY: Use the modified data provided by the hook
    ABORT: Abort the operation entirely
    """

    CONTINUE = "continue"
    SKIP = "skip"
    MODIFY = "modify"
    ABORT = "abort"


@dataclass
class HookEvent:
    """
    Base event passed to hooks.

    Attributes:
        event_type: Type of event (e.g., "pre_tool_use", "stop")
        data: Event-specific data dictionary
        context: Additional context information
    """

    event_type: str
    data: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from data with optional default."""
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access to data."""
        return self.data[key]


@dataclass
class HookResult:
    """
    Result returned by a hook execution.

    Attributes:
        action: The action to take (default: CONTINUE)
        modified_data: Optional modified data to use instead of original
        message: Optional message explaining the action
        metadata: Optional additional metadata from the hook
    """

    action: HookAction = HookAction.CONTINUE
    modified_data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def continue_execution(cls) -> "HookResult":
        """Create a CONTINUE result."""
        return cls(action=HookAction.CONTINUE)

    @classmethod
    def skip_operation(cls, message: Optional[str] = None) -> "HookResult":
        """Create a SKIP result."""
        return cls(action=HookAction.SKIP, message=message)

    @classmethod
    def modify_data(cls, data: Dict[str, Any], message: Optional[str] = None) -> "HookResult":
        """Create a MODIFY result with new data."""
        return cls(action=HookAction.MODIFY, modified_data=data, message=message)

    @classmethod
    def abort_operation(cls, message: str) -> "HookResult":
        """Create an ABORT result with reason."""
        return cls(action=HookAction.ABORT, message=message)


class BaseHook(ABC):
    """
    Base class for all hooks.

    Hooks intercept agent operations at defined points, allowing for:
    - Validation and modification of inputs
    - Logging and auditing
    - Custom permission checks
    - Result processing

    Subclasses must implement the execute() method and define
    which event types they handle via the 'handles' attribute.
    """

    # Event types this hook handles (e.g., ["pre_tool_use", "post_tool_use"])
    # Use ["*"] to handle all events
    handles: List[str] = []

    # Priority determines execution order (lower = earlier)
    # Default hooks use 100, use lower for early execution, higher for late
    priority: int = 100

    # Whether the hook is enabled
    enabled: bool = True

    # Human-readable name for logging
    name: str = "BaseHook"

    def __init__(self, name: Optional[str] = None, priority: Optional[int] = None):
        """
        Initialize the hook.

        Args:
            name: Optional custom name for this hook instance
            priority: Optional custom priority
        """
        if name:
            self.name = name
        if priority is not None:
            self.priority = priority

    @abstractmethod
    def execute(self, event: HookEvent) -> HookResult:
        """
        Execute the hook logic.

        This method is called when an event matching this hook's
        'handles' list is dispatched.

        Args:
            event: The event to process

        Returns:
            HookResult indicating what action to take
        """
        pass

    def should_handle(self, event_type: str) -> bool:
        """
        Check if this hook handles the given event type.

        Args:
            event_type: The event type to check

        Returns:
            True if this hook handles the event
        """
        if not self.enabled:
            return False
        return event_type in self.handles or "*" in self.handles

    def enable(self) -> None:
        """Enable this hook."""
        self.enabled = True

    def disable(self) -> None:
        """Disable this hook."""
        self.enabled = False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, priority={self.priority}, enabled={self.enabled})"  # noqa: E501
