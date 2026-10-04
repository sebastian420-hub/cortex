"""The benchmark's own quality gate: every task must fail as shipped and pass when solved."""

import tempfile
from pathlib import Path

import pytest

from bench.suite import TASKS, get, select
from bench.task import apply_solution, materialize, verify


def test_there_are_enough_tasks_of_both_kinds():
    assert len(TASKS) >= 20
    assert sum(t.kind == "bugfix" for t in TASKS) >= 15
    assert sum(t.kind == "refactor" for t in TASKS) >= 5


def test_task_ids_are_unique():
    ids = [t.id for t in TASKS]
    assert len(ids) == len(set(ids))


def test_selecting_by_id_and_kind():
    assert [t.id for t in select(["bug-sum-to-off-by-one"])] == ["bug-sum-to-off-by-one"]
    assert all(t.kind == "refactor" for t in select(kind="refactor"))
    with pytest.raises(KeyError):
        get("no-such-task")


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_task_is_well_formed(task):
    assert task.prompt.strip()
    for name in task.protected:
        assert name in task.files, f"{name} must be part of the starting project"
        assert name not in task.solution, "the reference solution must not touch the tests"
    assert task.solution, "a task needs a reference solution"


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_task_fails_as_shipped_and_passes_when_solved(task):
    with tempfile.TemporaryDirectory() as scratch:
        project = Path(scratch) / "project"
        materialize(task, project)

        before = verify(task, project)
        apply_solution(task, project)
        after = verify(task, project)

    assert not before.passed, "a task that already passes tests nothing"
    assert after.passed, after.output
    if task.kind == "bugfix":
        # it must fail on the planted bug, not because the tests cannot even be loaded
        assert "error during collection" not in before.output.lower(), before.output
        assert "ModuleNotFoundError" not in before.output, before.output
        assert "AssertionError" in before.output or "Error" in before.output


def test_a_bug_fix_prompt_does_not_give_away_the_fix():
    # prompts describe symptoms; they must not contain the corrected line itself
    for task in TASKS:
        if task.kind != "bugfix":
            continue
        for name, fixed in task.solution.items():
            changed = [
                line.strip()
                for line in fixed.splitlines()
                if line.strip() and line.strip() not in task.files[name]
            ]
            for line in changed:
                assert line not in task.prompt, (task.id, line)
