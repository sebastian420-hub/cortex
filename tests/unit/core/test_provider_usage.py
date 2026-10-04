"""Token usage is read from each provider's response and reported in one shape (or not at all)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cortex.core.providers.usage import normalize_usage, usage_of_response

# ---- the normalizer ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        {"prompt_tokens": 12, "completion_tokens": 5},  # OpenAI, OpenRouter, DeepSeek
        {"input_tokens": 12, "output_tokens": 5},  # Anthropic
        {"prompt_eval_count": 12, "eval_count": 5},  # Ollama
        SimpleNamespace(prompt_tokens=12, completion_tokens=5, total_tokens=17),
        SimpleNamespace(input_tokens=12, output_tokens=5),
    ],
)
def test_every_providers_naming_gives_the_same_shape(raw):
    assert normalize_usage(raw) == {"input_tokens": 12, "output_tokens": 5}


@pytest.mark.parametrize("raw", [None, {}, SimpleNamespace(), {"prompt_tokens": None}, "text"])
def test_no_usage_means_none_not_zero(raw):
    assert normalize_usage(raw) is None


def test_one_side_missing_counts_as_zero_for_that_side_only():
    assert normalize_usage({"output_tokens": 7}) == {"input_tokens": 0, "output_tokens": 7}


def test_usage_is_found_on_a_normalized_response_and_on_an_ollama_response():
    assert usage_of_response({"message": {}, "usage": {"input_tokens": 3, "output_tokens": 4}}) == {
        "input_tokens": 3,
        "output_tokens": 4,
    }
    assert usage_of_response({"message": {}, "prompt_eval_count": 3, "eval_count": 4}) == {
        "input_tokens": 3,
        "output_tokens": 4,
    }
    assert usage_of_response({"message": {}}) is None
    assert usage_of_response(None) is None


# ---- the providers pass it through -------------------------------------------------------


def _openai_style_response(usage):
    message = SimpleNamespace(role="assistant", content="hello", tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def test_openrouter_reports_usage(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with patch("openai.OpenAI") as openai_class:
        client = MagicMock()
        openai_class.return_value = client
        client.chat.completions.create.return_value = _openai_style_response(
            SimpleNamespace(prompt_tokens=100, completion_tokens=20)
        )
        from cortex.core.providers import OpenRouterProvider

        result = OpenRouterProvider().chat("some/model", [{"role": "user", "content": "hi"}])

    assert result["usage"] == {"input_tokens": 100, "output_tokens": 20}
    assert result["message"]["content"] == "hello"


def test_openrouter_without_usage_has_no_usage_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with patch("openai.OpenAI") as openai_class:
        client = MagicMock()
        openai_class.return_value = client
        client.chat.completions.create.return_value = _openai_style_response(None)
        from cortex.core.providers import OpenRouterProvider

        result = OpenRouterProvider().chat("some/model", [{"role": "user", "content": "hi"}])

    assert "usage" not in result


def test_deepseek_reports_usage(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    with patch("openai.OpenAI") as openai_class:
        client = MagicMock()
        openai_class.return_value = client
        client.chat.completions.create.return_value = _openai_style_response(
            SimpleNamespace(prompt_tokens=7, completion_tokens=3)
        )
        from cortex.core.providers.deepseek import DeepSeekProvider

        result = DeepSeekProvider().chat("deepseek-chat", [{"role": "user", "content": "hi"}])

    assert result["usage"] == {"input_tokens": 7, "output_tokens": 3}


def test_anthropic_reports_usage(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with patch("anthropic.Anthropic") as anthropic_class:
        client = MagicMock()
        anthropic_class.return_value = client
        client.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hello")],
            usage=SimpleNamespace(input_tokens=50, output_tokens=9),
        )
        from cortex.core.providers.anthropic_provider import AnthropicProvider

        result = AnthropicProvider().chat("claude-x", [{"role": "user", "content": "hi"}])

    assert result["usage"] == {"input_tokens": 50, "output_tokens": 9}
    assert result["message"]["content"] == "hello"
