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

from .scripted import final, tool_call, tool_calls, tool_order_violations


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


# ---- the loop guard: stops a turn that keeps failing the same way ----------------------


def test_repeating_the_same_error_stops_the_turn(make_agent):
    script = [tool_call("read_file", {"path": "missing.py"}, f"c{i}") for i in range(6)]
    agent = make_agent(script)

    result = agent._process_message("keep trying")

    assert result.status == "loop_guard"
    assert "read_file" in result.error
    assert len(agent.provider.seen) == 3  # stopped on the third identical failure


def test_different_errors_do_not_trip_the_loop_guard(make_agent):
    script = [tool_call("read_file", {"path": f"missing{i}.py"}, f"c{i}") for i in range(4)]
    script.append(final("gave up politely"))
    agent = make_agent(script)

    result = agent._process_message("try several files")

    assert result.status == "ok"


def test_loop_guard_history_resets_between_turns(make_agent):
    def failing_turn(prefix):
        return [
            tool_call("read_file", {"path": "missing.py"}, f"{prefix}{i}") for i in range(2)
        ] + [final("done")]

    agent = make_agent(failing_turn("a") + failing_turn("b"))

    first = agent._process_message("first request")
    second = agent._process_message("second request")

    assert first.status == "ok"
    assert second.status == "ok"  # would be loop_guard if turn one's errors still counted


def test_guard_guidance_never_lands_inside_a_batch_of_tool_results(make_agent):
    batch = tool_calls(
        ("read_file", {"path": "missing.py"}, "x1"), ("read_file", {"path": "missing.py"}, "x2")
    )
    agent = make_agent(
        [batch, batch, batch, final("done")], error_recovery={"enable_smart_recovery": True}
    )

    agent._process_message("two failing reads at a time")

    # Strict mode raises if any call sent a broken tool order; also check what was sent.
    assert all(tool_order_violations(sent) == [] for sent in agent.provider.seen)


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


def _rollback(agent):
    from cortex.cli_commands.commands.base import CommandContext
    from cortex.cli_commands.commands.transaction import RollbackCommand

    ctx = CommandContext(
        agent=agent, config=agent.config, hook_manager=agent.hook_manager, output_format="text"
    )
    RollbackCommand().execute(ctx)


def test_rollback_removes_a_file_the_agent_created(make_agent, project):
    agent = make_agent(
        [tool_call("write_file", {"path": "new.txt", "content": "hi"}), final("done")],
        planning=False,
    )
    agent._process_message("create new.txt")
    assert (project / "new.txt").exists()

    _rollback(agent)

    assert not (project / "new.txt").exists()


def test_rollback_undoes_every_change_of_the_turn(make_agent, project):
    (project / "b.py").write_text("B0\n")
    original_a = (project / "a.py").read_text()
    agent = make_agent(
        [
            tool_call(
                "edit",
                {"file_path": "a.py", "old_string": "return 1", "new_string": "return 2"},
                "c1",
            ),
            tool_call("write_file", {"path": "b.py", "content": "B1\n"}, "c2"),
            tool_call(
                "edit",
                {"file_path": "a.py", "old_string": "return 2", "new_string": "return 3"},
                "c3",
            ),
            final("done"),
        ],
        planning=False,
    )
    agent._process_message("change things")
    assert "return 3" in (project / "a.py").read_text()

    _rollback(agent)

    assert (project / "a.py").read_text() == original_a
    assert (project / "b.py").read_text() == "B0\n"


def test_rollback_restores_the_exact_bytes(make_agent, project):
    original = b"def hello():\r\n    return 1\r\n"  # CRLF: a text round trip would change it
    (project / "crlf.py").write_bytes(original)
    agent = make_agent(
        [tool_call("write_file", {"path": "crlf.py", "content": "replaced\n"}), final("ok")],
        planning=False,
    )
    agent._process_message("overwrite crlf.py")
    assert (project / "crlf.py").read_bytes() != original

    _rollback(agent)

    assert (project / "crlf.py").read_bytes() == original


def test_rollback_only_undoes_the_latest_message(make_agent, project):
    agent = make_agent(
        [
            tool_call(
                "edit", {"file_path": "a.py", "old_string": "return 1", "new_string": "return 2"}
            ),
            final("first done"),
            tool_call("write_file", {"path": "later.txt", "content": "x"}, "c2"),
            final("second done"),
        ],
        planning=False,
    )
    agent._process_message("first")
    agent._process_message("second")

    _rollback(agent)

    assert not (project / "later.txt").exists()
    assert "return 2" in (project / "a.py").read_text()


