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
    "test_edit_can_be_rolled_back_with_the_rollback_command": "P3-1: transactions not wired in",
    "test_ast_rename_refuses_when_other_files_use_the_symbol": "P3-5: rename is single-file",
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
    # A broken tool-call order must fail the test loudly instead of being quietly repaired
    # before it reaches the provider.
    monkeypatch.setenv("CORTEX_STRICT_MESSAGES", "1")
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
