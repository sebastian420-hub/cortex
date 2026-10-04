"""A local model must be given a context window big enough for Cortex, and Cortex must size its
history to that window.

Cortex sends about 7,000 tokens (the tool definitions and the system prompt) before the user's
first word. Ollama applies its own small default window when none is given and silently drops the
oldest messages, system prompt included, so the model would see a broken prompt.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from cortex.agent import Cortex
from cortex.config import AgentConfig
from cortex.core.context import estimate_tokens
from cortex.core.conversation import RESPONSE_RESERVE_TOKENS, ConversationManager
from cortex.core.providers.ollama import DEFAULT_NUM_CTX, OllamaProvider
from cortex.models import PermissionMode
from cortex.tools import get_registry
from tests.e2e.scripted import ScriptedProvider

MESSAGES = [{"role": "user", "content": "hi"}]


@pytest.fixture
def ollama_module():
    fake = MagicMock()
    fake.chat.return_value = {"message": {"role": "assistant", "content": "ok"}}
    with patch.dict("sys.modules", {"ollama": fake}):
        yield fake


@pytest.fixture(autouse=True)
def no_env_override(monkeypatch):
    monkeypatch.delenv("CORTEX_OLLAMA_NUM_CTX", raising=False)


# ---- the provider -------------------------------------------------------------------------


def test_every_chat_call_states_the_context_window(ollama_module):
    OllamaProvider().chat("qwen3-coder", MESSAGES)

    assert ollama_module.chat.call_args.kwargs["options"] == {"num_ctx": DEFAULT_NUM_CTX}


def test_streaming_states_it_too(ollama_module):
    ollama_module.chat.return_value = iter([])

    list(OllamaProvider().stream_chat("qwen3-coder", MESSAGES))

    assert ollama_module.chat.call_args.kwargs["options"] == {"num_ctx": DEFAULT_NUM_CTX}


def test_the_default_is_large_enough_for_cortexs_own_prompt():
    tools = estimate_tokens(json.dumps(get_registry().get_all_schemas()))

    assert DEFAULT_NUM_CTX >= 2 * (tools + 1000), "the window must leave real room for the work"


def test_the_window_can_be_set_from_the_config(ollama_module):
    provider = OllamaProvider()
    provider.configure({"num_ctx": 65536})

    provider.chat("m", MESSAGES)

    assert ollama_module.chat.call_args.kwargs["options"]["num_ctx"] == 65536
    assert provider.context_window == 65536


def test_the_environment_wins_over_the_config(ollama_module, monkeypatch):
    monkeypatch.setenv("CORTEX_OLLAMA_NUM_CTX", "49152")
    provider = OllamaProvider()
    provider.configure({"num_ctx": 65536})

    assert provider.context_window == 49152


@pytest.mark.parametrize("bad", ["lots", "0", "-5", ""])
def test_an_unusable_setting_falls_back_to_the_default(ollama_module, monkeypatch, bad):
    monkeypatch.setenv("CORTEX_OLLAMA_NUM_CTX", bad)

    assert OllamaProvider().context_window == DEFAULT_NUM_CTX


def test_other_providers_have_no_fixed_window():
    assert ScriptedProvider([]).context_window is None


# ---- the conversation budget --------------------------------------------------------------


def test_limit_context_lowers_the_budget_and_never_raises_it():
    manager = ConversationManager(system_prompt="x", model="llama3.2")
    original = manager.max_tokens

    manager.limit_context(20000)
    assert manager.max_tokens == 20000 - RESPONSE_RESERVE_TOKENS

    manager.limit_context(10**7)
    assert manager.max_tokens == 20000 - RESPONSE_RESERVE_TOKENS < original


def test_limit_context_keeps_a_floor():
    manager = ConversationManager(system_prompt="x", model="llama3.2")

    manager.limit_context(100)

    assert manager.max_tokens == 2000


# ---- the agent ----------------------------------------------------------------------------


class WindowProvider(ScriptedProvider):
    def __init__(self, window):
        super().__init__([])
        self._window = window

    @property
    def context_window(self):
        return self._window


def make_agent(tmp_path, planning=False, window=None, model="llama3.2"):
    config = AgentConfig(
        model=model,
        provider="ollama",
        permission_mode=PermissionMode.AUTO_APPROVE,
        checkpoints={"enabled": False},
    )
    with patch("cortex.core.providers.factory.ProviderFactory.get_provider") as factory:
        factory.return_value = WindowProvider(window)
        return Cortex(
            model=model,
            project_dir=str(tmp_path),
            config=config,
            enable_planning=planning,
            enable_layered_memory=False,
        )


def tool_tokens(planning):
    exclude = (
        []
        if planning
        else ["monitor_plan", "update_plan", "create_and_execute_plan", "metacognitive_reflect"]
    )
    return estimate_tokens(
        json.dumps(get_registry().get_all_schemas(exclude_names=exclude)), "llama3.2"
    )


def test_history_budget_leaves_room_for_the_tool_definitions(tmp_path):
    agent = make_agent(tmp_path, window=32768)

    expected = 32768 - tool_tokens(planning=False) - RESPONSE_RESERVE_TOKENS
    assert agent.conversation.max_tokens == expected


def test_more_tools_mean_a_smaller_history_budget(tmp_path):
    lean = make_agent(tmp_path, planning=False, window=32768).conversation.max_tokens
    full = make_agent(tmp_path, planning=True, window=32768).conversation.max_tokens

    assert full < lean


def test_a_provider_without_a_fixed_window_changes_nothing(tmp_path):
    with_window = make_agent(tmp_path, window=None).conversation.max_tokens
    reference = ConversationManager(system_prompt="x", model="llama3.2").max_tokens

    assert with_window == reference


def test_a_window_too_small_for_the_tools_is_reported(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        make_agent(tmp_path, window=4096)

    warning = " ".join(r.getMessage() for r in caplog.records)
    assert "4096" in warning and "CORTEX_OLLAMA_NUM_CTX" in warning


def test_a_comfortable_window_is_not_reported(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        make_agent(tmp_path, window=32768)

    assert "CORTEX_OLLAMA_NUM_CTX" not in " ".join(r.getMessage() for r in caplog.records)


def test_switching_models_applies_the_new_providers_window(tmp_path):
    agent = make_agent(tmp_path, window=65536)
    large = agent.conversation.max_tokens

    with patch("cortex.core.providers.factory.ProviderFactory.get_provider") as factory:
        factory.return_value = WindowProvider(16384)
        agent.switch_model("other-model", provider_override="ollama", silent=True)

    assert agent.conversation.max_tokens < large
