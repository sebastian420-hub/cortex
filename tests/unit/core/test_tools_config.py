"""`tools.disabled` and `tools.plugins` in the configuration must take effect.

Both were read from the config file into the config object and then never used: a tool listed
under `tools.disabled` was still offered to the model and still ran, and a configured plugin was
never loaded. Loading the setting is not enough (invariant 4: honest configuration); the effect has
to be tested.
"""

import sys
import types

import pytest

from cortex.agent import Cortex
from cortex.config import AgentConfig
from cortex.models import PermissionMode
from cortex.tools.base import Tool
from cortex.tools.registry import reset_registry
from tests.e2e.scripted import ScriptedProvider, final, tool_call


class Recording(ScriptedProvider):
    """Remembers which tools were offered on each model call."""

    def __init__(self, script):
        super().__init__(script)
        self.offered = []

    def chat(self, model, messages, tools=None):
        self.offered.append([t["function"]["name"] for t in (tools or [])])
        return super().chat(model, messages, tools)


@pytest.fixture(autouse=True)
def fresh_registry():
    """Plugins register into a process-wide registry; do not let them outlive a test."""
    reset_registry()
    yield
    reset_registry()


def tool_names(agent: Cortex) -> set:
    return {t["function"]["name"] for t in agent._enabled_tool_schemas()}


def make_agent(tmp_path, script=(), **config) -> Cortex:
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        config=AgentConfig(
            model="llama3.2",
            provider="ollama",
            permission_mode=PermissionMode.AUTO_APPROVE,
            checkpoints={"enabled": False},
            **config,
        ),
        enable_planning=False,
        enable_layered_memory=False,
    )
    agent.provider = Recording(list(script))
    return agent


# ---- tools.disabled -----------------------------------------------------------------------


def test_a_disabled_tool_is_not_offered_to_the_model(tmp_path):
    agent = make_agent(tmp_path, [final("ok")], tools_disabled=["web_search", "git_push"])

    agent._process_message("hello")

    offered = agent.provider.offered[0]
    assert "web_search" not in offered and "git_push" not in offered
    assert "read_file" in offered and "write_file" in offered


def test_a_disabled_tool_is_refused_if_the_model_calls_it_anyway(tmp_path):
    agent = make_agent(tmp_path, tools_disabled=["write_file"])

    result = agent.execute_tool("write_file", {"path": "x.txt", "content": "hi"})

    assert result["success"] is False
    assert "disabled" in result["error"]
    assert not (tmp_path / "x.txt").exists()


def test_the_model_sees_the_refusal_when_it_calls_a_disabled_tool(tmp_path):
    script = [tool_call("write_file", {"path": "x.txt", "content": "hi"}), final("done")]
    agent = make_agent(tmp_path, script, tools_disabled=["write_file"])

    agent._process_message("write x.txt")

    tool_message = [m for m in agent.conversation.get_history() if m["role"] == "tool"][0]
    assert "disabled" in tool_message["content"]
    assert not (tmp_path / "x.txt").exists()


def test_tools_that_are_not_disabled_still_work(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    agent = make_agent(tmp_path, tools_disabled=["write_file"])

    result = agent.execute_tool("read_file", {"path": "a.txt"})

    assert result["success"] is True


def test_a_disabled_tool_does_not_count_against_the_context_window(tmp_path):
    plain = make_agent(tmp_path)
    trimmed = make_agent(tmp_path, tools_disabled=["web_search", "web_fetch", "git_push"])

    assert len(trimmed._enabled_tool_schemas()) == len(plain._enabled_tool_schemas()) - 3


def test_disabling_a_tool_in_one_agent_leaves_other_agents_alone(tmp_path):
    first = make_agent(tmp_path, tools_disabled=["web_search"])
    second = make_agent(tmp_path)

    assert "web_search" not in tool_names(first)
    assert "web_search" in tool_names(second)


def test_a_name_that_is_not_a_tool_is_harmless(tmp_path):
    plain = make_agent(tmp_path)
    odd = make_agent(tmp_path, tools_disabled=["no_such_tool"])

    assert len(odd._enabled_tool_schemas()) == len(plain._enabled_tool_schemas())


def test_the_yaml_form_works_end_to_end(tmp_path):
    import yaml

    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump({"tools": {"disabled": ["web_search"]}}))

    config = AgentConfig.load(path)

    assert config.tools_disabled == ["web_search"]


# ---- tools.plugins ------------------------------------------------------------------------


