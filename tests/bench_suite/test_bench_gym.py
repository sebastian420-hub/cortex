"""The Cognitive Gym on the benchmark: its verdict comes from the task's tests."""

import tempfile
from pathlib import Path

import pytest

from bench.suite import get
from cortex.agent import Cortex
from cortex.config import AgentConfig
from cortex.core.gym.manager import GymManager
from cortex.models import PermissionMode
from tests.e2e.scripted import ScriptedProvider, final, tool_call

TASK = get("bug-sum-to-off-by-one")


@pytest.fixture
def real_project(tmp_path):
    project = tmp_path / "real_project"
    project.mkdir()
    (project / "keep.txt").write_text("my real files\n")
    return project


def agent_for(project: Path, script):
    config = AgentConfig(
        model="llama3.2",
        provider="ollama",
        permission_mode=PermissionMode.AUTO_APPROVE,
        checkpoints={"enabled": False},
    )
    agent = Cortex(
        model="llama3.2",
        project_dir=str(project),
        permission_mode=PermissionMode.AUTO_APPROVE,
        config=config,
        enable_planning=False,
        enable_layered_memory=False,
    )
    agent.provider = ScriptedProvider(script)
    return agent


def solving_script():
    return [
        tool_call("write_file", {"path": name, "content": content}, f"w{i}")
        for i, (name, content) in enumerate(TASK.solution.items())
    ] + [final("Fixed.")]


def test_a_session_that_fixes_the_task_passes_its_verifier(real_project):
    agent = agent_for(real_project, solving_script())

    outcome = GymManager(agent).run_benchmark_task(TASK.id)

    assert outcome["verified"] is True
    assert outcome["success"] is True


def test_a_session_that_only_says_it_is_done_fails(real_project):
    agent = agent_for(real_project, [final("All done, everything passes now!")])

    outcome = GymManager(agent).run_benchmark_task(TASK.id)

    assert outcome["turn_ok"] is True  # the model finished
    assert outcome["verified"] is True
    assert outcome["success"] is False  # but the tests say otherwise
    assert "sum_to" in outcome["error"] or "assert" in outcome["error"]


def test_the_real_project_is_never_touched(real_project):
    agent = agent_for(real_project, solving_script())

    GymManager(agent).run_benchmark_task(TASK.id)

    assert agent.project_dir == real_project
    assert sorted(p.name for p in real_project.iterdir()) == ["keep.txt"]
    assert (real_project / "keep.txt").read_text() == "my real files\n"


def test_the_scratch_project_is_removed_afterwards(real_project):
    agent = agent_for(real_project, solving_script())

    outcome = GymManager(agent).run_benchmark_task(TASK.id)

    assert not Path(outcome["sandbox"]).exists()


def test_an_unknown_task_lists_the_valid_ones(real_project):
    agent = agent_for(real_project, [])

    outcome = GymManager(agent).run_benchmark_task("no-such-task")

    assert outcome["success"] is False
    assert "bug-sum-to-off-by-one" in outcome["error"]


def test_the_task_prompt_reaches_the_model(real_project):
    agent = agent_for(real_project, [final("ok")])

    GymManager(agent).run_benchmark_task(TASK.id)

    first_user_message = next(m for m in agent.provider.seen[0] if m["role"] == "user")["content"]
    assert TASK.prompt in first_user_message
