"""End-to-end tests for the six invariants a coding agent must keep.

Each test drives the real agent loop with a scripted model (no network):

1. Truthful signals     - a result says "success" only if it succeeded
2. Valid conversation   - every tool request is followed by its result
3. Reversible/approved  - changes can be undone, and PLAN mode changes nothing
4. Honest configuration - what is set in config is what runs (see tests/unit/test_config_*.py)
5. Useful memory        - records are not duplicated
6. Measured claims      - covered by the benchmark harness (see bench/)
"""

import json

import pytest

from cortex.models import PermissionMode

from .scripted import final, tool_call, tool_order_violations


def _text(result) -> str:
    return json.dumps(result, default=str).lower()


def _read_step(step_id="s1", path="does_not_exist.py"):
    return {
        "id": step_id,
        "description": f"read {path}",
        "step_type": "tool_call",
        "tool_name": "read_file",
        "tool_arguments": {"path": path},
    }


# --------------------------------------------------------------------------------------
# The basic loop (must always work)
# --------------------------------------------------------------------------------------


def test_basic_loop_runs_tool_then_answers(make_agent):
    agent = make_agent([tool_call("read_file", {"path": "a.py"}), final("hello returns 1")])
    agent._process_message("what does a.py do?")

    roles = [m["role"] for m in agent.conversation.get_history()]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    assert len(agent.provider.seen) == 2
    assert not tool_order_violations(agent.provider.seen[1])


# --------------------------------------------------------------------------------------
# Invariant 1: truthful signals
# --------------------------------------------------------------------------------------


def test_failed_plan_returns_an_error(make_agent):
    agent = make_agent()
    result = agent.execute_tool("create_and_execute_plan", {"goal": "g", "steps": [_read_step()]})
    assert result["success"] is False
    assert "does_not_exist" in _text(result)


def test_plan_without_steps_is_rejected_with_a_clear_error(make_agent):
    agent = make_agent()
    result = agent.execute_tool("create_and_execute_plan", {"goal": "fix a bug in hello"})
    assert result["success"] is False
    assert "steps" in _text(result)
    assert "unexpected keyword" not in _text(result)


@pytest.mark.parametrize("step_type", ["subtask", "decision", "checkpoint"])
def test_unimplemented_plan_steps_do_not_report_success(make_agent, step_type):
    agent = make_agent()
    step = {"id": "s1", "description": "Refactor everything", "step_type": step_type}
    result = agent.execute_tool("create_and_execute_plan", {"goal": "g", "steps": [step]})
    assert result["success"] is False
    assert "not implemented" in _text(result)


def test_skill_step_loads_a_real_skill(make_agent):
    agent = make_agent()
    step = {
        "id": "s1",
        "description": "apply tdd skill",
        "step_type": "skill_application",
        "skill_name": "TDD_WORKFLOW",
    }
    result = agent.execute_tool("create_and_execute_plan", {"goal": "g", "steps": [step]})
    assert agent.planning_engine.active_plan.steps[0].status.value == "completed"
    assert result["success"] is True


def test_unknown_skill_step_fails_clearly(make_agent):
    agent = make_agent()
    step = {
        "id": "s1",
        "description": "apply missing skill",
        "step_type": "skill_application",
        "skill_name": "no_such_skill",
    }
    result = agent.execute_tool("create_and_execute_plan", {"goal": "g", "steps": [step]})
    assert result["success"] is False
    assert "no_such_skill" in _text(result)


def test_mood_counts_consecutive_failures_not_total(make_agent):
    script = [tool_call("read_file", {"path": f"missing{i}.py"}, f"f{i}") for i in range(3)]
    script += [tool_call("read_file", {"path": "a.py"}, f"s{i}") for i in range(8)]
    script += [tool_call("read_file", {"path": "missing_last.py"}, "flast"), final("done")]
    agent = make_agent(script)

    agent._process_message("exercise the appraisal")

    meta = agent.state_manager.state.metacognition
    assert meta.emotional_tone != "frustrated"
    assert meta.urgency_score < 1.0


def test_turn_returns_a_structured_result(make_agent):
    agent = make_agent([tool_call("read_file", {"path": "a.py"}), final("ok")])
    result = agent._process_message("read it")
    assert result is not None
    assert result.status == "ok"
    assert result.final_text == "ok"


def test_turn_that_raises_reports_error_status(make_agent):
    agent = make_agent()

    def boom(*_args, **_kwargs):
        raise RuntimeError("provider exploded")

    agent.provider.chat = boom
    result = agent._process_message("hello")
    assert result is not None
    assert result.status == "error"
    assert "provider exploded" in (result.error or "")


# --------------------------------------------------------------------------------------
# Invariant 2: valid conversation
# --------------------------------------------------------------------------------------


def test_message_order_is_valid_after_a_plan_runs(make_agent):
    steps = [
        _read_step("s1", "a.py"),
        {
            "id": "s2",
            "description": "list files",
            "step_type": "tool_call",
            "tool_name": "list_files",
            "tool_arguments": {},
            "dependencies": ["s1"],
        },
    ]
    plan = tool_call("create_and_execute_plan", {"goal": "inspect", "steps": steps}, "PLAN1")
    agent = make_agent([plan, final("done")])

    agent._process_message("inspect the project with a plan")

    assert len(agent.provider.seen) == 2
    assert tool_order_violations(agent.provider.seen[1]) == []


