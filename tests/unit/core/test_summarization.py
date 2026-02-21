"""
Unit tests for conversation summarization (cortex/core/summarization.py).
"""

import json
from unittest.mock import Mock, patch, MagicMock
import pytest

from cortex.core.summarization import (
    SummarizationStrategy,
    SummaryChunk,
    SummarizationConfig,
    SimpleSummarizer,
    LLMSummarizer,
    HybridSummarizer,
    create_summarizer,
    ConversationSummarizer
)


class TestSummarizationStrategy:
    """Test SummarizationStrategy enum."""

    def test_enum_values(self):
        """Test that SummarizationStrategy has correct values."""
        assert SummarizationStrategy.SIMPLE.value == "simple"
        assert SummarizationStrategy.LLM_BASED.value == "llm_based"
        assert SummarizationStrategy.HYBRID.value == "hybrid"


class TestSummaryChunk:
    """Test SummaryChunk dataclass."""

    def test_summary_chunk_creation(self):
        """Test creating a SummaryChunk."""
        chunk = SummaryChunk(
            original_message_count=10,
            original_token_count=1500,
            summary_token_count=150,
            summary_content="User asked about logging. Modified 2 files.",
            key_decisions=["Add logging to main.py", "Use info level"],
            files_modified=["main.py", "config.py"],
            files_read=["requirements.txt"],
            commands_executed=["pip install black"],
            errors_encountered=["File not found: missing.py"],
            timestamp_start="2024-01-01T00:00:00",
            timestamp_end="2024-01-01T00:05:00"
        )

        assert chunk.original_message_count == 10
        assert chunk.original_token_count == 1500
        assert chunk.summary_token_count == 150
        assert "User asked about logging" in chunk.summary_content
        assert chunk.key_decisions == ["Add logging to main.py", "Use info level"]
        assert chunk.files_modified == ["main.py", "config.py"]
        assert chunk.files_read == ["requirements.txt"]
        assert chunk.commands_executed == ["pip install black"]
        assert chunk.errors_encountered == ["File not found: missing.py"]

    def test_summary_chunk_to_message(self):
        """Test converting summary chunk to message format."""
        chunk = SummaryChunk(
            original_message_count=5,
            original_token_count=800,
            summary_token_count=100,
            summary_content="User requested feature addition.",
            key_decisions=["Implement in modules"],
            files_modified=["module.py"],
            files_read=["module.py", "tests.py"],
            commands_executed=["pytest"],
            errors_encountered=["Test failure"]
        )

        message = chunk.to_message()

        assert message["role"] == "system"
        assert "CONVERSATION SUMMARY" in message["content"]
        assert "User requested feature addition" in message["content"]
        assert "Files modified" in message["content"]
        assert "Files read" in message["content"]
        assert "Commands executed" in message["content"]
        assert "Errors encountered" in message["content"]
        assert "Key decisions" in message["content"]

    def test_summary_chunk_to_message_empty_lists(self):
        """Test converting summary chunk with empty lists."""
        chunk = SummaryChunk(
            original_message_count=3,
            original_token_count=300,
            summary_token_count=50,
            summary_content="General conversation."
        )

        message = chunk.to_message()

        # Should not include sections for empty lists
        content = message["content"]
        assert "General conversation" in content
        # Should not contain "Files modified:" etc.
        assert "Files modified:" not in content
        assert "Files read:" not in content


