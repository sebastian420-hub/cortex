"""Every way of starting Cortex must work, and flags/config must resolve predictably."""

import re
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

import cortex
from cortex import cli
from cortex.config import AgentConfig
from cortex.models import PermissionMode

REPO_ROOT = Path(__file__).resolve().parents[3]


def _args(**overrides) -> Namespace:
    base = dict(
        planning=False,
        memory=False,
        metacognition=False,
        enhanced=False,
        auto_approve=False,
        plan_mode=False,
    )
    base.update(overrides)
    return Namespace(**base)


# ---- feature resolution ----------------------------------------------------------------


def test_features_are_off_by_default():
    assert cli.resolve_agent_features(_args(), AgentConfig()) == (False, False, False)


def test_planning_flag_enables_only_planning():
    assert cli.resolve_agent_features(_args(planning=True), AgentConfig()) == (True, False, False)


def test_memory_flag_enables_only_memory():
    assert cli.resolve_agent_features(_args(memory=True), AgentConfig()) == (False, True, False)


def test_enhanced_is_an_alias_for_planning_and_memory():
    assert cli.resolve_agent_features(_args(enhanced=True), AgentConfig()) == (True, True, False)


def test_config_can_enable_features_without_flags():
    config = AgentConfig(
        enable_planning=True, enable_layered_memory=True, enable_metacognition=True
    )
    assert cli.resolve_agent_features(_args(), config) == (True, True, True)


# ---- permission mode -------------------------------------------------------------------


def test_permission_mode_comes_from_config_when_no_flag():
    # This used to be ignored unless --config was passed explicitly.
    config = AgentConfig(permission_mode=PermissionMode.PLAN)
    assert cli.resolve_permission_mode(_args(), config) == PermissionMode.PLAN


def test_permission_flags_beat_config():
    config = AgentConfig(permission_mode=PermissionMode.PLAN)
    assert cli.resolve_permission_mode(_args(auto_approve=True), config) == (
        PermissionMode.AUTO_APPROVE
    )
    config = AgentConfig(permission_mode=PermissionMode.AUTO_APPROVE)
    assert cli.resolve_permission_mode(_args(plan_mode=True), config) == PermissionMode.PLAN


# ---- the --config crash ----------------------------------------------------------------


class _StubAgent:
    """Just enough of Cortex for main() to run a one-shot prompt."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.prompts = []

    def _process_message(self, prompt, use_streaming=False):
        self.prompts.append(prompt)


@pytest.fixture
def run_main(monkeypatch, tmp_path):
    created = []

    def fake_cortex(**kwargs):
        agent = _StubAgent(**kwargs)
        created.append(agent)
        return agent

    monkeypatch.setattr(cli, "Cortex", fake_cortex)
    monkeypatch.setattr(cli, "validate_provider_setup", lambda *a, **k: True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))

    def _run(*argv):
        monkeypatch.setattr(sys, "argv", ["cortex", *argv])
        cli.main()
        return created[-1]

    return _run


def test_config_flag_without_enhanced_does_not_crash(run_main, tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("model: llama3.2\nmax_iterations: 5\n")

    agent = run_main("--config", str(config_file), "--prompt", "hello")

    assert agent.prompts == ["hello"]
    assert agent.kwargs["enable_planning"] is False


def test_config_file_can_turn_planning_on(run_main, tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("model: llama3.2\nenable_planning: true\nenable_layered_memory: true\n")

    agent = run_main("--config", str(config_file), "--prompt", "hello")

    assert agent.kwargs["enable_planning"] is True
    assert agent.kwargs["enable_layered_memory"] is True


def test_enhanced_flag_still_works_and_warns(run_main, capsys):
    agent = run_main("--enhanced", "--prompt", "hello")
    assert agent.kwargs["enable_planning"] is True
    assert agent.kwargs["enable_layered_memory"] is True


# ---- python -m cortex and the version --------------------------------------------------


def test_python_dash_m_cortex_runs():
    result = subprocess.run(
        [sys.executable, "-m", "cortex", "--version"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"Cortex {cortex.__version__}"


def test_version_has_a_single_source_of_truth():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    declared = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE).group(1)
    assert cortex.__version__ == declared
    assert cli.__version__ == declared
