"""The runner records the verifier's verdict, not the agent's opinion, plus honest metrics."""

import json

import pytest

from bench import report as reporting
from bench.runner import RunConfig, ablation_configs, cost, run_batch, run_task
from bench.suite import TASKS, get
from tests.e2e.scripted import ScriptedProvider, final, tool_call

TASK = get("bug-sum-to-off-by-one")
AGENT = dict(solver="agent", model="llama3.2", provider="ollama", max_iterations=10)


def solving_script(task):
    """A model that fixes the task by writing the reference solution with write_file."""
    script = [
        tool_call("write_file", {"path": name, "content": content}, f"w{i}")
        for i, (name, content) in enumerate(task.solution.items())
    ]
    return script + [final("Fixed.")]


class Reporting(ScriptedProvider):
    """A scripted model that reports token usage the way a real API does."""

    def chat(self, model, messages, tools=None):
        response = super().chat(model, messages, tools)
        response["usage"] = {"input_tokens": 100, "output_tokens": 10}
        return response


def run(task=TASK, factory=None, **overrides):
    config = RunConfig(**{**AGENT, **overrides})
    return run_task(task, config, provider_factory=factory)


# ---- the verdict --------------------------------------------------------------------------


def test_an_agent_that_fixes_the_bug_passes():
    result = run(factory=lambda task: ScriptedProvider(solving_script(task)))

    assert result.passed is True
    assert result.status == "ok"
    assert result.tool_calls == 1
    assert result.steps == 2  # one call to write the file, one to answer


def test_an_agent_that_only_claims_success_fails():
    result = run(factory=lambda task: ScriptedProvider([final("I fixed it, all tests pass!")]))

    assert result.passed is False
    assert result.status == "ok"  # the agent said it was done; the verifier disagrees
    assert "sum_to" in result.verifier_tail or "assert" in result.verifier_tail


def test_an_agent_that_rewrites_the_tests_still_fails():
    cheat = [
        tool_call(
            "write_file",
            {"path": "tests/test_mathutil.py", "content": "def test_ok():\n    assert True\n"},
        ),
        final("Done."),
    ]

    assert run(factory=lambda task: ScriptedProvider(cheat)).passed is False


def test_the_two_stand_ins():
    assert run_task(TASK, RunConfig(solver="oracle")).passed is True
    assert run_task(TASK, RunConfig(solver="noop")).passed is False


def test_every_task_can_be_solved_through_the_real_agent_loop():
    # the full path for all 20: copy, agent loop, write_file tool, verifier
    results = run_batch(
        [RunConfig(**AGENT)],
        TASKS,
        provider_factory=lambda task: ScriptedProvider(solving_script(task)),
    )

    assert len(results) == len(TASKS) >= 20
    assert [r.task_id for r in results if not r.passed] == []


# ---- metrics ------------------------------------------------------------------------------


def test_tokens_are_taken_from_the_providers_usage_when_it_reports_it():
    result = run(factory=lambda task: Reporting(solving_script(task)))

    assert (result.input_tokens, result.output_tokens) == (200, 20)  # two calls
    assert result.tokens_estimated is False


def test_tokens_are_estimated_and_flagged_when_the_provider_reports_none():
    result = run(factory=lambda task: ScriptedProvider(solving_script(task)))

    assert result.input_tokens > 0 and result.output_tokens >= 0
    assert result.tokens_estimated is True


def test_cost_needs_prices_and_is_never_guessed():
    reporting_model = lambda task: Reporting(solving_script(task))  # noqa: E731

    without = run(factory=reporting_model)
    priced = run(factory=reporting_model, price_in=3.0, price_out=15.0)

    assert without.cost_usd is None
    assert priced.cost_usd == pytest.approx((200 * 3.0 + 20 * 15.0) / 1e6)


def test_cost_function_edges():
    assert cost(RunConfig(price_in=1.0), 10, 10) is None  # only one price
    assert cost(RunConfig(price_in=1.0, price_out=1.0), None, None) is None


def test_a_crashing_run_is_recorded_not_raised():
    def broken(task):
        raise RuntimeError("provider exploded")

    result = run(factory=broken)

    assert result.status == "crashed"
    assert "provider exploded" in result.error
    assert result.passed is False


def test_the_agent_is_stopped_at_the_step_limit():
    endless = [tool_call("read_file", {"path": f"missing{i}.py"}, f"c{i}") for i in range(50)]

    result = run(factory=lambda task: ScriptedProvider(endless), max_iterations=3)

    assert result.passed is False
    assert result.status in ("max_iterations", "loop_guard")
    assert result.steps <= 4


# ---- settings -----------------------------------------------------------------------------


def test_ablation_covers_every_combination():
    configs = ablation_configs(RunConfig(**AGENT), ["planning", "memory", "metacognition"])

    assert len(configs) == 8
    assert len({c.label for c in configs}) == 8
    assert RunConfig(**AGENT).label in {c.label for c in configs}


def test_ablating_one_factor_leaves_the_others_as_set():
    configs = ablation_configs(RunConfig(**AGENT, planning=True), ["memory"])

    assert {(c.planning, c.memory) for c in configs} == {(True, False), (True, True)}


def test_an_unknown_factor_is_rejected():
    with pytest.raises(ValueError, match="mood"):
        ablation_configs(RunConfig(), ["mood"])


def test_planning_on_gives_the_agent_the_planning_tools():
    seen = {}

    def factory(task):
        provider = ScriptedProvider([final("nothing to do")])
        original = provider.chat

        def spy(model, messages, tools=None):
            seen["tools"] = {t["function"]["name"] for t in (tools or [])}
            return original(model, messages, tools)

        provider.chat = spy
        return provider

    run(factory=factory, planning=True)
    with_planning = seen["tools"]
    run(factory=factory, planning=False)

    assert "create_and_execute_plan" in with_planning
    assert "create_and_execute_plan" not in seen["tools"]


# ---- reports ------------------------------------------------------------------------------


def test_report_summary_and_markdown():
    configs = [RunConfig(**AGENT)]
    results = run_batch(
        configs,
        [TASK, get("refactor-move-function")],
        runs=2,
        provider_factory=lambda task: ScriptedProvider(
            solving_script(task) if task.id == TASK.id else [final("no changes")]
        ),
    )

    report = reporting.build_report(results, configs, runs=2, label="unit")
    row = report["summary"][configs[0].label]

    assert row["runs"] == 4 and row["passed"] == 2
    assert row["pass_rate"] == 0.5
    assert row["pass_rate_by_kind"] == {"bugfix": 1.0, "refactor": 0.0}
    assert row["total_cost_usd"] is None
    markdown = reporting.to_markdown(report)
    assert "2/4" in markdown and "50%" in markdown and "n/a" in markdown
    assert "refactor-move-function" in markdown  # failures are listed


def test_report_is_saved_as_json_and_markdown(tmp_path):
    configs = [RunConfig(solver="oracle")]
    report = reporting.build_report(run_batch(configs, [TASK]), configs, runs=1, label="x")

    path = reporting.save(report, tmp_path, "x")

    assert json.loads(path.read_text())["summary"]["solver=oracle"]["passed"] == 1
    assert path.with_suffix(".md").read_text().startswith("# Benchmark report: x")
