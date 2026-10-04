"""Context window management and conversation history optimization"""

from typing import List, Dict, Any, Optional
import json
import logging
import os

from ..utils.message_validation import tail_start

logger = logging.getLogger(__name__)

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

# Loaded tiktoken encodings by encoding name. A *failed* load is cached too (as None): tiktoken
# downloads its vocabulary on first use, so on an offline machine every token count used to
# retry that download. Now it is attempted once per process.
_ENCODING_CACHE: Dict[str, Optional[Any]] = {}

# Approximate encodings for model families that tiktoken does not know by name.
_FAMILY_ENCODINGS = (
    (("claude-", "anthropic"), "cl100k_base"),
    (("deepseek-",), "cl100k_base"),
    (("llama", "mistral", "mixtral", "codestral", "qwen"), "o200k_base"),
    (("command-r", "command-r-plus"), "cl100k_base"),
    (("gemini",), "cl100k_base"),
)
_DEFAULT_ENCODING = "cl100k_base"


def offline_mode() -> bool:
    """True when CORTEX_OFFLINE is set: never try to download tokenizer data."""
    return os.environ.get("CORTEX_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


def _encoding_name_for(model: str) -> str:
    """Name of the tiktoken encoding to use for ``model`` (no network access)."""
    try:
        # Exact answer for models tiktoken knows (the OpenAI models).
        return tiktoken.encoding_name_for_model(model)
    except (KeyError, ValueError):
        pass
    model_lower = model.lower()
    for prefixes, encoding_name in _FAMILY_ENCODINGS:
        if any(prefix in model_lower for prefix in prefixes):
            return encoding_name
    return _DEFAULT_ENCODING


def _load_encoding(encoding_name: str) -> Optional[Any]:
    """Load an encoding once; remember a failure so it is not retried."""
    if encoding_name in _ENCODING_CACHE:
        return _ENCODING_CACHE[encoding_name]
    try:
        encoding = tiktoken.get_encoding(encoding_name)
    except Exception as e:  # network down, no cache, unknown name: fall back to approximation
        logger.debug(f"Tokenizer {encoding_name} unavailable, using approximation: {e}")
        encoding = None
    _ENCODING_CACHE[encoding_name] = encoding
    return encoding


def get_encoding_for_model(model: str) -> Optional[Any]:
    """
    Get appropriate tiktoken encoding for a model.

    Args:
        model: Model name

    Returns:
        tiktoken.Encoding, or None if tiktoken is missing, offline mode is on, or the
        vocabulary could not be loaded. Callers then fall back to a character estimate.
    """
    if not TIKTOKEN_AVAILABLE or offline_mode():
        return None
    return _load_encoding(_encoding_name_for(model))


def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Estimate token count using tiktoken if available, fallback to approximation.

    This function provides accurate token counting for supported models and
    reasonable approximations for others.

    Args:
        text: Text to estimate (string or JSON-serializable object)
        model: Model name for tokenizer (default: gpt-4)

    Returns:
        Estimated token count
    """
    # Convert non-string text to JSON string for token counting
    if not isinstance(text, str):
        try:
            text = json.dumps(text, default=str)
        except (TypeError, ValueError):
            text = str(text)

    # Try native Rust tokenizer first (Phase 2 hybrid)
    try:
        from .feature_flags import FeatureFlag, FeatureManager

        fm = FeatureManager.get_instance()
        if fm.is_enabled(FeatureFlag.RUST_TOKENIZER):
            from ..native import native_count_tokens, NATIVE_AVAILABLE

            if NATIVE_AVAILABLE and native_count_tokens is not None:
                try:
                    return native_count_tokens(text, model)
                except Exception:
                    pass
    except ImportError:
        pass

    if TIKTOKEN_AVAILABLE:
        encoding = get_encoding_for_model(model)
        if encoding is not None:
            try:
                return len(encoding.encode(text))
            except Exception as e:
                logger.debug(f"Token encoding failed for model {model}: {e}")
                # Fall through to approximation

    # Fallback: character-based approximation with model-specific factors
    model_lower = model.lower()

    # Different models have different average characters per token
    if any(prefix in model_lower for prefix in ["claude-", "anthropic"]):
        # Claude tokens are roughly 3.5 characters each on average
        chars_per_token = 3.5
    elif any(prefix in model_lower for prefix in ["llama", "mistral", "mixtral", "codellama"]):
        # Llama/Mistral family tokens are roughly 3.8 characters each
        chars_per_token = 3.8
    elif any(prefix in model_lower for prefix in ["qwen"]):
        # Qwen tokens are roughly 4.0 characters each
        chars_per_token = 4.0
    elif any(prefix in model_lower for prefix in ["command-r", "command-r-plus"]):
        # Cohere tokens are roughly 3.7 characters each
        chars_per_token = 3.7
    elif any(prefix in model_lower for prefix in ["gemini"]):
        # Gemini tokens are roughly 4.0 characters each
        chars_per_token = 4.0
    else:
        # Default for GPT, DeepSeek, and unknown models
        chars_per_token = 4.0

    # Ensure at least 1 token for non-empty text
    if len(text) == 0:
        return 0
    return max(1, int(len(text) / chars_per_token))


def count_message_tokens(message: Dict[str, Any], model: str = "gpt-4") -> int:
    """
    Count tokens in a message dictionary, including role, content, and tool calls.

    This provides a more accurate token count than just counting content,
    as it includes the message structure overhead.

    Args:
        message: Message dictionary with role, content, etc.
        model: Model name for tokenizer

    Returns:
        Estimated token count for the entire message
    """
    # Base tokens for message structure
    # Different models have different overhead per message
    model_lower = model.lower()

    # Message overhead (role, etc.) - approximate values
    if any(prefix in model_lower for prefix in ["gpt-", "text-"]):
        # OpenAI models: ~3 tokens overhead for role
        overhead = 3
    elif any(prefix in model_lower for prefix in ["claude-", "anthropic"]):
        # Claude models: Anthropic has different message structure
        overhead = 4
    elif any(prefix in model_lower for prefix in ["llama", "mistral", "mixtral"]):
        # Llama/Mistral: Similar to OpenAI
        overhead = 3
    else:
        # Default overhead
        overhead = 3

    total_tokens = overhead

    # Add tokens for role
    role = message.get("role", "")
    if role:
        total_tokens += estimate_tokens(role, model)

    # Add tokens for content
    content = message.get("content", "")
    if content:
        if isinstance(content, list):
            # Handle multimodal content (list of content blocks)
            for block in content:
                if isinstance(block, dict):
                    # Text block
                    if block.get("type") == "text":
                        total_tokens += estimate_tokens(block.get("text", ""), model)
                    # Other block types (image, etc.) have token costs too
                    # For now, we'll approximate
                    else:
                        total_tokens += 100  # Approximate for non-text blocks
        else:
            total_tokens += estimate_tokens(content, model)

    # Add tokens for tool calls if present
    tool_calls = message.get("tool_calls")
    if tool_calls:
        # Each tool call has structure overhead
        for tool_call in tool_calls:
            # Tool call ID and type overhead
            total_tokens += 10
            # Function name
            if isinstance(tool_call, dict):
                function = tool_call.get("function", {})
                total_tokens += estimate_tokens(function.get("name", ""), model)
                total_tokens += estimate_tokens(function.get("arguments", ""), model)
            elif hasattr(tool_call, "function"):
                total_tokens += estimate_tokens(tool_call.function.name, model)
                total_tokens += estimate_tokens(tool_call.function.arguments, model)

    # Add tokens for tool call ID if present (for assistant messages with tool calls)
    tool_call_id = message.get("tool_call_id")
    if tool_call_id:
        total_tokens += estimate_tokens(tool_call_id, model)

    # Add tokens for name if present
    name = message.get("name")
    if name:
        total_tokens += estimate_tokens(name, model)

    return total_tokens


def get_conversation_tokens(
    conversation_history: List[Dict[str, Any]], model: str = "gpt-4"
) -> int:
    """
    Get estimated token count for conversation history.

    Uses count_message_tokens for accurate counting of message structures.

    Args:
        conversation_history: Conversation history
        model: Model name for tokenizer (default: gpt-4)

    Returns:
        Estimated token count
    """
    return sum(count_message_tokens(msg, model) for msg in conversation_history)


def truncate_history(
    conversation_history: List[Dict[str, Any]],
    max_tokens: int = 100000,
    keep_system: bool = True,
    keep_recent: int = 20,
    model: str = "gpt-4",
) -> List[Dict[str, Any]]:
    """
    Intelligently truncate conversation history when it exceeds token limit.

    Args:
        conversation_history: Full conversation history
        max_tokens: Maximum token limit
        keep_system: Whether to always keep system message
        keep_recent: Number of recent messages to keep

    Returns:
        Truncated conversation history
    """
    if not conversation_history:
        return []

    # Calculate total tokens using accurate message token counting
    total_tokens = sum(count_message_tokens(msg, model) for msg in conversation_history)

    # If under limit, return as-is
    if total_tokens <= max_tokens:
        return conversation_history

    # Separate system message
    system_msg = None
    if keep_system and conversation_history and conversation_history[0].get("role") == "system":
        system_msg = conversation_history[0]
        other_messages = conversation_history[1:]
    else:
        other_messages = conversation_history

    # Keep recent messages
    if keep_recent == 0:
        # Keep zero recent messages
        recent_messages = []
    elif len(other_messages) <= keep_recent:
        # If we can fit everything, just return
        if system_msg:
            return [system_msg] + other_messages
        return other_messages
    else:
        # Truncate: keep only recent messages, without cutting a tool call from its result
        recent_messages = other_messages[tail_start(other_messages, keep_recent) :]

    # Optionally summarize old messages (future enhancement)
    # For now, just drop them

    if system_msg:
        return [system_msg] + recent_messages
    return recent_messages
