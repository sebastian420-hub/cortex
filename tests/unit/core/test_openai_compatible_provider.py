"""One provider for anything that speaks the OpenAI chat API: OpenAI, vLLM, llama.cpp's server,
LM Studio, SGLang. The usual way to serve a big local model, so the base URL and key are the SDK's
own settings (OPENAI_BASE_URL, OPENAI_API_KEY) and a local server needs no key."""

import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cortex.agent import Cortex
from cortex.cli import build_parser, validate_provider_setup
from cortex.config import AgentConfig
from cortex.core.providers import ProviderError, ProviderFactory
from cortex.core.providers.openai_compatible import OpenAICompatibleProvider
from cortex.models import PermissionMode

MESSAGES = [{"role": "user", "content": "hi"}]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "CORTEX_OPENAI_CONTEXT_WINDOW"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def sdk():
    """The OpenAI SDK's client class, patched; yields (client_class, client)."""
    with patch("openai.OpenAI") as client_class:
        client = MagicMock()
        client_class.return_value = client
        yield client_class, client


def reply(content="hello", tool_calls=None, usage=None):
    message = SimpleNamespace(role="assistant", content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def tool_call(name="read_file", arguments='{"path": "a.py"}', call_id="call_1", type_="function"):
    return SimpleNamespace(
        id=call_id, type=type_, function=SimpleNamespace(name=name, arguments=arguments)
    )


# ---- connecting ---------------------------------------------------------------------------


def test_a_local_server_needs_only_a_base_url(sdk, monkeypatch):
    client_class, _ = sdk
    monkeypatch.setenv("OPENAI_BASE_URL", "http://spark:8000/v1")

    OpenAICompatibleProvider()

    kwargs = client_class.call_args.kwargs
    assert kwargs["base_url"] == "http://spark:8000/v1"
    assert kwargs["api_key"]  # the SDK insists on a non-empty key; a local server ignores it


def test_openai_itself_needs_a_key(sdk, monkeypatch):
    client_class, _ = sdk
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    OpenAICompatibleProvider()

    assert client_class.call_args.kwargs["api_key"] == "sk-test"
    assert client_class.call_args.kwargs.get("base_url") is None


def test_with_neither_it_says_what_to_set(sdk):
    with pytest.raises(ProviderError) as error:
        OpenAICompatibleProvider()

    assert "OPENAI_API_KEY" in str(error.value) and "OPENAI_BASE_URL" in str(error.value)


def test_the_key_check_matches_the_constructor(sdk, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://spark:8000/v1")

    assert OpenAICompatibleProvider().validate_api_key() is True


def test_the_config_can_supply_the_base_url_but_the_environment_wins(sdk, monkeypatch):
    client_class, _ = sdk
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    provider = OpenAICompatibleProvider()

    provider.configure({"base_url": "http://from-config:8000/v1"})
    assert client_class.call_args.kwargs["base_url"] == "http://from-config:8000/v1"

    monkeypatch.setenv("OPENAI_BASE_URL", "http://from-env:8000/v1")
    provider.configure({"base_url": "http://from-config:8000/v1"})
    assert client_class.call_args.kwargs["base_url"] == "http://from-env:8000/v1"


# ---- chatting -----------------------------------------------------------------------------


@pytest.fixture
def provider(sdk, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://spark:8000/v1")
    return OpenAICompatibleProvider()


def test_a_plain_answer(provider, sdk):
    _, client = sdk
    client.chat.completions.create.return_value = reply("hello there")

    result = provider.chat("Qwen/Qwen3-Coder-30B", MESSAGES)

    assert result["message"] == {"role": "assistant", "content": "hello there"}
    assert client.chat.completions.create.call_args.kwargs["model"] == "Qwen/Qwen3-Coder-30B"


def test_tools_are_passed_through_and_calls_come_back(provider, sdk):
    _, client = sdk
    client.chat.completions.create.return_value = reply("", [tool_call()])
    tools = [{"type": "function", "function": {"name": "read_file", "parameters": {}}}]

    result = provider.chat("m", MESSAGES, tools)

    assert client.chat.completions.create.call_args.kwargs["tools"] == tools
    call = result["message"]["tool_calls"][0]
    assert call["id"] == "call_1" and call["type"] == "function"
    assert call["function"]["name"] == "read_file"
    assert json.loads(call["function"]["arguments"]) == {"path": "a.py"}


def test_no_tools_means_no_tools_argument(provider, sdk):
    _, client = sdk
    client.chat.completions.create.return_value = reply()

    provider.chat("m", MESSAGES)

    assert "tools" not in client.chat.completions.create.call_args.kwargs


def test_untidy_tool_calls_from_a_local_model_are_repaired(provider, sdk):
    _, client = sdk
    messy = tool_call(call_id=None, arguments="")  # no id, empty arguments
    client.chat.completions.create.return_value = reply("", [messy])

    call = provider.chat("m", MESSAGES)["message"]["tool_calls"][0]

    assert call["id"]
    assert json.loads(call["function"]["arguments"]) == {}


def test_usage_is_reported_when_the_server_gives_it(provider, sdk):
    _, client = sdk
    usage = SimpleNamespace(prompt_tokens=120, completion_tokens=30)
    client.chat.completions.create.return_value = reply(usage=usage)

    assert provider.chat("m", MESSAGES)["usage"] == {"input_tokens": 120, "output_tokens": 30}


def test_no_usage_means_no_usage_key(provider, sdk):
    _, client = sdk
    client.chat.completions.create.return_value = reply(usage=None)

    assert "usage" not in provider.chat("m", MESSAGES)


def test_a_server_error_becomes_a_provider_error(provider, sdk):
    _, client = sdk
    client.chat.completions.create.side_effect = RuntimeError("connection refused")

    with pytest.raises(ProviderError, match="connection refused"):
        provider.chat("m", MESSAGES)


def test_text_that_is_not_valid_utf8_is_cleaned_before_sending(provider, sdk):
    _, client = sdk
    client.chat.completions.create.return_value = reply()

    provider.chat("m", [{"role": "user", "content": "bad \udcff byte"}])

    sent = client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    sent.encode("utf-8")  # must not raise


# ---- streaming ----------------------------------------------------------------------------


def chunk(content=None, tool_calls=None):
    delta = SimpleNamespace(role="assistant", content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def test_streaming_yields_text_pieces(provider, sdk):
    _, client = sdk
    client.chat.completions.create.return_value = iter([chunk("Hel"), chunk("lo")])

    pieces = [c["message"]["content"] for c in provider.stream_chat("m", MESSAGES)]

    assert pieces == ["Hel", "lo"]
    assert client.chat.completions.create.call_args.kwargs["stream"] is True


def test_streaming_tool_call_pieces_carry_their_index(provider, sdk):
    _, client = sdk
    piece = SimpleNamespace(
        id="c1", index=0, type="function", function=SimpleNamespace(name="grep", arguments='{"q"')
    )
    client.chat.completions.create.return_value = iter([chunk(tool_calls=[piece])])

    (out,) = list(provider.stream_chat("m", MESSAGES))

    call = out["message"]["tool_calls"][0]
    assert call["index"] == 0 and call["function"]["name"] == "grep"


def test_a_streaming_error_becomes_a_provider_error(provider, sdk):
    _, client = sdk
    client.chat.completions.create.side_effect = RuntimeError("boom")

    with pytest.raises(ProviderError, match="boom"):
        list(provider.stream_chat("m", MESSAGES))


# ---- the context window -------------------------------------------------------------------


def test_the_window_is_unknown_unless_you_say(provider):
    assert provider.context_window is None


def test_the_window_can_come_from_the_config(provider):
    provider.configure({"context_window": 65536})

    assert provider.context_window == 65536


def test_the_environment_wins_over_the_config_for_the_window(provider, monkeypatch):
    monkeypatch.setenv("CORTEX_OPENAI_CONTEXT_WINDOW", "32768")

    provider.configure({"context_window": 65536})

    assert provider.context_window == 32768


@pytest.mark.parametrize("bad", ["lots", "0", "-1", None])
def test_an_unusable_window_is_ignored(provider, bad):
    provider.configure({"context_window": bad})

    assert provider.context_window is None


# ---- being chosen -------------------------------------------------------------------------


def test_the_factory_builds_it_by_name_even_for_names_with_slashes(sdk, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://spark:8000/v1")

    # a slash in a model name normally means OpenRouter; an explicit provider overrides that
    chosen = ProviderFactory.get_provider("Qwen/Qwen3-Coder-30B", "openai")

    assert isinstance(chosen, OpenAICompatibleProvider)


def test_its_other_names_work_too(sdk, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://spark:8000/v1")

    assert isinstance(
        ProviderFactory.get_provider("m", "openai-compatible"), OpenAICompatibleProvider
    )


def test_the_command_line_accepts_it():
    args = build_parser().parse_args(["--provider", "openai", "--model", "m"])

    assert args.provider == "openai"


# ---- the agent and the configuration ------------------------------------------------------


def test_the_provider_name_honours_an_explicit_choice():
    name = ProviderFactory.get_provider_name

    assert name("Qwen/Qwen3-Coder-30B") == "openrouter"  # what the model name alone suggests
    assert name("Qwen/Qwen3-Coder-30B", "openai") == "openai"
    assert name("m", "OpenAI-Compatible") == "openai"
    assert name("claude-3-haiku", "claude") == "anthropic"
    assert name("m", None) == name("m")
    assert name("m", object()) == name("m")  # not a name: ignored


def test_each_provider_names_its_config_section():
    assert OpenAICompatibleProvider.config_section == "openai"
    assert AgentConfig().get_provider_options("openai") == {
        "base_url": None,
        "context_window": None,
    }
    assert AgentConfig(ollama={"num_ctx": 8192}).get_provider_options("ollama") == {"num_ctx": 8192}
    assert AgentConfig().get_provider_options(None) == {}
    assert AgentConfig().get_provider_options("anthropic") == {}


def make_agent(tmp_path, **openai):
    config = AgentConfig(
        model="Qwen/Qwen3-Coder-30B",
        provider="openai",
        openai=openai,
        permission_mode=PermissionMode.AUTO_APPROVE,
        checkpoints={"enabled": False},
    )
    return Cortex(
        model="Qwen/Qwen3-Coder-30B",
        project_dir=str(tmp_path),
        config=config,
        enable_planning=False,
        enable_layered_memory=False,
    )


def test_the_agent_sizes_its_history_to_the_configured_window(sdk, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://spark:8000/v1")
    # a window below the model's default budget (about 21,600 here) must lower the budget
    configured = make_agent(tmp_path, context_window=16384)
    unconfigured = make_agent(tmp_path)

    assert isinstance(configured.provider, OpenAICompatibleProvider)
    assert configured.provider.context_window == 16384
    assert configured.conversation.max_tokens < 16384
    assert unconfigured.provider.context_window is None
    assert unconfigured.conversation.max_tokens > configured.conversation.max_tokens


def test_the_config_base_url_reaches_the_client(sdk, monkeypatch, tmp_path):
    client_class, _ = sdk
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    make_agent(tmp_path, base_url="http://from-config:8000/v1")

    assert client_class.call_args.kwargs["base_url"] == "http://from-config:8000/v1"


def test_a_window_too_small_for_cortex_gets_advice_for_this_server(
    sdk, monkeypatch, tmp_path, caplog
):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://spark:8000/v1")

    with caplog.at_level(logging.WARNING):
        make_agent(tmp_path, context_window=4096)

    warning = " ".join(r.getMessage() for r in caplog.records)
    assert "4096" in warning
    assert "CORTEX_OPENAI_CONTEXT_WINDOW" in warning and "max-model-len" in warning
    assert "OLLAMA" not in warning  # advice for another provider would send the user astray


def test_the_startup_check_follows_the_chosen_provider_not_the_model_name():
    """--provider ollama with a name that looks like OpenRouter's must still check Ollama."""
    with patch.dict("sys.modules", {"ollama": MagicMock()}):
        with patch("cortex.cli.check_ollama", return_value=False) as check:
            assert validate_provider_setup("qwen/qwen3-coder", "ollama") is False

    check.assert_called_once()
