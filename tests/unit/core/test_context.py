"""
Unit tests for context management module (cortex/core/context.py).
"""

import json
from unittest.mock import patch, MagicMock
import pytest

from cortex.core.context import (
    estimate_tokens,
    count_message_tokens,
    truncate_history,
    get_conversation_tokens,
    TIKTOKEN_AVAILABLE
)


class TestEstimateTokens:
    """Test token estimation functionality."""
    
    def test_estimate_tokens_with_tiktoken_available(self):
        """Test token estimation when tiktoken is available."""
        test_text = "Hello, world! This is a test."

        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]

        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', True):
            with patch('cortex.core.context.get_encoding_for_model', return_value=mock_encoding) as mock_get_enc:
                token_count = estimate_tokens(test_text, model="gpt-4")

                mock_get_enc.assert_called_once_with("gpt-4")
                mock_encoding.encode.assert_called_once_with(test_text)
                assert token_count == 5
    
    def test_estimate_tokens_with_tiktoken_model_not_found(self):
        """Test token estimation when model not found in tiktoken."""
        test_text = "Hello, world!"
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', True):
            with patch('cortex.core.context.tiktoken', create=True) as mock_tiktoken:
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
            with patch('cortex.core.context.tiktoken', create=True) as mock_tiktoken:
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
        # Mock count_message_tokens to return low counts
        with patch('cortex.core.context.count_message_tokens', return_value=100):
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
        with patch('cortex.core.context.count_message_tokens', return_value=1000):
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
        
        with patch('cortex.core.context.count_message_tokens', return_value=1000):
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
        with patch('cortex.core.context.count_message_tokens', return_value=1000):
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
        
        with patch('cortex.core.context.count_message_tokens', return_value=1000):
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
        with patch('cortex.core.context.count_message_tokens', return_value=1000):
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
        
        # Mock count_message_tokens to return known values
        with patch('cortex.core.context.count_message_tokens') as mock_count:
            mock_count.side_effect = [50, 60]
            
            token_count = get_conversation_tokens(conversation, model="gpt-4")
            
            # Should call count_message_tokens for each message
            assert mock_count.call_count == 2
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
        
        with patch('cortex.core.context.count_message_tokens', return_value=125):
            token_count = get_conversation_tokens(conversation, model="gpt-4")
            assert token_count == 125


