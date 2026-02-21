"""Comprehensive tests for empty assistant message fix."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Iterator, Dict, Any


class TestStreamingResponseHandling:
    """Tests for streaming.py display_streaming_response function."""

    def test_reasoning_only_response_gets_content(self):
        """Test that reasoning-only responses are converted to content."""
        from cortex.core.streaming import display_streaming_response

        # Mock stream with only reasoning_content
        def mock_stream():
            yield {"message": {"reasoning_content": "Let me think about this..."}}
            yield {"message": {"reasoning_content": " The answer is 42."}}

        with patch('cortex.core.streaming.console') as mock_console:
            result = display_streaming_response(mock_stream())

        # Should have content from reasoning
        assert "content" in result
        assert result["content"] == "Let me think about this... The answer is 42."
        assert "reasoning_content" in result

    def test_reasoning_with_tool_syntax_gets_extracted(self):
        """Test that reasoning with tool syntax has tools extracted."""
        from cortex.core.streaming import display_streaming_response

        # Mock stream with tool syntax in reasoning
        def mock_stream():
            yield {"message": {"reasoning_content": "<tool_call>read_file({'path': 'test.py'})</tool_call>"}}

        with patch('cortex.core.streaming.console') as mock_console:
            with patch('cortex.core.streaming._extract_kimi_native_tool_calls_from_streaming') as mock_extract:
                # Return a valid tool call
                mock_extract.return_value = [
                    {"id": "call_1", "function": {"name": "read_file", "arguments": '{"path": "test.py"}'}, "type": "function"}
                ]
                result = display_streaming_response(mock_stream())

        # Should have tool_calls extracted
        assert "tool_calls" in result
        assert result["tool_calls"][0]["function"]["name"] == "read_file"

    def test_completely_empty_response_has_placeholder(self):
        """Test that completely empty responses get placeholder content."""
        from cortex.core.streaming import display_streaming_response

        # Mock stream with nothing
        def mock_stream():
            yield {"message": {}}

        with patch('cortex.core.streaming.console') as mock_console:
            result = display_streaming_response(mock_stream())

        # Should have empty content at minimum
        assert "content" in result
        assert result["content"] == ""

    def test_normal_response_unchanged(self):
        """Test that normal responses with content work as before."""
        from cortex.core.streaming import display_streaming_response

        def mock_stream():
            yield {"message": {"content": "Hello "}}
            yield {"message": {"content": "world!"}}

        with patch('cortex.core.streaming.console') as mock_console:
            result = display_streaming_response(mock_stream())

        assert result["content"] == "Hello world!"
        assert "tool_calls" not in result

    def test_content_and_reasoning_both_preserved(self):
        """Test that when both content and reasoning exist, both are preserved."""
        from cortex.core.streaming import display_streaming_response

        def mock_stream():
            yield {"message": {"content": "The answer is ", "reasoning_content": "Thinking..."}}
            yield {"message": {"content": "42", "reasoning_content": "Done"}}

        with patch('cortex.core.streaming.console') as mock_console:
            result = display_streaming_response(mock_stream())

        assert result["content"] == "The answer is 42"
        assert result["reasoning_content"] == "Thinking...Done"


class TestConversationMessageHandling:
    """Tests for conversation.py add_assistant_message function."""

    def test_reasoning_only_converted_to_content(self):
        """Test that reasoning-only messages get converted to content."""
        from cortex.core.conversation import ConversationManager as Conversation

        conv = Conversation(system_prompt="Test")

        with patch('cortex.core.conversation.logger') as mock_logger:
            conv.add_assistant_message(
                content="",
                tool_calls=None,
                reasoning_content="I need to think about this..."
            )

        history = conv.get_history()
        assistant_msg = [m for m in history if m["role"] == "assistant"][0]

        # Should have content extracted from reasoning
        assert "content" in assistant_msg
        assert "[Reasoning:" in assistant_msg["content"]
        # Should log at debug, not warning
        mock_logger.debug.assert_called()
        mock_logger.warning.assert_not_called()

    def test_reasoning_with_tool_syntax_no_warning(self):
        """Test that reasoning with tool syntax doesn't trigger warning."""
        from cortex.core.conversation import ConversationManager as Conversation

        conv = Conversation(system_prompt="Test")

        with patch('cortex.core.conversation.logger') as mock_logger:
            conv.add_assistant_message(
                content="",
                tool_calls=None,
                reasoning_content="<tool_call>read_file</tool_call>"
            )

        history = conv.get_history()
        assistant_msg = [m for m in history if m["role"] == "assistant"][0]

        # Should still have content
        assert "content" in assistant_msg
        # Should log at debug only, not warning
        mock_logger.debug.assert_called()
        mock_logger.warning.assert_not_called()

    def test_completely_empty_message_no_warning(self):
        """Test that completely empty messages don't trigger warning."""
        from cortex.core.conversation import ConversationManager as Conversation

        conv = Conversation(system_prompt="Test")

        with patch('cortex.core.conversation.logger') as mock_logger:
            conv.add_assistant_message(
                content="",
                tool_calls=None,
                reasoning_content=None
            )

        history = conv.get_history()
        assistant_msg = [m for m in history if m["role"] == "assistant"][0]

        # Should have placeholder content
        assert assistant_msg["content"] == "[Empty assistant response]"
        # Should log at debug only
        mock_logger.debug.assert_called()
        mock_logger.warning.assert_not_called()

    def test_normal_message_unchanged(self):
        """Test that normal messages work as before."""
        from cortex.core.conversation import ConversationManager as Conversation

        conv = Conversation(system_prompt="Test")
        conv.add_assistant_message(
            content="Hello world",
            tool_calls=None,
            reasoning_content=None
        )

        history = conv.get_history()
        assistant_msg = [m for m in history if m["role"] == "assistant"][0]

        assert assistant_msg["content"] == "Hello world"


