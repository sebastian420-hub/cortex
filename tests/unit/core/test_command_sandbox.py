"""Optional confinement for shell commands, and the promise it makes (and does not make).

By default commands run with the user's own permissions. With ``mode: bubblewrap`` they run in a
namespace where the project directory is the only writable place. If that mode is asked for but
cannot be provided, the command must be refused, never quietly run unconfined.
"""

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from cortex.core.command_sandbox import (
    SandboxConfig,
    SandboxUnavailable,
    confine,
    describe,
)
from cortex.models import PermissionMode
from cortex.tools.command_tools import ExecuteCommandTool


def _bwrap_usable() -> bool:
    if not shutil.which("bwrap"):
        return False
    probe = subprocess.run(
        ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--", "/bin/true"],
        capture_output=True,
    )
    return probe.returncode == 0


needs_bwrap = pytest.mark.skipif(not _bwrap_usable(), reason="bubblewrap cannot run here")


# ---- configuration -----------------------------------------------------------------------


def test_default_is_no_confinement():
    config = SandboxConfig.from_dict({})
    assert config.mode == "none"
    assert confine(["echo", "hi"], Path("/p"), config) is None


def test_an_unknown_mode_is_an_error_not_a_silent_fallback():
    with pytest.raises(ValueError, match="bubblwrap"):
        SandboxConfig.from_dict({"mode": "bubblwrap"})


def test_from_dict_reads_every_field():
    config = SandboxConfig.from_dict(
        {"mode": "bubblewrap", "network": False, "private_home": True, "writable": ["/data"]}
    )
    assert (config.mode, config.network, config.private_home, config.writable) == (
        "bubblewrap",
        False,
        True,
        ("/data",),
    )


# ---- the command line that is built ------------------------------------------------------


def _argv(tmp_path, **options):
    config = SandboxConfig.from_dict({"mode": "bubblewrap", **options})
    return confine(["/bin/sh", "-c", "echo hi"], tmp_path, config, bwrap="/usr/bin/bwrap")


def test_project_is_the_writable_place(tmp_path):
    argv = _argv(tmp_path)

    assert argv[0] == "/usr/bin/bwrap"
    assert argv[argv.index("--ro-bind") + 1 : argv.index("--ro-bind") + 3] == ["/", "/"]
    bind = argv.index("--bind")
    assert argv[bind + 1 : bind + 3] == [str(tmp_path), str(tmp_path)]
    assert argv[argv.index("--chdir") + 1] == str(tmp_path)
    assert argv[-4:] == ["--", "/bin/sh", "-c", "echo hi"]
    for flag in ("--die-with-parent", "--new-session", "--unshare-pid"):
        assert flag in argv


def test_tmp_is_private_and_mounted_before_the_project(tmp_path):
    argv = _argv(tmp_path)

    # a project that lives under /tmp must still be visible, so the tmpfs comes first
    assert argv.index("--tmpfs") < argv.index("--bind")
    assert argv[argv.index("--tmpfs") + 1] == "/tmp"


def test_network_is_allowed_unless_switched_off(tmp_path):
    assert "--unshare-net" not in _argv(tmp_path)
    assert "--unshare-net" in _argv(tmp_path, network=False)