class TestCountMessageTokens:
    """Test count_message_tokens functionality."""
    
    def test_count_message_tokens_basic_user_message(self):
        """Test token counting for a basic user message."""
        message = {
            "role": "user",
            "content": "Hello, how are you?"
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = count_message_tokens(message, model="gpt-4")
            # Base overhead (3) + role tokens + content tokens
            assert token_count >= 8  # Minimum should be overhead + content  # Minimum expected tokens
    
    def test_count_message_tokens_basic_assistant_message(self):
        """Test token counting for a basic assistant message."""
        message = {
            "role": "assistant",
            "content": "I'm doing well, thank you!"
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = count_message_tokens(message, model="gpt-4")
            assert token_count >= 8
    
    def test_count_message_tokens_with_system_role(self):
        """Test token counting with system role."""
        message = {
            "role": "system",
            "content": "You are a helpful assistant."
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = count_message_tokens(message, model="gpt-4")
            assert token_count >= 8
    
    def test_count_message_tokens_empty_content(self):
        """Test token counting with empty content."""
        message = {
            "role": "user",
            "content": ""
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = count_message_tokens(message, model="gpt-4")
            # Only overhead and role tokens
            assert token_count >= 3
    
    def test_count_message_tokens_multimodal_content(self):
        """Test token counting for multimodal content with text blocks."""
        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
            ]
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = count_message_tokens(message, model="gpt-4")
            # Text tokens + 100 for image block + overhead
            assert token_count >= 103
    
    def test_count_message_tokens_with_tool_calls(self):
        """Test token counting with tool calls."""
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "San Francisco"}'
                    }
                }
            ]
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = count_message_tokens(message, model="gpt-4")
            # Tool call overhead (10) + name + arguments + tool_call_id + content + role + base
            assert token_count >= 15
    
    def test_count_message_tokens_with_tool_call_id(self):
        """Test token counting for tool response message."""
        message = {
            "role": "tool",
            "content": "Sunny, 72°F",
            "tool_call_id": "call_abc123"
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = count_message_tokens(message, model="gpt-4")
            assert token_count >= 8
    
    def test_count_message_tokens_with_name(self):
        """Test token counting with name field."""
        message = {
            "role": "user",
            "content": "Hello",
            "name": "John"
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = count_message_tokens(message, model="gpt-4")
            assert token_count >= 6
    
    def test_count_message_tokens_different_models(self):
        """Test that different models have different overhead."""
        message = {
            "role": "user",
            "content": "Test"
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            gpt_token_count = count_message_tokens(message, model="gpt-4")
            claude_token_count = count_message_tokens(message, model="claude-3-5-sonnet-20240620")
            
            # Different models should have different overhead (3 for GPT, 4 for Claude)
            # Account for content token differences too
            assert gpt_token_count != claude_token_count
    
    def test_count_message_tokens_with_tiktoken(self):
        """Test count_message_tokens when tiktoken is available."""
        message = {
            "role": "user",
            "content": "Hello, world!"
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', True):
            with patch('cortex.core.context.tiktoken', create=True) as mock_tiktoken:
                mock_encoding = MagicMock()
                mock_encoding.encode.return_value = [1, 2, 3]  # 3 tokens
                mock_tiktoken.encoding_for_model.return_value = mock_encoding
                
                token_count = count_message_tokens(message, model="gpt-4")
                
                # Should have overhead + content tokens
                # Base overhead (3) + role tokens + content tokens (3)
                assert token_count >= 6
    
    def test_count_message_tokens_large_content(self):
        """Test token counting with large content."""
        message = {
            "role": "user",
            "content": "This is a longer message with multiple words. " * 10
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = count_message_tokens(message, model="gpt-4")
            assert token_count > 50
    
    def test_count_message_tokens_no_role(self):
        """Test token counting with missing role."""
        message = {
            "content": "Hello"
        }
        
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            token_count = count_message_tokens(message, model="gpt-4")
            # Only overhead + content
            assert token_count >= 4


class TestGetEncodingForModel:
    """Test get_encoding_for_model functionality."""
    
    def test_get_encoding_with_tiktoken_unavailable(self):
        """Test when tiktoken is not available."""
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', False):
            from cortex.core.context import get_encoding_for_model
            result = get_encoding_for_model("gpt-4")
            assert result is None
    
    def test_get_encoding_with_known_model(self):
        """Test getting encoding for a known model."""
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', True):
            with patch('cortex.core.context.tiktoken', create=True) as mock_tiktoken:
                mock_encoding = MagicMock()
                mock_tiktoken.encoding_for_model.return_value = mock_encoding
                
                from cortex.core.context import get_encoding_for_model, _ENCODING_CACHE
                
                # Clear cache for this specific model to ensure it's called
                if "gpt-4" in _ENCODING_CACHE:
                    del _ENCODING_CACHE["gpt-4"]
                
                result = get_encoding_for_model("gpt-4")
                
                assert result is not None
                mock_tiktoken.encoding_for_model.assert_called_once_with("gpt-4")
    
    def test_get_encoding_for_claude_model(self):
        """Test getting encoding for Claude model."""
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', True):
            with patch('cortex.core.context.tiktoken', create=True) as mock_tiktoken:
                mock_tiktoken.encoding_for_model.side_effect = KeyError("Model not found")
                mock_encoding = MagicMock()
                mock_tiktoken.get_encoding.return_value = mock_encoding
                
                from cortex.core.context import get_encoding_for_model
                result = get_encoding_for_model("claude-3-5-sonnet-20240620")
                
                assert result is mock_encoding
                mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")
    
    def test_get_encoding_for_llama_model(self):
        """Test getting encoding for Llama model."""
        with patch('cortex.core.context.TIKTOKEN_AVAILABLE', True):
            with patch('cortex.core.context.tiktoken', create=True) as mock_tiktoken:
                mock_tiktoken.encoding_for_model.side_effect = KeyError("Model not found")
                mock_encoding = MagicMock()
                mock_tiktoken.get_encoding.return_value = mock_encoding
                
                from cortex.core.context import get_encoding_for_model
                result = get_encoding_for_model("llama-3-8b")
                
                assert result is mock_encoding
                mock_tiktoken.get_encoding.assert_called_once_with("o200k_base")
    
    def test_get_encoding_for_deepseek_model(self):
        """Test getting encoding for DeepSeek model."""
        from cortex.core.context import _ENCODING_CACHE

        # Clear cache so mock is used instead of cached real encoding
        cached_value = _ENCODING_CACHE.pop("deepseek-chat", None)
        try:
            with patch('cortex.core.context.TIKTOKEN_AVAILABLE', True):
                with patch('cortex.core.context.tiktoken', create=True) as mock_tiktoken:
                    mock_tiktoken.encoding_for_model.side_effect = KeyError("Model not found")
                    mock_encoding = MagicMock()
                    mock_tiktoken.get_encoding.return_value = mock_encoding

                    from cortex.core.context import get_encoding_for_model
                    result = get_encoding_for_model("deepseek-chat")

                    assert result is mock_encoding
                    mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")
        finally:
            # Clean up: remove mock encoding from cache
            _ENCODING_CACHE.pop("deepseek-chat", None)
            # Restore original if there was one
            if cached_value is not None:
                _ENCODING_CACHE["deepseek-chat"] = cached_value


class TestModuleConfiguration:
    """Test module-level configuration and constants."""
    
    def test_tiktoken_availability(self):
        """Test that TIKTOKEN_AVAILABLE is a boolean."""
        assert isinstance(TIKTOKEN_AVAILABLE, bool)
        
        # It should be either True or False depending on installation
        # We don't care which, just that it's defined
        assert TIKTOKEN_AVAILABLE in (True, False)
    
    def test_encoding_cache_exists(self):
        """Test that encoding cache exists."""
        from cortex.core.context import _ENCODING_CACHE
        assert isinstance(_ENCODING_CACHE, dict)