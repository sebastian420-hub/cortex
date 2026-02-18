"""Benchmarks for token counting operations."""

import pytest

from cortex.core.context import (
    estimate_tokens,
    count_message_tokens,
    get_conversation_tokens,
    truncate_history,
)


@pytest.mark.performance
class TestTokenCountingBenchmarks:
    """Benchmark suite for token counting."""

    def test_estimate_tokens_1k(self, benchmark, sample_text_1k):
        """Benchmark: Token estimation for ~1K chars."""
        benchmark(estimate_tokens, sample_text_1k, "gpt-4")

    def test_estimate_tokens_10k(self, benchmark, sample_text_10k):
        """Benchmark: Token estimation for ~10K chars."""
        benchmark(estimate_tokens, sample_text_10k, "gpt-4")

    def test_estimate_tokens_100k(self, benchmark, sample_text_100k):
        """Benchmark: Token estimation for ~100K chars."""
        benchmark(estimate_tokens, sample_text_100k, "gpt-4")

    def test_estimate_tokens_claude_model(self, benchmark, sample_text_10k):
        """Benchmark: Token estimation with Claude model."""
        benchmark(estimate_tokens, sample_text_10k, "claude-3-sonnet")

    def test_estimate_tokens_llama_model(self, benchmark, sample_text_10k):
        """Benchmark: Token estimation with Llama model."""
        benchmark(estimate_tokens, sample_text_10k, "llama3.2")

    def test_count_message_tokens_simple(self, benchmark, sample_text_1k):
        """Benchmark: Count tokens in a simple message."""
        message = {"role": "user", "content": sample_text_1k}
        benchmark(count_message_tokens, message, "gpt-4")

    def test_count_message_tokens_with_tool_calls(self, benchmark, sample_text_1k):
        """Benchmark: Count tokens in a message with tool calls."""
        message = {
            "role": "assistant",
            "content": sample_text_1k,
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"file_path": "/path/to/file.py"}',
                    },
                },
                {
                    "id": "call_456",
                    "type": "function",
                    "function": {
                        "name": "grep",
                        "arguments": '{"pattern": "def.*\\\\(", "path": "."}',
                    },
                },
            ],
        }
        benchmark(count_message_tokens, message, "gpt-4")


@pytest.mark.performance
class TestConversationTokenBenchmarks:
    """Benchmark suite for conversation-level token operations."""

    def test_conversation_tokens_20_messages(self, benchmark, sample_conversation):
        """Benchmark: Count tokens in 20-message conversation."""
        benchmark(get_conversation_tokens, sample_conversation, "gpt-4")

    def test_truncate_history_no_truncation(self, benchmark, sample_conversation):
        """Benchmark: Truncate history when under limit (no-op)."""
        benchmark(
            truncate_history,
            sample_conversation,
            max_tokens=1000000,
            keep_recent=20,
            model="gpt-4",
        )

    def test_truncate_history_with_truncation(self, benchmark, sample_conversation):
        """Benchmark: Truncate history when over limit."""
        benchmark(
            truncate_history,
            sample_conversation,
            max_tokens=1000,
            keep_recent=5,
            model="gpt-4",
        )