class TestSummarizationConfig:
    """Test SummarizationConfig dataclass."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = SummarizationConfig()

        assert config.enabled is True
        assert config.strategy == SummarizationStrategy.SIMPLE
        assert config.trigger_threshold == 0.8
        assert config.max_summary_tokens == 500
        assert config.preserve_tool_results is True
        assert config.preserve_errors is True
        assert config.min_messages_to_summarize == 5

    def test_config_custom_values(self):
        """Test configuration with custom values."""
        config = SummarizationConfig(
            enabled=False,
            strategy=SummarizationStrategy.LLM_BASED,
            trigger_threshold=0.7,
            max_summary_tokens=300,
            preserve_tool_results=False,
            preserve_errors=False,
            min_messages_to_summarize=10
        )

        assert config.enabled is False
        assert config.strategy == SummarizationStrategy.LLM_BASED
        assert config.trigger_threshold == 0.7
        assert config.max_summary_tokens == 300
        assert config.preserve_tool_results is False
        assert config.preserve_errors is False
        assert config.min_messages_to_summarize == 10


class TestSimpleSummarizer:
    """Test SimpleSummarizer class."""

    @pytest.fixture
    def summarizer(self):
        """Create a SimpleSummarizer instance."""
        return SimpleSummarizer()

    def test_should_summarize(self, summarizer):
        """Test should_summarize method."""
        # Below threshold
        assert summarizer.should_summarize([], current_tokens=400, max_tokens=1000, threshold=0.5) is False

        # At threshold
        assert summarizer.should_summarize([], current_tokens=500, max_tokens=1000, threshold=0.5) is False

        # Above threshold
        assert summarizer.should_summarize([], current_tokens=600, max_tokens=1000, threshold=0.5) is True

        # Default threshold
        assert summarizer.should_summarize([], current_tokens=850, max_tokens=1000) is True

    def test_summarize_empty_messages(self, summarizer):
        """Test summarizing empty message list."""
        with patch("cortex.core.summarization.count_message_tokens", return_value=0):
            chunk = summarizer.summarize([], max_summary_tokens=500)

            assert chunk.original_message_count == 0
            assert chunk.original_token_count == 0
            # System returns 2 tokens for "General conversation" placeholder
            assert chunk.summary_token_count > 0
            assert chunk.summary_content == "General conversation"
            assert chunk.key_decisions == []
            assert chunk.files_modified == []
            assert chunk.files_read == []
            assert chunk.commands_executed == []
            assert chunk.errors_encountered == []

    def test_summarize_user_messages(self, summarizer):
        """Test summarizing user messages."""
        messages = [
            {"role": "user", "content": "Add logging to the application"},
            {"role": "user", "content": "Also add tests"}
        ]

        with patch('cortex.core.context.estimate_tokens', return_value=10):
            chunk = summarizer.summarize(messages, max_summary_tokens=500)

            assert chunk.original_message_count == 2
            assert "User asked" in chunk.summary_content
            assert "Add logging" in chunk.summary_content
            assert "add tests" in chunk.summary_content

    def test_summarize_with_tool_calls(self, summarizer):
        """Test summarizing messages with tool calls."""
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": "main.py"})
                        }
                    },
                    {
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps({"path": "main.py", "content": "..."})
                        }
                    }
                ]
            }
        ]

        with patch('cortex.core.context.estimate_tokens', return_value=10):
            chunk = summarizer.summarize(messages, max_summary_tokens=500)

            assert "main.py" in chunk.files_read
            assert "main.py" in chunk.files_modified
            assert len(chunk.files_read) == 1
            assert len(chunk.files_modified) == 1

    def test_summarize_with_execute_command(self, summarizer):
        """Test summarizing messages with execute_command."""
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "execute_command",
                            "arguments": json.dumps({"command": "pytest tests/"})
                        }
                    }
                ]
            }
        ]

        with patch('cortex.core.context.estimate_tokens', return_value=10):
            chunk = summarizer.summarize(messages, max_summary_tokens=500)

            assert "pytest tests/" in chunk.commands_executed[0]

    def test_summarize_with_tool_errors(self, summarizer):
        """Test summarizing messages with tool errors."""
        messages = [
            {
                "role": "tool",
                "content": json.dumps({
                    "success": False,
                    "error": "File not found: missing.py"
                })
            }
        ]

        with patch('cortex.core.context.estimate_tokens', return_value=10):
            chunk = summarizer.summarize(messages, max_summary_tokens=500)

            assert "File not found" in chunk.errors_encountered[0]

    def test_extract_decisions(self, summarizer):
        """Test decision extraction from content."""
        content = "I'll add logging to the main module. Let me check the existing code first. I decided to use the logging module."

        decisions = summarizer._extract_decisions(content)

        # Should extract decision-like phrases
        assert len(decisions) > 0
        assert any("add logging" in d.lower() for d in decisions)
        assert any("use the logging module" in d.lower() for d in decisions)


class TestLLMSummarizer:
    """Test LLMSummarizer class."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock model provider."""
        provider = Mock()
        provider.chat.return_value = {
            "message": {"content": "LLM summary: User wanted logging added."}
        }
        return provider

    @pytest.fixture
    def llm_summarizer(self, mock_provider):
        """Create an LLMSummarizer instance."""
        return LLMSummarizer(provider=mock_provider, model="gpt-4")

    def test_summarize_success(self, llm_summarizer, mock_provider):
        """Test successful LLM summarization."""
        messages = [
            {"role": "user", "content": "Add logging"},
            {"role": "assistant", "content": "I'll help with that"}
        ]

        with patch('cortex.core.context.estimate_tokens', return_value=50):
            with patch('cortex.core.summarization.SimpleSummarizer') as mock_simple:
                mock_simple_instance = Mock()
                mock_simple_instance.summarize.return_value = SummaryChunk(
                    original_message_count=2,
                    original_token_count=100,
                    summary_token_count=20,
                    summary_content="Simple summary",
                    key_decisions=["decision"],
                    files_modified=[],
                    files_read=[],
                    commands_executed=[],
                    errors_encountered=[]
                )
                mock_simple.return_value = mock_simple_instance

                chunk = llm_summarizer.summarize(messages, max_summary_tokens=200)

                # Verify LLM was called
                mock_provider.chat.assert_called_once()

                # Verify result includes LLM content
                assert "LLM summary" in chunk.summary_content
                assert chunk.key_decisions == ["decision"]

    def test_summarize_failure_fallback(self, llm_summarizer, mock_provider):
        """Test LLM summarization failure with fallback to simple."""
        mock_provider.chat.side_effect = Exception("API error")

        messages = [{"role": "user", "content": "Test"}]

        with patch('cortex.core.context.estimate_tokens', return_value=10):
            with patch('cortex.core.summarization.SimpleSummarizer') as mock_simple:
                mock_simple_instance = Mock()
                mock_simple_instance.summarize.return_value = SummaryChunk(
                    original_message_count=1,
                    original_token_count=20,
                    summary_token_count=5,
                    summary_content="Fallback summary",
                    key_decisions=[],
                    files_modified=[],
                    files_read=[],
                    commands_executed=[],
                    errors_encountered=[]
                )
                mock_simple.return_value = mock_simple_instance

                chunk = llm_summarizer.summarize(messages, max_summary_tokens=200)

                # Should fall back to simple summarizer
                assert chunk.summary_content == "Fallback summary"

    def test_format_messages_for_summary(self, llm_summarizer):
        """Test formatting messages for summary prompt."""
        messages = [
            {"role": "user", "content": "Short message"},
            {"role": "assistant", "content": "This is a longer message that might get truncated if it exceeds certain length limits."},
            {"role": "tool", "content": json.dumps({"success": True, "result": "data"})}
        ]

        formatted = llm_summarizer._format_messages_for_summary(messages, max_chars=1000)

        assert "USER: Short message" in formatted
        assert "ASSISTANT:" in formatted
        assert "TOOL: [Tool result: success]" in formatted

    def test_format_messages_truncation(self, llm_summarizer):
        """Test truncation of formatted messages."""
        messages = [
            {"role": "user", "content": "A" * 300},  # Very long message
            {"role": "assistant", "content": "B"}
        ]

        formatted = llm_summarizer._format_messages_for_summary(messages, max_chars=100)

        # Should be truncated
        assert len(formatted) <= 100
        assert "..." in formatted or "A" in formatted


