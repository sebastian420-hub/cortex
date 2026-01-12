"""Event definitions for the hook system"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import HookEvent


# Event type constants
EVENT_PRE_TOOL_USE = "pre_tool_use"
EVENT_POST_TOOL_USE = "post_tool_use"
EVENT_STOP = "stop"
EVENT_USER_PROMPT_SUBMIT = "user_prompt_submit"
EVENT_SESSION_START = "session_start"
EVENT_SESSION_END = "session_end"


@dataclass
class PreToolUseEvent(HookEvent):
    """
    Event fired before a tool is executed.

    This event allows hooks to:
    - Validate tool inputs
    - Block certain tools
    - Modify tool arguments
    - Add logging/auditing

    Data fields:
        tool_name: Name of the tool being called
        arguments: Tool arguments dictionary
        permission_mode: Current permission mode
    """

    def __init__(self, tool_name: str, arguments: Dict[str, Any], permission_mode: str, **context):
        super().__init__(
            event_type=EVENT_PRE_TOOL_USE,
            data={
                "tool_name": tool_name,
                "arguments": arguments,
                "permission_mode": permission_mode,
            },
            context=context,
        )

    @property
    def tool_name(self) -> str:
        return self.data["tool_name"]

    @property
    def arguments(self) -> Dict[str, Any]:
        return self.data["arguments"]

    @property
    def permission_mode(self) -> str:
        return self.data["permission_mode"]


@dataclass
class PostToolUseEvent(HookEvent):
    """
    Event fired after a tool is executed.

    This event allows hooks to:
    - Process tool results
    - Log execution outcomes
    - Modify results before they're added to conversation
    - Track metrics

    Data fields:
        tool_name: Name of the tool that was called
        arguments: Tool arguments that were used
        result: Tool execution result
        success: Whether the tool succeeded
        duration_ms: Execution duration in milliseconds (if available)
    """

    def __init__(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        success: bool,
        duration_ms: Optional[float] = None,
        **context,
    ):
        super().__init__(
            event_type=EVENT_POST_TOOL_USE,
            data={
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "success": success,
                "duration_ms": duration_ms,
            },
            context=context,
        )

    @property
    def tool_name(self) -> str:
        return self.data["tool_name"]

    @property
    def arguments(self) -> Dict[str, Any]:
        return self.data["arguments"]

    @property
    def result(self) -> Dict[str, Any]:
        return self.data["result"]

    @property
    def success(self) -> bool:
        return self.data["success"]

    @property
    def duration_ms(self) -> Optional[float]:
        return self.data.get("duration_ms")


@dataclass
class StopEvent(HookEvent):
    """
    Event fired to decide whether the agent should stop.

    This event allows hooks to:
    - Implement custom stopping conditions
    - Override default stopping behavior
    - Add cleanup logic before stopping

    Data fields:
        iteration: Current iteration number
        last_response: The last assistant response
        has_tool_calls: Whether the last response had tool calls
        max_iterations: Maximum allowed iterations
    """

    def __init__(
        self,
        iteration: int,
        last_response: Dict[str, Any],
        has_tool_calls: bool,
        max_iterations: int,
        **context,
    ):
        super().__init__(
            event_type=EVENT_STOP,
            data={
                "iteration": iteration,
                "last_response": last_response,
                "has_tool_calls": has_tool_calls,
                "max_iterations": max_iterations,
            },
            context=context,
        )

    @property
    def iteration(self) -> int:
        return self.data["iteration"]

    @property
    def last_response(self) -> Dict[str, Any]:
        return self.data["last_response"]

    @property
    def has_tool_calls(self) -> bool:
        return self.data["has_tool_calls"]

    @property
    def max_iterations(self) -> int:
        return self.data["max_iterations"]


@dataclass
class UserPromptSubmitEvent(HookEvent):
    """
    Event fired when a user submits a prompt.

    This event allows hooks to:
    - Validate user input
    - Modify prompts before processing
    - Add context or instructions
    - Block certain inputs

    Data fields:
        prompt: The user's prompt text
        conversation_length: Current conversation history length
    """

    def __init__(self, prompt: str, conversation_length: int, **context):
        super().__init__(
            event_type=EVENT_USER_PROMPT_SUBMIT,
            data={
                "prompt": prompt,
                "conversation_length": conversation_length,
            },
            context=context,
        )

    @property
    def prompt(self) -> str:
        return self.data["prompt"]

    @property
    def conversation_length(self) -> int:
        return self.data["conversation_length"]


@dataclass
class SessionStartEvent(HookEvent):
    """
    Event fired when a new session starts.

    This event allows hooks to:
    - Initialize session-specific state
    - Load session configuration
    - Set up logging

    Data fields:
        model: Model being used
        project_dir: Project directory path
        permission_mode: Permission mode
        config: Agent configuration dictionary
    """

    def __init__(
        self,
        model: str,
        project_dir: str,
        permission_mode: str,
        config: Optional[Dict[str, Any]] = None,
        **context,
    ):
        super().__init__(
            event_type=EVENT_SESSION_START,
            data={
                "model": model,
                "project_dir": project_dir,
                "permission_mode": permission_mode,
                "config": config or {},
            },
            context=context,
        )

    @property
    def model(self) -> str:
        return self.data["model"]

    @property
    def project_dir(self) -> str:
        return self.data["project_dir"]

    @property
    def permission_mode(self) -> str:
        return self.data["permission_mode"]

    @property
    def config(self) -> Dict[str, Any]:
        return self.data["config"]


@dataclass
class SessionEndEvent(HookEvent):
    """
    Event fired when a session ends.

    This event allows hooks to:
    - Clean up resources
    - Save session state
    - Log session summary

    Data fields:
        model: Model that was used
        project_dir: Project directory path
        messages_count: Total messages in session
        tools_used: List of tools used during session
    """

    def __init__(
        self,
        model: str,
        project_dir: str,
        messages_count: int,
        tools_used: Optional[List[str]] = None,
        **context,
    ):
        super().__init__(
            event_type=EVENT_SESSION_END,
            data={
                "model": model,
                "project_dir": project_dir,
                "messages_count": messages_count,
                "tools_used": tools_used or [],
            },
            context=context,
        )

    @property
    def model(self) -> str:
        return self.data["model"]

    @property
    def project_dir(self) -> str:
        return self.data["project_dir"]

    @property
    def messages_count(self) -> int:
        return self.data["messages_count"]

    @property
    def tools_used(self) -> List[str]:
        return self.data["tools_used"]
