"""Explicit memory: the remember tool, the /memory commands, and recall in a later session."""

import io

import pytest
from rich.console import Console

from cortex.agent import Cortex
from cortex.cli_commands.commands.base import CommandContext
from cortex.cli_commands.commands.memory import MemoryCommand
from cortex.config import AgentConfig
from cortex.core.memory.core_memory import MemorySource, MemoryType
from cortex.core.memory_layers.session import EnhancedMemoryBank
from cortex.models import PermissionMode

pytestmark = pytest.mark.usefixtures("stub_sentence_transformers")


def semantic(tmp_path, collection="remember_tests"):
    return {
        "enabled": True,
        "persist_directory": str(tmp_path / "semantic_db"),
        "collection_name": collection,
    }


def bank_for(tmp_path, session_id="s1", **kwargs):
    return EnhancedMemoryBank(semantic_config=semantic(tmp_path), session_id=session_id, **kwargs)


def make_agent(tmp_path, semantic_memory=None, session_label="a"):
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    config = AgentConfig(
        model="llama3.2",
        provider="ollama",
        permission_mode=PermissionMode.AUTO_APPROVE,
        semantic_memory=semantic_memory or {},
    )
    return Cortex(
        model="llama3.2",
        project_dir=str(project),
        permission_mode=PermissionMode.AUTO_APPROVE,
        config=config,
        enable_planning=False,
        enable_layered_memory=True,
    )


# ---- the bank ----------------------------------------------------------------------------


def test_a_convention_the_user_asked_for_is_stored_as_their_instruction(tmp_path):
    bank = bank_for(tmp_path)

    result = bank.remember("Always run the tests with pytest -x", "convention", user_requested=True)

    assert result["persistent"] is True
    record = bank.semantic_manager.get_document(result["id"])
    assert record["metadata"]["source"] == "user"  # explicit instructions do not fade
    assert record["metadata"]["type"] == "preference"
    assert bank.get_by_type(MemoryType.PREFERENCE)[0].source == MemorySource.USER


@pytest.mark.parametrize(
    "kind, stored_type",
    [
        ("convention", "preference"),
        ("decision", "decision"),
        ("fact", "fact"),
        ("solution", "context"),
    ],
)
def test_each_kind_is_stored_with_the_right_type(tmp_path, kind, stored_type):
    bank = bank_for(tmp_path)

    result = bank.remember("Something worth keeping for later", kind)

    assert bank.semantic_manager.get_document(result["id"])["metadata"]["type"] == stored_type


def test_a_model_initiated_memory_is_less_certain_than_a_users(tmp_path):
    bank = bank_for(tmp_path)

    mine = bank.remember("The API client lives in client.py", "fact")
    theirs = bank.remember("Never edit generated files", "convention", user_requested=True)

    mine_meta = bank.semantic_manager.get_document(mine["id"])["metadata"]
    theirs_meta = bank.semantic_manager.get_document(theirs["id"])["metadata"]
    assert mine_meta["source"] == "inferred" and mine_meta["confidence"] < theirs_meta["confidence"]


def test_remembering_the_same_thing_twice_keeps_one_entry(tmp_path):
    bank = bank_for(tmp_path)

    first = bank.remember("Use black with line length 100", "convention")
    second = bank.remember("use black with line length 100", "convention")

    assert first["id"] == second["id"]
    assert bank.semantic_manager.count() == 1


def test_without_long_term_memory_it_says_so_instead_of_pretending(tmp_path):
    bank = EnhancedMemoryBank(session_id="s1")  # semantic memory off

    result = bank.remember("Use black with line length 100", "convention")

    assert result["persistent"] is False
    assert "this session only" in result["message"].lower()
    assert bank.get_by_type(MemoryType.PREFERENCE)  # still available for the session


def test_a_convention_is_found_by_a_related_question_in_a_later_session(tmp_path):
    first_session = bank_for(tmp_path, session_id="monday")
    first_session.remember("Run the tests with pytest -x and never with unittest", "convention")
    first_session.remember("The staging database is reset every night", "fact")
    first_session.remember("Logos live in the assets folder", "fact")
    del first_session

    next_week = bank_for(tmp_path, session_id="friday")
    found = next_week.retrieve_semantic_context(
        "how do I run the tests?", top_k=1, global_search=True
    )

    assert found and "pytest -x" in found[0]["document"]


def test_list_edit_and_forget(tmp_path):
    bank = bank_for(tmp_path)
    kept = bank.remember("Use tabs for indentation", "convention")["id"]

    listed = bank.list_memories()
    assert [m["id"] for m in listed] == [kept]

    new_id = bank.edit_memory(kept, "Use four spaces for indentation")
    assert [m["document"] for m in bank.list_memories()] == ["Use four spaces for indentation"]

    assert bank.forget(new_id) is True
    assert bank.list_memories() == []
    assert bank.forget(new_id) is False


# ---- the tool, as the model calls it ------------------------------------------------------


def test_the_remember_tool_stores_and_reports_persistence(tmp_path):
    agent = make_agent(tmp_path, semantic(tmp_path, "tool_tests"))

    result = agent.execute_tool(
        "remember",
        {"content": "Deploys go out from the release branch", "kind": "decision"},
    )

    assert result["success"] is True
    assert result["data"]["persistent"] is True
    assert agent.memory_bank.semantic_manager.count() == 1