def test_agent_repairs_a_broken_tool_order_before_sending(make_agent, monkeypatch):
    monkeypatch.delenv("CORTEX_STRICT_MESSAGES")  # production behaviour: repair, do not raise
    agent = make_agent()
    history = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "go"},
        tool_call("read_file", {"path": "a.py"}, "c1"),
        {"role": "assistant", "content": "interleaved note"},
        {"role": "tool", "tool_call_id": "c1", "content": "ok"},
    ]
    assert tool_order_violations(history) != []

    sent = agent._prepare_messages_for_api(history)

    assert tool_order_violations(sent) == []


def test_strict_mode_raises_on_a_broken_tool_order(make_agent):
    agent = make_agent()
    history = [
        {"role": "system", "content": "sys"},
        tool_call("read_file", {"path": "a.py"}, "c1"),
        {"role": "user", "content": "interleaved"},
    ]
    with pytest.raises(Exception, match="tool-call message order"):
        agent._prepare_messages_for_api(history)


# --------------------------------------------------------------------------------------
# Invariant 3: reversible or approved
# --------------------------------------------------------------------------------------


def test_edit_can_be_rolled_back_with_the_rollback_command(make_agent, project):
    from cortex.cli_commands.commands.base import CommandContext
    from cortex.cli_commands.commands.transaction import RollbackCommand

    original = (project / "a.py").read_text()
    edit = tool_call(
        "edit", {"file_path": "a.py", "old_string": "return 1", "new_string": "return 2"}
    )
    agent = make_agent([edit, final("edited")], planning=False)
    agent._process_message("change hello to return 2")
    assert "return 2" in (project / "a.py").read_text()

    ctx = CommandContext(
        agent=agent, config=agent.config, hook_manager=agent.hook_manager, output_format="text"
    )
    RollbackCommand().execute(ctx)

    assert (project / "a.py").read_text() == original


def test_plan_mode_does_not_run_project_code(make_agent, project):
    agent = make_agent(mode=PermissionMode.PLAN, planning=False)
    agent.execute_tool("run_tests", {})
    assert not (project / "RAN_MARKER.txt").exists()


def test_plan_mode_blocks_every_mutating_tool(make_agent, project):
    agent = make_agent(mode=PermissionMode.PLAN, planning=False)
    original = (project / "a.py").read_text()
    attempts = [
        ("edit", {"file_path": "a.py", "old_string": "return 1", "new_string": "return 2"}),
        ("write_file", {"path": "new.txt", "content": "x"}),
        ("execute_command", {"command": "touch cmd_ran.txt"}),
        (
            "ast_refactor",
            {
                "file_path": "a.py",
                "action": "rename_symbol",
                "symbol_name": "hello",
                "new_name": "hi",
            },
        ),
    ]
    for name, args in attempts:
        agent.execute_tool(name, args)
    assert (project / "a.py").read_text() == original
    assert not (project / "new.txt").exists()
    assert not (project / "cmd_ran.txt").exists()


def test_every_registered_tool_has_a_policy_class():
    from cortex.core.tool_policy import ToolClass, classify_tool
    from cortex.tools import get_registry

    names = [s["function"]["name"] for s in get_registry().get_all_schemas()]
    unclassified = [n for n in names if not isinstance(classify_tool(n), ToolClass)]
    assert unclassified == []


def test_ast_rename_refuses_when_other_files_use_the_symbol(make_agent, project):
    (project / "m.py").write_text("def compute(x):\n    return x + 1\n")
    (project / "n.py").write_text("from m import compute\nprint(compute(5))\n")
    agent = make_agent(planning=False)
    before = (project / "m.py").read_text()

    result = agent.execute_tool(
        "ast_refactor",
        {
            "file_path": "m.py",
            "action": "rename_symbol",
            "symbol_name": "compute",
            "new_name": "calc",
        },
    )

    assert result["success"] is False
    assert "n.py" in _text(result)
    assert (project / "m.py").read_text() == before


def test_ast_rename_with_file_scope_is_explicit_opt_in(make_agent, project):
    (project / "m.py").write_text("def compute(x):\n    return x + 1\n")
    (project / "n.py").write_text("from m import compute\nprint(compute(5))\n")
    agent = make_agent(planning=False)

    result = agent.execute_tool(
        "ast_refactor",
        {
            "file_path": "m.py",
            "action": "rename_symbol",
            "symbol_name": "compute",
            "new_name": "calc",
            "scope": "file",
        },
    )

    assert result["success"] is True
    assert "def calc" in (project / "m.py").read_text()


# --------------------------------------------------------------------------------------
# Invariant 5: useful memory
# --------------------------------------------------------------------------------------


def test_one_failed_tool_call_is_recorded_once(make_agent):
    agent = make_agent([tool_call("read_file", {"path": "missing.py"}), final("it failed")])
    agent._process_message("read a missing file")
    assert len(agent.memory_bank.failed_approaches) == 1


def test_state_text_uses_real_newlines(make_agent):
    agent = make_agent()
    manager = agent.state_manager
    manager.set_primary_goal("refactor the module")
    manager.state.working_memory.add_insight("x is used in y", priority=3)

    text = manager.get_llm_context()

    assert "\n" in text
    assert "\\n" not in text


def test_state_summary_works_with_an_active_plan(make_agent):
    agent = make_agent()
    plan = agent.planning_engine.create_plan(
        "inspect", steps=[{"id": "s1", "description": "d", "step_type": "tool_call"}]
    )
    agent.state_manager.set_active_plan(plan)

    summary = agent.state_manager.get_state_summary()

    assert "inspect" in summary
