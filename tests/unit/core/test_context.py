"""
Unit tests for context management module (cortex/core/context.py).
"""

import json
from unittest.mock import patch, MagicMock
import pytest

from cortex.core.context import (
    estimate_tokens,
    truncate_history,
    get_conversation_tokens,
    TIKTOKEN_AVAILABLE
)


class TestEstimateTokens:
    """Test token estimation functionality."""
    
    def test_estimate_tokens_with_tiktoken_available(self):
        """Test token estimation when tiktoken is available."""
        test_text = "Hello, world! This is a test."
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', True):
            with patch('cortex.core.context.tiktoken') as mock_tiktoken:
                mock_encoding = MagicMock()
                mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
                mock_tiktoken.encoding_for_model.return_value = mock_encoding
                
                token_count = estimate_tokens(test_text, model="gpt-4")
                
                mock_tiktoken.encoding_for_model.assert_called_once_with("gpt-4")
                mock_encoding.encode.assert_called_once_with(test_text)
                assert token_count == 5
    
    def test_estimate_tokens_with_tiktoken_model_not_found(self):
        """Test token estimation when model not found in tiktoken."""
        test_text = "Hello, world!"
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', True):
            with patch('cortex.core.context.tiktoken') as mock_tiktoken:
                # Simulate KeyError for encoding_for_model
                mock_tiktoken.encoding_for_model.side_effect = KeyError("Model not found")
                mock_encoding = MagicMock()
                mock_encoding.encode.return_value = [1, 2, 3]
                mock_tiktoken.get_encoding.return_value = mock_encoding
                
                token_count = estimate_tokens(test_text, model="unknown-model")
                
                mock_tiktoken.encoding_for_model.assert_called_once_with("unknown-model")
                mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")
                mock_encoding.encode.assert_called_once_with(test_text)
                assert token_count == 3
    
    def test_estimate_tokens_with_tiktoken_fallback(self):
        """Test token estimation when tiktoken fails completely."""
        test_text = "Hello, world!"  # 13 characters
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', True):
            with patch('cortex.core.context.tiktoken') as mock_tiktoken:
                # Simulate multiple failures
                mock_tiktoken.encoding_for_model.side_effect = KeyError("Model not found")
                mock_tiktoken.get_encoding.side_effect = ValueError("Encoding not found")
                
                token_count = estimate_tokens(test_text, model="unknown")
                
                # Should fall back to character count / 4
                assert token_count == len(test_text) // 4  # 13 // 4 = 3
    
    def test_estimate_tokens_without_tiktoken(self):
        """Test token estimation when tiktoken is not installed."""
        test_text = "Hello, world! This is a longer test."  # 37 characters
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = estimate_tokens(test_text, model="gpt-4")
            
            # Should use fallback approximation
            assert token_count == len(test_text) // 4  # 37 // 4 = 9
    
    def test_estimate_tokens_empty_string(self):
        """Test token estimation with empty string."""
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = estimate_tokens("", model="gpt-4")
            assert token_count == 0