def test_the_remember_tool_is_honest_when_memory_is_off(tmp_path):
    agent = make_agent(tmp_path)  # semantic memory is off by default

    result = agent.execute_tool("remember", {"content": "Deploys go out from the release branch"})

    assert result["success"] is True
    assert result["data"]["persistent"] is False
    assert "this session only" in result["data"]["message"].lower()


@pytest.mark.parametrize(
    "arguments",
    [
        {"content": ""},
        {"content": "   "},
        {"content": "x" * 2000},
        {"content": "A perfectly good sentence", "kind": "gossip"},
    ],
)
def test_the_remember_tool_rejects_bad_input(tmp_path, arguments):
    agent = make_agent(tmp_path, semantic(tmp_path, "tool_bad_input"))

    result = agent.execute_tool("remember", arguments)

    assert result["success"] is False
    assert agent.memory_bank.semantic_manager.count() == 0


def test_a_later_session_is_given_the_convention_in_its_prompt(tmp_path):
    config = semantic(tmp_path, "prompt_tests")
    monday = make_agent(tmp_path, config)
    monday.execute_tool(
        "remember",
        {"content": "Run the tests with pytest -x", "kind": "convention", "user_requested": True},
    )

    friday = make_agent(tmp_path, config)
    friday.conversation.add_user_message("how do I run the tests?")

    assert "pytest -x" in friday._get_system_prompt()


def test_memory_that_has_nothing_to_do_with_the_question_is_not_injected(tmp_path):
    config = semantic(tmp_path, "relevance_tests")
    monday = make_agent(tmp_path, config)
    monday.execute_tool("remember", {"content": "Cafeteria closes at four on Fridays"})

    friday = make_agent(tmp_path, config)
    # (no words in common, so the test stub's similarity stays below the floor; real embedding
    # models separate unrelated sentences by more than this)
    friday.conversation.add_user_message("refactor parser module")

    prompt = friday._get_system_prompt()
    assert "afeteria" not in prompt
    assert "Relevant Historical Context" not in prompt


# ---- the /memory command ------------------------------------------------------------------


def run_memory(agent, args):
    out = io.StringIO()
    from unittest.mock import patch

    with patch(
        "cortex.cli_commands.commands.memory.console",
        Console(file=out, width=200, force_terminal=False),
    ):
        ctx = CommandContext(
            agent=agent, config=agent.config, hook_manager=agent.hook_manager, output_format="text"
        )
        MemoryCommand().execute(ctx, args)
    return out.getvalue()


def test_memory_list_shows_what_is_stored(tmp_path):
    agent = make_agent(tmp_path, semantic(tmp_path, "cmd_list"))
    agent.memory_bank.remember("Use black with line length 100", "convention", user_requested=True)

    output = run_memory(agent, "list")

    assert "Use black with line length 100" in output
    assert "convention" in output.lower() or "preference" in output.lower()


def test_memory_list_when_nothing_is_stored(tmp_path):
    agent = make_agent(tmp_path, semantic(tmp_path, "cmd_empty"))

    assert "nothing" in run_memory(agent, "list").lower()


def test_memory_add_stores_it_as_the_users_own_instruction(tmp_path):
    agent = make_agent(tmp_path, semantic(tmp_path, "cmd_add"))

    run_memory(agent, "add Never commit directly to main")

    entry = agent.memory_bank.list_memories()[0]
    assert entry["document"] == "Never commit directly to main"
    assert entry["metadata"]["source"] == "user"


def test_memory_delete_removes_an_entry_by_id_prefix(tmp_path):
    agent = make_agent(tmp_path, semantic(tmp_path, "cmd_delete"))
    doc_id = agent.memory_bank.remember("Temporary note to delete", "fact")["id"]

    output = run_memory(agent, f"delete {doc_id[:10]}")

    assert agent.memory_bank.list_memories() == []
    assert "deleted" in output.lower()


def test_memory_edit_changes_the_text(tmp_path):
    agent = make_agent(tmp_path, semantic(tmp_path, "cmd_edit"))
    doc_id = agent.memory_bank.remember("Use tabs for indentation", "convention")["id"]

    run_memory(agent, f"edit {doc_id[:10]} Use four spaces for indentation")

    assert [m["document"] for m in agent.memory_bank.list_memories()] == [
        "Use four spaces for indentation"
    ]


def test_an_unknown_id_is_reported_and_nothing_is_changed(tmp_path):
    agent = make_agent(tmp_path, semantic(tmp_path, "cmd_unknown"))
    agent.memory_bank.remember("Keep me around", "fact")

    output = run_memory(agent, "delete mem_nope")

    assert "no memory" in output.lower()
    assert len(agent.memory_bank.list_memories()) == 1


def test_an_ambiguous_id_prefix_is_refused(tmp_path):
    agent = make_agent(tmp_path, semantic(tmp_path, "cmd_ambiguous"))
    agent.memory_bank.remember("First thing to keep", "fact")
    agent.memory_bank.remember("Second thing to keep", "fact")

    output = run_memory(agent, "delete mem_")

    assert "matches" in output.lower()
    assert len(agent.memory_bank.list_memories()) == 2


def test_memory_commands_explain_when_long_term_memory_is_off(tmp_path):
    agent = make_agent(tmp_path)

    for args in ("list", "add Something to remember", "delete mem_x"):
        assert "long-term memory is off" in run_memory(agent, args).lower()
