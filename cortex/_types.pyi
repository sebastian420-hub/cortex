"""Type stubs for Cortex.

This file provides type definitions for complex types used across the codebase.
"""

from typing import TypedDict, Optional, List, Dict, Any, Literal

# Error Types
ErrorTypeValue = Literal[
    "validation",
    "security",
    "not_found",
    "execution",
    "timeout",
    "permission_denied",
]

# Tool Response Types
class SuccessResponse(TypedDict, total=False):
    success: Literal[True]
    # Additional fields depend on the tool

class ErrorResponse(TypedDict, total=False):
    success: Literal[False]
    error: str
    error_type: ErrorTypeValue
    retryable: bool
    hint: str
    context: Dict[str, Any]

class PermissionDenialResponse(TypedDict):
    success: Literal[False]
    error: str
    error_type: Literal["permission_denied"]
    permission_denied: Literal[True]
    action: str

ToolResponse = SuccessResponse | ErrorResponse | PermissionDenialResponse

# Message Types
class UserMessage(TypedDict):
    role: Literal["user"]
    content: str

class AssistantMessage(TypedDict, total=False):
    role: Literal["assistant"]
    content: str
    tool_calls: List[Dict[str, Any]]

class ToolResultMessage(TypedDict):
    role: Literal["tool"]
    tool_use_id: str
    content: str

Message = UserMessage | AssistantMessage | ToolResultMessage

# Tool Schema Types
class ToolParameter(TypedDict, total=False):
    type: str
    description: str
    enum: List[str]
    default: Any

class ToolParameters(TypedDict, total=False):
    type: Literal["object"]
    properties: Dict[str, ToolParameter]
    required: List[str]

class ToolFunction(TypedDict):
    name: str
    description: str
    parameters: ToolParameters

class ToolSchema(TypedDict):
    type: Literal["function"]
    function: ToolFunction

# Provider Response Types
class ProviderUsage(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    total_tokens: int

class ProviderMessage(TypedDict, total=False):
    role: str
    content: str
    tool_calls: List[Dict[str, Any]]

class ProviderResponse(TypedDict, total=False):
    message: ProviderMessage
    stop_reason: str
    usage: ProviderUsage

# Config Types
class ParallelConfig(TypedDict, total=False):
    enabled: bool
    max_workers: int
    batch_size: int

class FileCacheConfig(TypedDict, total=False):
    enabled: bool
    max_entries: int
    max_size_mb: float

class TimeoutConfig(TypedDict, total=False):
    default: int
    network: int
    long: int
    git: int
    search: int

class ToolsConfig(TypedDict, total=False):
    plugins: List[str]
    disabled: List[str]
    enabled: List[str]

# Routing Types
class RoutingDecision(TypedDict, total=False):
    model_name: str
    confidence: float
    reasoning: Dict[str, Any]

# Cache Types
class CacheStats(TypedDict):
    enabled: bool
    entries: int
    max_entries: int
    size_bytes: int
    size_mb: float
    max_size_mb: float
    hits: int
    misses: int
    hit_rate: float

# Batch Execution Types
class BatchStats(TypedDict):
    results: List[Dict[str, Any]]
    parallel_count: int
    serial_count: int
    total_time_ms: float
    parallel_time_ms: float