class TestTruncateHistory:
    """Test conversation history truncation functionality."""
    
    @pytest.fixture
    def sample_conversation(self):
        """Create a sample conversation history for testing."""
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there! How can I help you?"},
            {"role": "user", "content": "Can you write a function?"},
            {"role": "assistant", "content": "Sure, what language?"},
            {"role": "user", "content": "Python please."},
            {"role": "assistant", "content": "Here's a simple function."},
            {"role": "user", "content": "Thanks!"},
            {"role": "assistant", "content": "You're welcome!"},
        ]
    
    def test_truncate_history_within_limit(self, sample_conversation):
        """Test truncation when history is within token limit."""
        # Mock estimate_tokens to return low counts
        with patch('cortex.core.context.estimate_tokens', return_value=100):
            truncated = truncate_history(
                sample_conversation,
                max_tokens=1000,
                keep_system=True,
                keep_recent=5
            )
            
            # Should return original history unchanged
            assert truncated == sample_conversation
    
    def test_truncate_history_exceeds_limit(self, sample_conversation):
        """Test truncation when history exceeds token limit."""
        # Mock estimate_tokens to return high counts
        with patch('cortex.core.context.estimate_tokens', return_value=1000):
            truncated = truncate_history(
                sample_conversation,
                max_tokens=500,
                keep_system=True,
                keep_recent=3
            )
            
            # Should keep system message and recent messages
            assert len(truncated) == 4  # system + 3 recent
            assert truncated[0] == sample_conversation[0]  # system message
            
            # Recent messages should be the last 3 (excluding system)
            recent_non_system = sample_conversation[-3:]
            assert truncated[1:] == recent_non_system
    
    def test_truncate_history_no_system_message(self, sample_conversation):
        """Test truncation when there's no system message."""
        # Remove system message
        conversation_without_system = sample_conversation[1:]
        
        with patch('cortex.core.context.estimate_tokens', return_value=1000):
            truncated = truncate_history(
                conversation_without_system,
                max_tokens=500,
                keep_system=True,  # Should have no effect
                keep_recent=2
            )
            
            # Should keep only recent messages
            assert len(truncated) == 2
            assert truncated == conversation_without_system[-2:]
    
    def test_truncate_history_disable_system_preservation(self, sample_conversation):
        """Test truncation with system preservation disabled."""
        with patch('cortex.core.context.estimate_tokens', return_value=1000):
            truncated = truncate_history(
                sample_conversation,
                max_tokens=500,
                keep_system=False,
                keep_recent=3
            )
            
            # Should not preserve system message
            assert len(truncated) == 3
            assert truncated == sample_conversation[-3:]
    
    def test_truncate_history_empty(self):
        """Test truncation with empty history."""
        truncated = truncate_history([], max_tokens=1000)
        assert truncated == []
    
    def test_truncate_history_smaller_than_keep_recent(self, sample_conversation):
        """Test when conversation has fewer messages than keep_recent."""
        small_conversation = sample_conversation[:3]  # 3 messages
        
        with patch('cortex.core.context.estimate_tokens', return_value=1000):
            truncated = truncate_history(
                small_conversation,
                max_tokens=500,
                keep_system=True,
                keep_recent=10  # Larger than conversation size
            )
            
            # Should return entire conversation
            assert truncated == small_conversation
    
    def test_truncate_history_keep_recent_zero(self, sample_conversation):
        """Test truncation with keep_recent=0."""
        with patch('cortex.core.context.estimate_tokens', return_value=1000):
            truncated = truncate_history(
                sample_conversation,
                max_tokens=500,
                keep_system=True,
                keep_recent=0
            )
            
            # Should keep only system message if keep_system=True
            assert len(truncated) == 1
            assert truncated[0] == sample_conversation[0]


class TestGetConversationTokens:
    """Test conversation token counting functionality."""
    
    def test_get_conversation_tokens(self):
        """Test token counting for conversation history."""
        conversation = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        
        # Mock estimate_tokens to return known values
        with patch('cortex.core.context.estimate_tokens') as mock_estimate:
            mock_estimate.side_effect = [50, 60]
            
            token_count = get_conversation_tokens(conversation, model="gpt-4")
            
            # Should call estimate_tokens for each message
            assert mock_estimate.call_count == 2
            assert token_count == 110
    
    def test_get_conversation_tokens_empty(self):
        """Test token counting with empty conversation."""
        token_count = get_conversation_tokens([], model="gpt-4")
        assert token_count == 0
    
    def test_get_conversation_tokens_with_complex_messages(self):
        """Test token counting with complex message structures."""
        conversation = [
            {
                "role": "user",
                "content": "Hello",
                "tool_calls": [{"function": {"name": "test", "arguments": "{}"}}]
            }
        ]
        
        with patch('cortex.core.context.estimate_tokens', return_value=75):
            token_count = get_conversation_tokens(conversation, model="gpt-4")
            assert token_count == 75


class TestModuleConfiguration:
    """Test module-level configuration and constants."""
    
    def test_tiktoken_availability(self):
        """Test that TIKTOKEN_AVAILABLE is a boolean."""
        assert isinstance(TIKTOKEN_AVAILABLE, bool)
        
        # It should be either True or False depending on installation
        # We don't care which, just that it's defined
        assert TIKTOKEN_AVAILABLE in (True, False)