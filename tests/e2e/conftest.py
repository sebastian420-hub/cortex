"""Fixtures for the end-to-end scenario tests."""

import subprocess
from pathlib import Path
from typing import Callable, Sequence

import pytest

from cortex.agent import Cortex
from cortex.config import AgentConfig
from cortex.models import PermissionMode

from .scripted import ScriptedProvider

# Known bugs, one entry per test that currently fails. Each is registered as a strict expected
# failure, so the suite stays green today and the moment a fix lands its test flips to
# "unexpectedly passed" and forces the entry to be deleted. The list below is the open-bug list.
KNOWN_BUGS = {
    "test_failed_plan_returns_an_error": "P2-1: a failed plan is reported as a success",
    "test_unknown_skill_step_fails_clearly": "P2-1: a failed plan is reported as a success",
    "test_plan_without_steps_is_rejected_with_a_clear_error": "P2-4: starter plan fails in grep",
    "test_unimplemented_plan_steps_do_not_report_success": "P2-4: placeholder steps fake success",
    "test_skill_step_loads_a_real_skill": "P2-4: the skill loader is a stub returning {}",
    "test_mood_counts_consecutive_failures_not_total": "P2-5: mood counts total failures",
    "test_turn_returns_a_structured_result": "P2-8: turns return None, not a result",
    "test_turn_that_raises_reports_error_status": "P2-8: turn errors are swallowed",
    "test_message_order_is_valid_after_a_plan_runs": "P2-2: plan steps break tool-call order",
    "test_edit_can_be_rolled_back_with_the_rollback_command": "P3-1: transactions not wired in",
    "test_plan_mode_does_not_run_project_code": "P3-3: run_tests runs in PLAN mode",
    "test_every_registered_tool_has_a_policy_class": "P3-3: no tool classification exists",
    "test_ast_rename_refuses_when_other_files_use_the_symbol": "P3-5: rename is single-file",
    "test_one_failed_tool_call_is_recorded_once": "P2-3: learnings are extracted twice",
    "test_state_text_uses_real_newlines": "P2-6: state text has literal backslash-n",
    "test_state_summary_works_with_an_active_plan": "P2-6: get_state_summary reads active_goal",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        reason = KNOWN_BUGS.get(getattr(item, "originalname", None) or item.name)
        if reason and "tests/e2e" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.xfail(strict=True, reason=reason, raises=Exception))


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Keep ~/.cortex (sessions, backups, memory) out of the real home directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.fixture
def project(tmp_path) -> Path:
    """A small git project with a source file and a test that leaves a marker when run."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "a.py").write_text("def hello():\n    return 1\n")
    (root / "test_marker.py").write_text(
        "def test_marker():\n    open('RAN_MARKER.txt', 'w').write('ran')\n"
    )
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    import os

    full_env = {**os.environ, **env}
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, env=full_env)
    subprocess.run(["git", "add", "."], cwd=root, check=True, env=full_env)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True, env=full_env)
    return root


@pytest.fixture
def make_agent(project) -> Callable[..., Cortex]:
    """Build a real ``Cortex`` agent wired to a ``ScriptedProvider``."""

    def _make(
        script: Sequence[dict] = (),
        mode: str = PermissionMode.AUTO_APPROVE,
        planning: bool = True,
        max_iterations: int = 50,
        **config_overrides,
    ) -> Cortex:
        config = AgentConfig(
            model="llama3.2",
            provider="ollama",
            permission_mode=mode,
            max_iterations=max_iterations,
            **config_overrides,
        )
        agent = Cortex(
            model="llama3.2",
            project_dir=str(project),
            permission_mode=mode,
            config=config,
            enable_planning=planning,
            enable_layered_memory=planning,
        )
        agent.provider = ScriptedProvider(list(script))
        return agent

    return _make