def test_private_home_hides_the_home_directory_but_not_a_project_inside_it(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "home" / "work"
    project.mkdir(parents=True)

    argv = confine(
        ["/bin/true"],
        project,
        SandboxConfig.from_dict({"mode": "bubblewrap", "private_home": True}),
        bwrap="bwrap",
    )

    tmpfs_targets = [argv[i + 1] for i, a in enumerate(argv) if a == "--tmpfs"]
    assert str(tmp_path / "home") in tmpfs_targets
    last_home_tmpfs = max(i for i, a in enumerate(argv) if a == "--tmpfs")
    assert last_home_tmpfs < argv.index("--bind"), "the project must be bound after home is hidden"


def test_extra_writable_paths_are_bound_and_missing_ones_skipped(tmp_path):
    extra = tmp_path / "cache"
    extra.mkdir()
    argv = _argv(tmp_path / "proj_missing_ok", writable=[str(extra), str(tmp_path / "nope")])

    binds = [argv[i + 1] for i, a in enumerate(argv) if a == "--bind"]
    assert str(extra) in binds
    assert str(tmp_path / "nope") not in binds


# ---- when it cannot be provided ----------------------------------------------------------


def test_missing_bwrap_refuses_instead_of_running_unconfined(tmp_path, monkeypatch):
    monkeypatch.setattr("cortex.core.command_sandbox.shutil.which", lambda name: None)
    config = SandboxConfig.from_dict({"mode": "bubblewrap"})

    with pytest.raises(SandboxUnavailable, match="bubblewrap"):
        confine(["/bin/true"], tmp_path, config)


def test_tool_refuses_to_run_when_the_sandbox_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr("cortex.core.command_sandbox.shutil.which", lambda name: None)
    tool = ExecuteCommandTool(
        tmp_path,
        PermissionMode.AUTO_APPROVE,
        None,
        command_sandbox=SandboxConfig.from_dict({"mode": "bubblewrap"}),
    )

    result = tool.execute(command="touch should_not_exist.txt")

    assert result["success"] is False
    assert "bubblewrap" in str(result).lower()
    assert not (tmp_path / "should_not_exist.txt").exists()


def test_run_tests_also_refuses_when_the_sandbox_is_unavailable(tmp_path, monkeypatch):
    from cortex.tools.test_tools import RunTestsTool

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(
        "import pathlib\n\ndef test_x():\n    pathlib.Path('ran.txt').write_text('x')\n"
    )
    monkeypatch.setattr("cortex.core.command_sandbox.shutil.which", lambda name: None)
    tool = RunTestsTool(
        tmp_path,
        PermissionMode.AUTO_APPROVE,
        None,
        command_sandbox=SandboxConfig.from_dict({"mode": "bubblewrap"}),
    )

    result = tool.execute()

    assert result["success"] is False
    assert "bubblewrap" in str(result).lower()
    assert not (tmp_path / "ran.txt").exists()


def test_describe_says_what_each_mode_does_and_does_not_do():
    none = describe(SandboxConfig.from_dict({}))
    assert "not isolated" in none.lower() or "no isolation" in none.lower()

    wrapped = describe(SandboxConfig.from_dict({"mode": "bubblewrap"}))
    assert "write" in wrapped.lower() and "project" in wrapped.lower()
    assert "read" in wrapped.lower()  # it must admit the rest of the disk stays readable
    assert "network" in wrapped.lower()
    private = describe(SandboxConfig.from_dict({"mode": "bubblewrap", "network": False}))
    assert private != wrapped


# ---- the real thing ----------------------------------------------------------------------


def _tool(project: Path, **options) -> ExecuteCommandTool:
    return ExecuteCommandTool(
        project,
        PermissionMode.AUTO_APPROVE,
        None,
        command_sandbox=SandboxConfig.from_dict({"mode": "bubblewrap", **options}),
    )


@needs_bwrap
def test_confined_command_can_write_in_the_project(tmp_path):
    result = _tool(tmp_path).execute(command="echo inside > made.txt && cat made.txt")

    assert result["success"] is True, result
    assert (tmp_path / "made.txt").read_text() == "inside\n"
    assert "inside" in result["data"]["output"]


@needs_bwrap
def test_confined_command_cannot_write_outside_the_project(tmp_path):
    probe = Path("/usr") / f"cortex_sandbox_probe_{uuid.uuid4().hex}"
    try:
        result = _tool(tmp_path).execute(command=f"touch {probe}")

        assert result["success"] is False
        assert not probe.exists(), "the command escaped the sandbox"
        assert "read-only" in str(result).lower()
    finally:
        if probe.exists():
            probe.unlink()


@needs_bwrap
def test_tmp_inside_the_sandbox_is_private(tmp_path):
    marker = f"cortex_private_tmp_{uuid.uuid4().hex}"
    try:
        result = _tool(tmp_path).execute(command=f"touch /tmp/{marker} && ls /tmp")

        assert result["success"] is True, result
        assert marker in result["data"]["output"]
        assert not Path("/tmp", marker).exists(), "the sandbox's /tmp leaked to the host"
    finally:
        Path("/tmp", marker).unlink(missing_ok=True)


@needs_bwrap
def test_exit_code_and_output_still_come_back(tmp_path):
    result = _tool(tmp_path).execute(command="echo before; exit 3")

    assert result["success"] is False
    assert result["error_context"]["exit_code"] == 3
    assert "before" in result["error_context"]["output"]


@needs_bwrap
def test_a_runaway_command_is_stopped_by_the_timeout(tmp_path):
    tool = _tool(tmp_path)
    tool.default_timeout = 1

    result = tool.execute(command="sleep 30")

    assert result["success"] is False
    assert "timed out" in str(result).lower()


@needs_bwrap
def test_network_can_be_cut_off(tmp_path):
    result = _tool(tmp_path, network=False).execute(command="cat /proc/net/dev")

    interfaces = [
        line.split(":")[0].strip() for line in result["data"]["output"].splitlines() if ":" in line
    ]
    assert interfaces == ["lo"]


# ---- plumbing ----------------------------------------------------------------------------


def _registered_tool_names():
    from cortex.tools import get_registry

    return [s["function"]["name"] for s in get_registry().get_all_schemas()]


@pytest.mark.parametrize("name", _registered_tool_names())
def test_every_registered_tool_can_be_created_with_the_sandbox_and_transactions(name, tmp_path):
    """Several tools have fixed constructor signatures; adding a keyword to the factory once broke
    all of the planning tools. Creating each one is the cheap way to catch the next such change."""
    from unittest.mock import MagicMock

    from cortex.core.transaction import TransactionManager
    from cortex.tools import create_tool_instance

    tool = create_tool_instance(
        name,
        tmp_path,
        PermissionMode.NORMAL,
        None,
        parent_agent=MagicMock(),
        transaction_manager=TransactionManager(backup_dir=tmp_path / "b", enabled=False),
        command_sandbox=SandboxConfig.from_dict({"mode": "bubblewrap"}),
    )

    if name in ("execute_command", "run_tests"):  # the tools that actually run commands
        assert tool._command_sandbox.mode == "bubblewrap"


def test_the_agent_gives_its_sandbox_to_the_tools_it_runs(make_agent_for_sandbox):
    agent = make_agent_for_sandbox({"mode": "bubblewrap", "network": False})

    assert agent.command_sandbox.mode == "bubblewrap"
    assert agent.command_sandbox.network is False


@pytest.fixture
def make_agent_for_sandbox(tmp_path):
    from cortex.agent import Cortex
    from cortex.config import AgentConfig

    def _make(sandbox):
        config = AgentConfig(model="llama3.2", provider="ollama", command_sandbox=sandbox)
        return Cortex(
            model="llama3.2",
            project_dir=str(tmp_path),
            config=config,
            enable_planning=False,
            enable_layered_memory=False,
        )

    return _make


def test_a_misspelt_sandbox_mode_stops_the_agent_at_startup(make_agent_for_sandbox):
    with pytest.raises(ValueError, match="bubblwrap"):
        make_agent_for_sandbox({"mode": "bubblwrap"})
