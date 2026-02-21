"""Model-specific context window limits and detection.

This module provides utilities for determining the appropriate context window
size based on the model being used. Different models have different context
limits, and this helps optimize memory usage and prevent overflow.
"""

import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Model context window limits (in tokens)
# These are conservative estimates to leave room for tool definitions and overhead
MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    # OpenAI Models
    "gpt-4": 8000,
    "gpt-4-turbo": 128000,
    "gpt-4-turbo-preview": 128000,
    "gpt-4-1106-preview": 128000,
    "gpt-4-0125-preview": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-3.5-turbo": 16000,
    "gpt-3.5-turbo-16k": 16000,
    # Anthropic Claude Models
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-3-5-sonnet": 200000,
    "claude-3-5-haiku": 200000,
    "claude-2.1": 200000,
    "claude-2": 100000,
    "claude-instant": 100000,
    # DeepSeek Models
    "deepseek-chat": 64000,
    "deepseek-coder": 64000,
    "deepseek-reasoner": 64000,
    # Moonshot AI Models (Kimi)
    "moonshot-v1": 200000,
    "kimi-k1": 200000,
    "kimi-k2": 200000,
    "kimi-k2.5": 200000,
    "moonshotai/kimi-k2.5": 200000,
    # MiMo Models (OpenRouter)
    "mimo-v2": 200000,
    "mimo-v2-flash": 200000,
    # Ollama Models (local)
    "llama3.2": 128000,
    "llama3.1": 128000,
    "llama3": 8000,
    "llama2": 4096,
    "mistral": 8000,
    "mixtral": 32000,
    "codellama": 16000,
    "qwen2.5": 32000,
    "qwen2": 32000,
    "phi3": 128000,
    "gemma2": 8000,
    # Google Models
    "gemini-pro": 32000,
    "gemini-1.5-pro": 1000000,  # 1M context!
    "gemini-1.5-flash": 1000000,
}

# Pattern-based detection for models not in exact mapping
MODEL_PATTERNS = [
    # Claude patterns
    (re.compile(r"claude-3.*opus", re.I), 200000),
    (re.compile(r"claude-3.*sonnet", re.I), 200000),
    (re.compile(r"claude-3.*haiku", re.I), 200000),
    (re.compile(r"claude-2", re.I), 100000),
    # GPT patterns
    (re.compile(r"gpt-4.*turbo", re.I), 128000),
    (re.compile(r"gpt-4o", re.I), 128000),
    (re.compile(r"gpt-4(?!o)", re.I), 8000),  # gpt-4 without 'o'
    (re.compile(r"gpt-3.5.*16k", re.I), 16000),
    (re.compile(r"gpt-3.5", re.I), 16000),
    # DeepSeek patterns
    (re.compile(r"deepseek", re.I), 64000),
    # Kimi/Moonshot patterns
    (re.compile(r"kimi", re.I), 200000),
    (re.compile(r"moonshot", re.I), 200000),
    # MiMo patterns
    (re.compile(r"mimo", re.I), 200000),
    # Llama patterns
    (re.compile(r"llama3\.2", re.I), 128000),
    (re.compile(r"llama3\.1", re.I), 128000),
    (re.compile(r"llama3", re.I), 8000),
    (re.compile(r"llama2", re.I), 4096),
    # Gemini patterns
    (re.compile(r"gemini-1\.5", re.I), 1000000),
    (re.compile(r"gemini", re.I), 32000),
    # Mistral patterns
    (re.compile(r"mixtral", re.I), 32000),
    (re.compile(r"mistral", re.I), 8000),
    # Qwen patterns
    (re.compile(r"qwen", re.I), 32000),
]

# Default fallback limit (conservative)
DEFAULT_CONTEXT_LIMIT = 100000


