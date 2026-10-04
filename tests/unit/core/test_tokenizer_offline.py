"""Token counting must work with no network and must not retry a doomed download.

tiktoken fetches its vocabulary the first time an encoding is used. On an offline machine that
used to be retried on *every* token count (33 failed attempts for one trivial agent turn), and
asking for a model tiktoken knows by name (the default, "gpt-4") raised instead of falling back.
"""

import pytest

from cortex.core import context


@pytest.fixture(autouse=True)
def real_tokenizer_path(monkeypatch):
    """The suite normally turns tiktoken off; these tests exercise the tiktoken path."""
    monkeypatch.setattr(context, "TIKTOKEN_AVAILABLE", True)
    monkeypatch.delenv("CORTEX_OFFLINE", raising=False)
    monkeypatch.setattr(context, "_ENCODING_CACHE", {})


class _Download:
    """Stand-in for tiktoken.get_encoding that always fails and counts its calls."""

    def __init__(self):
        self.calls = []

    def __call__(self, name):
        self.calls.append(name)
        raise ConnectionError("no network")


def test_a_failed_load_is_attempted_only_once(monkeypatch):
    download = _Download()
    monkeypatch.setattr(context.tiktoken, "get_encoding", download)

    for _ in range(5):
        assert context.estimate_tokens("hello world, this is a test", "llama3") > 0
        assert context.estimate_tokens("hello world, this is a test", "qwen2.5") > 0

    # Both models map to the same encoding, so one failed attempt covers every later call.
    assert download.calls == ["o200k_base"]


def test_default_model_name_does_not_raise_offline(monkeypatch):
    monkeypatch.setattr(context.tiktoken, "get_encoding", _Download())

    # "gpt-4" is known to tiktoken by name, which used to take an unguarded code path.
    assert isinstance(context.estimate_tokens("hello world", "gpt-4"), int)
    assert isinstance(context.estimate_tokens("hello world"), int)


def test_offline_switch_never_calls_tiktoken(monkeypatch):
    download = _Download()
    monkeypatch.setattr(context.tiktoken, "get_encoding", download)
    monkeypatch.setenv("CORTEX_OFFLINE", "1")

    assert context.estimate_tokens("hello world", "gpt-4") > 0
    assert download.calls == []


@pytest.mark.parametrize(
    "model, expected",
    [
        ("gpt-4", "cl100k_base"),
        ("claude-3-5-sonnet", "cl100k_base"),
        ("anthropic/claude-3-haiku", "cl100k_base"),
        ("deepseek-chat", "cl100k_base"),
        ("llama3.2", "o200k_base"),
        ("mistral-large", "o200k_base"),
        ("totally-unknown-model", "cl100k_base"),
    ],
)
def test_encoding_is_chosen_without_network(model, expected):
    assert context._encoding_name_for(model) == expected
