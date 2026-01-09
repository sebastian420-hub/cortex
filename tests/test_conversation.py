"""Tests for conversation management"""

import pytest
from cortex.core.conversation import ConversationManager
from cortex.core.context import estimate_tokens, truncate_history


def test_conversation_manager():
    """Test ConversationManager basic functionality"""
    manager = ConversationManager(
        system_prompt="You are a helpful assistant.",
        max_tokens=1000,
        keep_recent=5
    )
    
    manager.add_user_message("Hello")
    manager.add_assistant_message("Hi there!")
    
    history = manager.get_history()
    assert len(history) == 3  # system + user + assistant
    assert history[0]["role"] == "system"
    assert history[1]["role"] == "user"
    assert history[2]["role"] == "assistant"


def test_conversation_clear():
    """Test clearing conversation"""
    manager = ConversationManager(
        system_prompt="You are a helpful assistant.",
        max_tokens=1000
    )
    
    manager.add_user_message("Hello")
    manager.clear(keep_system=False)
    
    history = manager.get_history()
    assert len(history) == 0


def test_conversation_clear_keep_system():
    """Test clearing conversation while keeping system message"""
    manager = ConversationManager(
        system_prompt="You are a helpful assistant.",
        max_tokens=1000
    )
    
    manager.add_user_message("Hello")
    manager.clear(keep_system=True)
    
    history = manager.get_history()
    assert len(history) == 1
    assert history[0]["role"] == "system"


def test_estimate_tokens():
    """Test token estimation"""
    text = "Hello, world! " * 10  # ~130 characters
    tokens = estimate_tokens(text)
    assert tokens > 0
    assert tokens < len(text)  # Should be less than character count


def test_truncate_history():
    """Test history truncation"""
    history = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Message 1"},
        {"role": "assistant", "content": "Response 1"},
    ]
    
    # Should not truncate if under limit
    result = truncate_history(history, max_tokens=10000)
    assert len(result) == len(history)
    
    # Should truncate if over limit
    large_history = [
        {"role": "system", "content": "System prompt"},
    ] + [
        {"role": "user", "content": "X" * 10000},
        {"role": "assistant", "content": "Y" * 10000},
    ] * 10
    
    result = truncate_history(large_history, max_tokens=1000, keep_recent=2)
    assert len(result) < len(large_history)
    assert result[0]["role"] == "system"  # System message kept