def get_model_context_limit(model_name: str) -> int:
    """
    Get the context window limit for a specific model.

    Args:
        model_name: Name of the model (e.g., "gpt-4", "claude-3-opus")

    Returns:
        Context limit in tokens
    """
    if not model_name:
        return DEFAULT_CONTEXT_LIMIT

    # Normalize model name
    model_lower = model_name.lower().strip()

    # Try exact match first
    if model_lower in MODEL_CONTEXT_LIMITS:
        limit = MODEL_CONTEXT_LIMITS[model_lower]
        logger.debug(f"Context limit for {model_name}: {limit:,} tokens (exact match)")
        return limit

    # Try without provider prefix (e.g., "openai/gpt-4" -> "gpt-4")
    if "/" in model_lower:
        model_without_prefix = model_lower.split("/", 1)[1]
        if model_without_prefix in MODEL_CONTEXT_LIMITS:
            limit = MODEL_CONTEXT_LIMITS[model_without_prefix]
            logger.debug(f"Context limit for {model_name}: {limit:,} tokens (without prefix)")
            return limit

    # Try pattern matching
    for pattern, limit in MODEL_PATTERNS:
        if pattern.search(model_name):
            logger.debug(f"Context limit for {model_name}: {limit:,} tokens (pattern match)")
            return limit

    # Fallback to default
    logger.info(
        f"No context limit found for model '{model_name}', using default: {DEFAULT_CONTEXT_LIMIT:,} tokens"  # noqa: E501
    )
    return DEFAULT_CONTEXT_LIMIT


def get_recommended_max_tokens(model_name: str, safety_margin: float = 0.8) -> int:
    """
    Get recommended max_tokens setting for a model with safety margin.

    The safety margin ensures we don't use the full context window, leaving
    room for tool definitions, system prompt overhead, and response generation.

    Args:
        model_name: Name of the model
        safety_margin: Fraction of context to use (0.8 = 80%)

    Returns:
        Recommended max_tokens value
    """
    full_limit = get_model_context_limit(model_name)
    recommended = int(full_limit * safety_margin)

    logger.debug(
        f"Recommended max_tokens for {model_name}: {recommended:,} "
        f"({safety_margin*100:.0f}% of {full_limit:,})"
    )

    return recommended


def get_model_context_info(model_name: str) -> Dict[str, Any]:
    """
    Get comprehensive context information for a model.

    Args:
        model_name: Name of the model

    Returns:
        Dictionary with context information
    """
    full_limit = get_model_context_limit(model_name)
    recommended_80 = get_recommended_max_tokens(model_name, 0.8)
    recommended_90 = get_recommended_max_tokens(model_name, 0.9)

    return {
        "model_name": model_name,
        "full_context_limit": full_limit,
        "recommended_max_tokens_80": recommended_80,  # Conservative (80%)
        "recommended_max_tokens_90": recommended_90,  # Aggressive (90%)
        "is_large_context": full_limit >= 100000,  # 100K+ tokens
        "is_mega_context": full_limit >= 500000,  # 500K+ tokens (like Gemini 1.5)
    }


def auto_configure_context(model_name: str, user_max_tokens: Optional[int] = None) -> int:
    """
    Automatically configure optimal context window size for a model.

    If user provides explicit max_tokens, validates it against model limits.
    Otherwise, uses recommended settings based on model capabilities.

    Args:
        model_name: Name of the model
        user_max_tokens: User-specified max_tokens (optional)

    Returns:
        Configured max_tokens value
    """
    model_limit = get_model_context_limit(model_name)

    if user_max_tokens is not None:
        # User specified a value - validate it
        if user_max_tokens > model_limit:
            logger.warning(
                f"User-specified max_tokens ({user_max_tokens:,}) exceeds model limit "
                f"({model_limit:,}). Capping at model limit."
            )
            return model_limit
        else:
            logger.debug(
                f"Using user-specified max_tokens: {user_max_tokens:,} "
                f"(model limit: {model_limit:,})"
            )
            return user_max_tokens

    # Auto-configure based on model
    # For large context models (100K+), use 90% to maximize utility
    # For smaller models, use 80% to be more conservative
    if model_limit >= 100000:
        recommended = get_recommended_max_tokens(model_name, 0.9)
        logger.info(
            f"Auto-configured large context model '{model_name}': {recommended:,} tokens "
            f"(90% of {model_limit:,})"
        )
    else:
        recommended = get_recommended_max_tokens(model_name, 0.8)
        logger.info(
            f"Auto-configured standard context model '{model_name}': {recommended:,} tokens "
            f"(80% of {model_limit:,})"
        )

    return recommended