class TestHybridSummarizer:
    """Test HybridSummarizer class."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider."""
        provider = Mock()
        provider.chat.return_value = {
            "message": {"content": "Enhanced LLM summary"}
        }
        return provider

    def test_hybrid_with_provider(self, mock_provider):
        """Test hybrid summarizer with provider available."""
        summarizer = HybridSummarizer(provider=mock_provider, model="gpt-4")

        messages = [{"role": "user", "content": "Test"}] * 11  # More than 10 messages

        with patch.object(summarizer.simple, 'summarize') as mock_simple_summarize:
            simple_chunk = SummaryChunk(
                original_message_count=11,
                original_token_count=2200,
                summary_token_count=100,
                summary_content="Simple summary",
                key_decisions=["decision"],
                files_modified=["file.py"],
                files_read=["read.py"],
                commands_executed=[],
                errors_encountered=[]
            )
            mock_simple_summarize.return_value = simple_chunk

            with patch.object(summarizer.llm, 'summarize') as mock_llm_summarize:
                llm_chunk = SummaryChunk(
                    original_message_count=11,
                    original_token_count=2200,
                    summary_token_count=150,
                    summary_content="Enhanced LLM summary",
                    key_decisions=[],
                    files_modified=[],
                    files_read=[],
                    commands_executed=[],
                    errors_encountered=[]
                )
                mock_llm_summarize.return_value = llm_chunk

                chunk = summarizer.summarize(messages, max_summary_tokens=500)

                # Should use LLM content but simple's structured data
                assert chunk.summary_content == "Enhanced LLM summary"
                assert chunk.key_decisions == ["decision"]
                assert chunk.files_modified == ["file.py"]

    def test_hybrid_without_provider(self):
        """Test hybrid summarizer without provider."""
        summarizer = HybridSummarizer(provider=None, model="")

        messages = [{"role": "user", "content": "Test"}]

        with patch.object(summarizer.simple, 'summarize') as mock_simple_summarize:
            simple_chunk = SummaryChunk(
                original_message_count=1,
                original_token_count=20,
                summary_token_count=5,
                summary_content="Simple summary",
                key_decisions=[],
                files_modified=[],
                files_read=[],
                commands_executed=[],
                errors_encountered=[]
            )
            mock_simple_summarize.return_value = simple_chunk

            chunk = summarizer.summarize(messages, max_summary_tokens=500)

            # Should return simple summary
            assert chunk.summary_content == "Simple summary"

    def test_hybrid_llm_failure(self, mock_provider):
        """Test hybrid summarizer when LLM enhancement fails."""
        summarizer = HybridSummarizer(provider=mock_provider, model="gpt-4")

        messages = [{"role": "user", "content": "Test"}] * 11

        with patch.object(summarizer.simple, 'summarize') as mock_simple_summarize:
            simple_chunk = SummaryChunk(
                original_message_count=11,
                original_token_count=2200,
                summary_token_count=100,
                summary_content="Simple summary",
                key_decisions=[],
                files_modified=[],
                files_read=[],
                commands_executed=[],
                errors_encountered=[]
            )
            mock_simple_summarize.return_value = simple_chunk

            with patch.object(summarizer.llm, 'summarize', side_effect=Exception("LLM failed")):
                chunk = summarizer.summarize(messages, max_summary_tokens=500)

                # Should fall back to simple summary
                assert chunk.summary_content == "Simple summary"

