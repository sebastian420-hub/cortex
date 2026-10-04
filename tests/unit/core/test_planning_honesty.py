"""The planning engine must never claim success it did not earn (invariant 1)."""

from cortex.core.planning import PlanningEngine, PlanStepStatus, result_excerpt


def _engine(results):
    """An engine whose tool executor returns the given results in order."""
    queue = list(results)
    return PlanningEngine(tool_executor=lambda name, args: queue.pop(0))


def _step(step_id, deps=()):
    return {
        "id": step_id,
        "description": f"step {step_id}",
        "step_type": "tool_call",
        "tool_name": "read_file",
        "tool_arguments": {"path": f"{step_id}.txt"},
        "dependencies": list(deps),
    }


OK = {"success": True, "data": {"content": "file body"}}
BAD = {"success": False, "error": "File not found: b.txt"}


def test_new_plan_without_steps_is_empty():
    plan = PlanningEngine().create_plan("any goal")
    assert len(plan) == 0


def test_failed_step_fails_the_plan_even_when_not_stopping_on_failure():
    engine = _engine([OK, BAD, OK])
    plan = engine.create_plan("g", steps=[_step("a"), _step("b"), _step("c")])

    result = engine.execute_plan(plan, stop_on_failure=False)

    assert result["success"] is False
    assert "step b" in result["error"]
    assert "File not found: b.txt" in result["error"]
    assert plan.status.value == "failed"


def test_steps_blocked_behind_a_failure_are_reported():
    engine = _engine([OK, BAD])
    plan = engine.create_plan("g", steps=[_step("a"), _step("b", ["a"]), _step("c", ["b"])])

    result = engine.execute_plan(plan, stop_on_failure=False)

    assert result["success"] is False
    assert "1 step(s) were not run" in result["error"]
    assert plan.get_step_by_id("c").status == PlanStepStatus.PENDING


def test_error_result_carries_per_step_outcomes_for_the_model():
    engine = _engine([OK, BAD])
    plan = engine.create_plan("g", steps=[_step("a"), _step("b", ["a"])])

    result = engine.execute_plan(plan)

    steps = result["error_context"]["steps"]
    assert [s["status"] for s in steps] == ["completed", "failed"]
    assert steps[0]["output"] == "file body"
    assert "File not found" in steps[1]["error"]


def test_plan_summary_shows_why_a_step_failed():
    engine = _engine([BAD])
    plan = engine.create_plan("g", steps=[_step("b")])
    engine.execute_plan(plan)

    assert "File not found: b.txt" in engine.get_plan_summary(plan)


def test_successful_plan_reports_each_step():
    engine = _engine([OK, OK])
    plan = engine.create_plan("g", steps=[_step("a"), _step("b", ["a"])])

    result = engine.execute_plan(plan)

    assert result["success"] is True
    assert [s["status"] for s in result["data"]["steps"]] == ["completed", "completed"]


def test_result_excerpt_is_bounded():
    big = {"success": True, "data": {"content": "x" * 5000}}
    excerpt = result_excerpt(big, limit=100)
    assert len(excerpt) < 200
    assert "truncated" in excerpt


def test_result_excerpt_prefers_the_error_for_failures():
    assert result_excerpt({"success": False, "error": "boom"}) == "boom"