class EchoTool(Tool):
    def execute(self, text: str = ""):
        return {"success": True, "data": f"echo: {text}"}


@pytest.fixture
def plugin_module(monkeypatch):
    module = types.ModuleType("cortex_test_plugin")
    module.PLUGIN_TOOLS = [
        {
            "name": "echo_plugin",
            "class": EchoTool,
            "schema": {
                "type": "function",
                "function": {
                    "name": "echo_plugin",
                    "description": "Echo the text back",
                    "parameters": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                },
            },
        }
    ]
    monkeypatch.setitem(sys.modules, "cortex_test_plugin", module)
    return module


def test_a_configured_plugin_is_loaded_and_offered(tmp_path, plugin_module):
    agent = make_agent(tmp_path, [final("ok")], tools_plugins=["cortex_test_plugin"])

    agent._process_message("hello")

    assert "echo_plugin" in agent.provider.offered[0]


def test_a_plugin_tool_can_be_used(tmp_path, plugin_module):
    agent = make_agent(tmp_path, tools_plugins=["cortex_test_plugin"])

    result = agent.execute_tool("echo_plugin", {"text": "hi"})

    assert result["success"] is True and "echo: hi" in str(result)


def test_without_the_setting_the_plugin_is_not_there(tmp_path, plugin_module):
    agent = make_agent(tmp_path)

    assert "echo_plugin" not in tool_names(agent)


def test_a_plugin_that_cannot_be_loaded_is_reported_but_does_not_stop_startup(tmp_path, caplog):
    import logging

    with caplog.at_level(logging.WARNING):
        agent = make_agent(tmp_path, tools_plugins=["no_such_plugin_module"])

    assert agent is not None
    assert "no_such_plugin_module" in " ".join(r.getMessage() for r in caplog.records)


def test_a_plugin_tool_can_be_disabled_too(tmp_path, plugin_module):
    agent = make_agent(
        tmp_path, tools_plugins=["cortex_test_plugin"], tools_disabled=["echo_plugin"]
    )

    assert "echo_plugin" not in tool_names(agent)
    assert agent.execute_tool("echo_plugin", {"text": "x"})["success"] is False


def test_two_agents_loading_the_same_plugin_is_fine(tmp_path, plugin_module):
    make_agent(tmp_path, tools_plugins=["cortex_test_plugin"])
    second = make_agent(tmp_path, tools_plugins=["cortex_test_plugin"])

    assert "echo_plugin" in tool_names(second)


# ---- calling a namespaced tool by the name the model is shown --------------------------------


def test_a_namespaced_tool_is_found_by_the_name_in_its_schema():
    from cortex.tools.registry import ToolRegistry

    registry = ToolRegistry()
    schema = {"type": "function", "function": {"name": "echo", "description": "d"}}
    registry.register("echo", EchoTool, schema, namespace="plugin")

    assert registry.get_tool_class("echo") is EchoTool  # what the model calls it
    assert registry.get_tool_class("plugin:echo") is EchoTool  # the full name still works
    assert registry.get_schema("echo") == schema
    assert registry.is_enabled("echo") is True


def test_a_short_name_shared_by_two_tools_is_not_guessed():
    from cortex.tools.registry import ToolRegistry

    registry = ToolRegistry()
    schema = {"type": "function", "function": {"name": "echo"}}
    registry.register("echo", EchoTool, schema, namespace="one")
    registry.register("echo", EchoTool, schema, namespace="two")

    assert registry.get_tool_class("echo") is None
    assert registry.get_tool_class("one:echo") is EchoTool


def test_an_exact_name_wins_over_a_short_name():
    from cortex.tools.registry import ToolRegistry

    class Builtin(EchoTool):
        pass

    registry = ToolRegistry()
    schema = {"type": "function", "function": {"name": "echo"}}
    registry.register("echo", Builtin, schema)  # builtin namespace: key is "echo"
    registry.register("echo", EchoTool, schema, namespace="plugin")

    assert registry.get_tool_class("echo") is Builtin


def test_a_disabled_namespaced_tool_stays_disabled_under_its_short_name():
    from cortex.tools.registry import ToolRegistry

    registry = ToolRegistry()
    schema = {"type": "function", "function": {"name": "echo"}}
    registry.register("echo", EchoTool, schema, namespace="plugin", enabled=False)

    assert registry.get_tool_class("echo") is None
    assert registry.is_enabled("echo") is False