class TestCreateSummarizer:
    """Test create_summarizer factory function."""

    def test_create_simple(self):
        """Test creating simple summarizer."""
        summarizer = create_summarizer(SummarizationStrategy.SIMPLE)
        assert isinstance(summarizer, SimpleSummarizer)

    def test_create_llm_based_with_provider(self):
        """Test creating LLM-based summarizer with provider."""
        mock_provider = Mock()
        summarizer = create_summarizer(
            SummarizationStrategy.LLM_BASED,
            provider=mock_provider,
            model="gpt-4"
        )
        assert isinstance(summarizer, LLMSummarizer)
        assert summarizer.provider == mock_provider
        assert summarizer.model == "gpt-4"

    def test_create_llm_based_without_provider(self):
        """Test creating LLM-based summarizer without provider (should fallback)."""
        with patch('cortex.core.summarization.logger') as mock_logger:
            summarizer = create_summarizer(SummarizationStrategy.LLM_BASED, provider=None)
            assert isinstance(summarizer, SimpleSummarizer)
            mock_logger.warning.assert_called()

    def test_create_hybrid(self):
        """Test creating hybrid summarizer."""
        mock_provider = Mock()
        summarizer = create_summarizer(
            SummarizationStrategy.HYBRID,
            provider=mock_provider,
            model="gpt-4"
        )
        assert isinstance(summarizer, HybridSummarizer)

    def test_create_unknown_strategy(self):
        """Test creating summarizer with unknown strategy (should default to simple)."""
        # Use a mock strategy value
        class UnknownStrategy:
            value = "unknown"

        summarizer = create_summarizer(UnknownStrategy())  # type: ignore
        assert isinstance(summarizer, SimpleSummarizer)
