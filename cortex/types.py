"""Type definitions for Cortex using TypedDict for better type safety."""

from typing import List, Optional, Any, Literal, Union
from typing_extensions import TypedDict, NotRequired


# ============ Tool Types ============


class ToolResult(TypedDict):
    """Standard tool result format returned by all tools."""

    success: bool
    error: NotRequired[str]
    error_type: NotRequired[
        Literal["permission", "not_found", "validation", "execution", "timeout", "security"]
    ]
    retryable: NotRequired[bool]
    permission_denied: NotRequired[bool]
    reason: NotRequired[str]
    data: NotRequired[dict]


class ToolCallFunction(TypedDict):
    """Tool call function specification from model response."""

    name: str
    arguments: str  # JSON string


class ToolCall(TypedDict):
    """Tool call from model response."""

    id: str
    type: Literal["function"]
    function: ToolCallFunction


class FunctionDefinition(TypedDict):
    """Function definition in tool schema."""

    name: str
    description: str
    parameters: dict


class ToolDefinition(TypedDict):
    """Tool definition for model (OpenAI function calling format)."""

    type: Literal["function"]
    function: FunctionDefinition


# ============ Message Types ============


class SystemMessage(TypedDict):
    """System message in conversation."""

    role: Literal["system"]
    content: str


class UserMessage(TypedDict):
    """User message in conversation."""

    role: Literal["user"]
    content: str


class AssistantMessage(TypedDict):
    """Assistant message in conversation."""

    role: Literal["assistant"]
    content: NotRequired[str]
    tool_calls: NotRequired[List[ToolCall]]
    reasoning_content: NotRequired[str]


class ToolMessage(TypedDict):
    """Tool result message in conversation."""

    role: Literal["tool"]
    tool_call_id: str
    content: str  # JSON string of tool result


# Union type for all message types
Message = Union[SystemMessage, UserMessage, AssistantMessage, ToolMessage]


# ============ Model Response Types ============


class ModelResponseMessage(TypedDict):
    """Message portion of model response."""

    content: NotRequired[str]
    tool_calls: NotRequired[List[ToolCall]]
    reasoning_content: NotRequired[str]


class ModelResponse(TypedDict):
    """Response from model provider."""

    message: ModelResponseMessage
    done: NotRequired[bool]
    model: NotRequired[str]


# ============ Hook Types ============


class HookResultData(TypedDict):
    """Modified data from hook execution."""

    tool_name: NotRequired[str]
    arguments: NotRequired[dict]
    prompt: NotRequired[str]
    result: NotRequired[dict]


class HookResult(TypedDict):
    """Result from hook execution."""

    action: Literal["continue", "skip", "modify", "abort"]
    message: NotRequired[str]
    modified_data: NotRequired[HookResultData]


# ============ Session Types ============


class SessionData(TypedDict):
    """Session persistence data structure."""

    session_name: str
    conversation_history: List[Message]
    model: str
    permission_mode: str
    project_dir: str
    created_at: str
    version: str
    metadata: NotRequired[dict]


class SessionMetadata(TypedDict):
    """Session metadata for listing sessions."""

    name: str
    created_at: str
    model: str
    project_dir: str


# ============ Config Types ============


class TimeoutConfig(TypedDict):
    """Timeout configuration for different operations."""

    default: int
    git: NotRequired[int]
    test: NotRequired[int]
    command: NotRequired[int]


class ErrorRecoveryConfig(TypedDict):
    """Error recovery configuration."""

    enable_smart_recovery: bool
    max_repeats: int
    stuck_threshold: NotRequired[int]
    buffer_size: NotRequired[int]
    recovery_strategy: NotRequired[Literal["suggest", "escalate", "continue"]]


class SessionRetentionConfig(TypedDict):
    """Session retention and cleanup configuration."""

    max_age_days: int
    max_count: int
    max_total_size_mb: NotRequired[int]
    cleanup_on_startup: NotRequired[bool]
    warn_on_truncation: NotRequired[bool]


# ============ Todo Types ============


class TodoItem(TypedDict):
    """A single todo item for task tracking."""

    content: str
    status: Literal["pending", "in_progress", "completed"]
    activeForm: str  # Present continuous form (e.g., "Running tests")


class TodoProgress(TypedDict):
    """Todo progress statistics."""

    total: int
    pending: int
    in_progress: int
    completed: int


# ============ Question Types ============


class QuestionOption(TypedDict):
    """An option for a structured question."""

    label: str
    description: str


class Question(TypedDict):
    """A structured question for user input."""

    question: str
    header: str  # Short label (max 12 chars)
    options: List[QuestionOption]
    multiSelect: NotRequired[bool]


class QuestionAnswer(TypedDict):
    """Answer to a structured question."""

    header: str
    selected: List[str]
    custom_input: NotRequired[str]


# ============ Subagent Types ============


class SubagentResultData(TypedDict):
    """Result from subagent execution."""

    agent_id: str
    agent_type: str
    success: bool
    result: str
    tool_calls_made: int
    tokens_used: int
    duration_ms: float
    error: NotRequired[str]


# ============ Context Types ============


class TruncationStats(TypedDict):
    """Statistics about context truncation."""

    truncation_count: int
    total_messages_removed: int
    current_message_count: int
    current_token_count: int
    max_tokens: int
    keep_recent: int


class SummaryChunk(TypedDict):
    """A summarized chunk of conversation history."""

    original_message_count: int
    original_token_count: int
    summary_token_count: int
    summary_content: str
    key_decisions: List[str]
    files_modified: List[str]
    errors_encountered: List[str]
    timestamp_start: str
    timestamp_end: str