def test_rollback_with_nothing_to_undo_is_harmless(make_agent, project):
    agent = make_agent([final("nothing to change")], planning=False)
    original = (project / "a.py").read_text()
    agent._process_message("just talk")

    _rollback(agent)
    _rollback(agent)

    assert (project / "a.py").read_text() == original


def test_ending_the_session_finishes_the_open_transaction(make_agent, project):
    agent = make_agent(
        [tool_call("write_file", {"path": "kept.txt", "content": "x"}), final("done")],
        planning=False,
    )
    agent._process_message("create kept.txt")
    assert agent.transaction_manager.has_active_transaction()

    agent._cleanup()

    assert not agent.transaction_manager.has_active_transaction()
    assert (project / "kept.txt").exists()


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


def _rename(agent, **overrides):
    args = {
        "file_path": "m.py",
        "action": "rename_symbol",
        "symbol_name": "compute",
        "new_name": "calc",
    }
    args.update(overrides)
    return agent.execute_tool("ast_refactor", args)


def test_ast_rename_ignores_files_that_only_share_a_prefix(make_agent, project):
    (project / "m.py").write_text("def compute(x):\n    return x + 1\n")
    (project / "n.py").write_text("def compute_all(xs):\n    return [x for x in xs]\n")
    agent = make_agent(planning=False)

    result = _rename(agent)

    assert result["success"] is True
    assert "def calc(" in (project / "m.py").read_text()


def test_ast_rename_ignores_vendored_and_cache_directories(make_agent, project):
    (project / "m.py").write_text("def compute(x):\n    return x + 1\n")
    for folder in ("node_modules/pkg", ".venv/lib", "__pycache__", "build"):
        (project / folder).mkdir(parents=True)
        (project / folder / "x.py").write_text("compute(1)\n")
    agent = make_agent(planning=False)

    assert _rename(agent)["success"] is True


def test_ast_rename_refusal_names_every_file_and_the_way_out(make_agent, project):
    (project / "m.py").write_text("def compute(x):\n    return x + 1\n")
    for name in ("n.py", "o.py"):
        (project / name).write_text("from m import compute\n")
    (project / "sub").mkdir()
    (project / "sub" / "p.py").write_text("import m\nm.compute(1)\n")
    agent = make_agent(planning=False)

    result = _rename(agent)

    text = _text(result)
    assert result["success"] is False
    for name in ("n.py", "o.py", "p.py"):
        assert name in text
    assert "scope" in text and "file" in text


def test_ast_rename_refusal_caps_a_long_list_but_gives_the_count(make_agent, project):
    (project / "m.py").write_text("def compute(x):\n    return x + 1\n")
    for i in range(25):
        (project / f"user_{i:02d}.py").write_text("from m import compute\n")
    agent = make_agent(planning=False)

    result = _rename(agent)

    text = _text(result)
    assert result["success"] is False
    assert "25" in text  # the real total is stated
    assert "user_00.py" in text
    assert "user_24.py" not in text  # past the cap, not listed
    assert "5 more" in text


def test_ast_rename_rejects_an_unknown_scope(make_agent, project):
    (project / "m.py").write_text("def compute(x):\n    return x + 1\n")
    agent = make_agent(planning=False)

    result = _rename(agent, scope="everywhere")

    assert result["success"] is False
    assert "scope" in _text(result)
    assert "def compute(" in (project / "m.py").read_text()


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


def _count_retrievals(agent):
    """Replace semantic retrieval with a counting stub and return the list of queries it saw."""
    queries = []

    def retrieve(query, top_k=3, global_search=False):
        queries.append((query, global_search))
        return []

    agent.memory_bank.retrieve_semantic_context = retrieve
    return queries


def test_semantic_retrieval_runs_once_per_user_message(make_agent, project):
    for name in ("b.py", "c.py"):
        (project / name).write_text(f"# {name}\n")
    agent = make_agent(
        [
            tool_call("read_file", {"path": "a.py"}, "c1"),
            tool_call("read_file", {"path": "b.py"}, "c2"),
            tool_call("read_file", {"path": "c.py"}, "c3"),
            final("done"),
        ]
    )
    queries = _count_retrievals(agent)

    agent._process_message("look at the three files")

    # One session lookup and one global lookup for the message, however many iterations ran.
    assert len(agent.provider.seen) == 4
    assert sorted(g for _, g in queries) == [False, True]


def test_each_new_user_message_retrieves_again(make_agent):
    agent = make_agent([final("one"), final("two")])
    queries = _count_retrievals(agent)

    agent._process_message("first question")
    agent._process_message("second question")

    assert [q for q, _ in queries].count("first question") == 2
    assert [q for q, _ in queries].count("second question") == 2