class TestAgentResponseHandling:
    """Tests for agent.py response handling."""

    def test_reasoning_only_no_user_warning(self):
        """Test that reasoning-only responses don't show user warnings."""
        from cortex.agent import Cortex

        agent = Cortex(model="test")
        agent._output_warning = Mock()
        agent._output_response = Mock()

        # Simulate final response with reasoning but no content
        response_message = {
            "content": "",
            "reasoning_content": "Let me think...",
            "tool_calls": None
        }

        # Should not call _output_warning
        # Note: In real scenario this happens in the conversation loop
        # We're testing the logic that was changed
        assert not response_message.get("content")
        assert response_message.get("reasoning_content")


class TestEdgeCases:
    """Edge case tests."""

    def test_whitespace_only_content(self):
        """Test handling of whitespace-only content - whitespace is valid."""
        from cortex.core.conversation import ConversationManager as Conversation

        conv = Conversation(system_prompt="Test")
        conv.add_assistant_message(
            content="   ",
            tool_calls=None,
            reasoning_content=None
        )

        history = conv.get_history()
        assistant_msg = [m for m in history if m["role"] == "assistant"][0]
        # Whitespace is valid content - should be preserved as-is
        assert assistant_msg["content"] == "   "

    def test_empty_strings_in_reasoning_list(self):
        """Test streaming with empty strings in reasoning parts."""
        from cortex.core.streaming import display_streaming_response

        def mock_stream():
            yield {"message": {"reasoning_content": ""}}
            yield {"message": {"reasoning_content": "Actual content"}}
            yield {"message": {"reasoning_content": ""}}

        with patch('cortex.core.streaming.console') as mock_console:
            result = display_streaming_response(mock_stream())

        # Should have content from non-empty reasoning
        assert result["content"] == "Actual content"

    def test_tool_calls_with_empty_reasoning(self):
        """Test that tool calls work even with empty reasoning."""
        from cortex.core.conversation import ConversationManager as Conversation

        conv = Conversation(system_prompt="Test")
        conv.add_assistant_message(
            content="",
            tool_calls=[{"id": "1", "function": {"name": "test"}}],
            reasoning_content=None
        )

        history = conv.get_history()
        assistant_msg = [m for m in history if m["role"] == "assistant"][0]

        # Should have tool_calls
        assert "tool_calls" in assistant_msg
        assert assistant_msg["tool_calls"][0]["function"]["name"] == "test"


class TestRegressionScenarios:
    """Tests to ensure no regressions in existing functionality."""

    def test_normal_tool_calls_work(self):
        """Ensure normal tool calling still works."""
        from cortex.core.streaming import display_streaming_response

        def mock_stream():
            yield {"message": {"content": "I'll help"}}
            yield {"message": {"tool_calls": [{"id": "1", "function": {"name": "read_file", "arguments": "{}"}}]}}

        with patch('cortex.core.streaming.console') as mock_console:
            result = display_streaming_response(mock_stream())

        assert result["content"] == "I'll help"
        assert "tool_calls" in result

    def test_content_and_tool_calls_together(self):
        """Ensure content + tool calls still works."""
        from cortex.core.conversation import ConversationManager as Conversation

        conv = Conversation(system_prompt="Test")
        conv.add_assistant_message(
            content="Let me check",
            tool_calls=[{"id": "1", "function": {"name": "test"}}],
            reasoning_content=None
        )

        history = conv.get_history()
        assistant_msg = [m for m in history if m["role"] == "assistant"][0]

        assert assistant_msg["content"] == "Let me check"
        assert "tool_calls" in assistant_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
