"""Context window management and conversation history optimization"""

from typing import List, Dict, Any
import json


def estimate_tokens(text: str) -> int:
    """
    Rough estimation of token count.
    Uses approximation: ~4 characters per token.
    
    Args:
        text: Text to estimate
        
    Returns:
        Estimated token count
    """
    return len(text) // 4


def truncate_history(
    conversation_history: List[Dict[str, Any]],
    max_tokens: int = 100000,
    keep_system: bool = True,
    keep_recent: int = 20
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
    
    # Calculate total tokens
    total_tokens = sum(
        estimate_tokens(json.dumps(msg, default=str))
        for msg in conversation_history
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
    if len(other_messages) <= keep_recent:
        # If we can fit everything, just return
        if system_msg:
            return [system_msg] + other_messages
        return other_messages
    
    # Truncate: keep system + recent messages
    recent_messages = other_messages[-keep_recent:]
    
    # Optionally summarize old messages (future enhancement)
    # For now, just drop them
    
    if system_msg:
        return [system_msg] + recent_messages
    return recent_messages


def get_conversation_tokens(conversation_history: List[Dict[str, Any]]) -> int:
    """
    Get estimated token count for conversation history.
    
    Args:
        conversation_history: Conversation history
        
    Returns:
        Estimated token count
    """
    return sum(
        estimate_tokens(json.dumps(msg, default=str))
        for msg in conversation_history
    )

