"""Context window management and conversation history optimization"""

from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

# Cache for encodings to avoid recreating them
_ENCODING_CACHE = {}


def get_encoding_for_model(model: str) -> Optional[Any]:
    """
    Get appropriate tiktoken encoding for a model.
    
    Args:
        model: Model name
        
    Returns:
        tiktoken.Encoding or None if not available
    """
    if not TIKTOKEN_AVAILABLE:
        return None
        
    # Check cache first
    if model in _ENCODING_CACHE:
        return _ENCODING_CACHE[model]
    
    try:
        # Try to get encoding directly for the model
        # This works for OpenAI models
        encoding = tiktoken.encoding_for_model(model)
        _ENCODING_CACHE[model] = encoding
        return encoding
    except (KeyError, ValueError):
        # Model not found in tiktoken's registry
        # Map model families to appropriate encodings
        model_lower = model.lower()
        
        # Determine encoding based on model family
        if any(prefix in model_lower for prefix in ["claude-", "anthropic"]):
            # Claude models - Anthropic uses different tokenizer
            # cl100k_base is a reasonable approximation for modern Claude models
            encoding_name = "cl100k_base"
        elif any(prefix in model_lower for prefix in ["deepseek-"]):
            # DeepSeek models use OpenAI-compatible tokenizer
            encoding_name = "cl100k_base"
        elif any(prefix in model_lower for prefix in ["llama", "mistral", "mixtral", "codestral", "qwen"]):
            # Llama/Mistral family - these use SentencePiece tokenizers
            # o200k_base is a reasonable approximation for modern models
            try:
                encoding_name = "o200k_base"
            except KeyError:
                encoding_name = "cl100k_base"
        elif any(prefix in model_lower for prefix in ["command-r", "command-r-plus"]):
            # Cohere models - use cl100k_base as approximation
            encoding_name = "cl100k_base"
        elif any(prefix in model_lower for prefix in ["gemini"]):
            # Gemini models - Google's tokenizer, cl100k_base approximation
            encoding_name = "cl100k_base"
        else:
            # Default to cl100k_base for unknown models
            encoding_name = "cl100k_base"
        
        try:
            encoding = tiktoken.get_encoding(encoding_name)
            _ENCODING_CACHE[model] = encoding
            return encoding
        except Exception as e:
            logger.debug(f"Failed to get encoding {encoding_name} for model {model}: {e}")
            return None


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
    total_tokens = sum(
        count_message_tokens(msg, model) for msg in conversation_history
    )

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
        # Truncate: keep only recent messages
        recent_messages = other_messages[-keep_recent:]

    # Optionally summarize old messages (future enhancement)
    # For now, just drop them

    if system_msg:
        return [system_msg] + recent_messages
    return recent_messages



