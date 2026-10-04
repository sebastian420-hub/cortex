"""The verify command is the gate: nothing counts as done until it exits 0. It runs in the task's
own directory, is stopped if it hangs, and goes through the command sandbox when one is set,
because it runs code the agent wrote."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from cortex.core.command_sandbox import SandboxConfig, SandboxUnavailable
from cortex.headless import verify as verify_module
from cortex.headless.verify import TAIL_CHARS, run_verify

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX shell")


def py(code: str) -> str:
    """A shell command that runs ``code`` with this Python."""
    import shlex

    return f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"


def test_exit_zero_passes(tmp_path):
    outcome = run_verify(py("print('all good')"), tmp_path, timeout_s=30)

    assert outcome.passed is True and outcome.exit_code == 0
    assert "all good" in outcome.output and outcome.timed_out is False


def test_a_nonzero_exit_fails_and_keeps_the_output(tmp_path):
    outcome = run_verify(
        py("import sys; print('3 failed'); print('oops', file=sys.stderr); sys.exit(2)"),
        tmp_path,
        timeout_s=30,
    )

    assert outcome.passed is False and outcome.exit_code == 2
    assert "3 failed" in outcome.output and "oops" in outcome.output  # both streams


def test_it_runs_in_the_given_directory(tmp_path):
    (tmp_path / "marker.txt").write_text("here")

    outcome = run_verify(py("print(open('marker.txt').read())"), tmp_path, timeout_s=30)

    assert outcome.passed and "here" in outcome.output


def test_a_command_that_does_not_exist_fails(tmp_path):
    outcome = run_verify("definitely-not-a-command-xyz", tmp_path, timeout_s=30)

    assert outcome.passed is False and outcome.exit_code != 0


def test_only_the_end_of_long_output_is_kept(tmp_path):
    outcome = run_verify(py("print('x' * 50000); print('THE-END')"), tmp_path, timeout_s=30)

    assert len(outcome.output) <= TAIL_CHARS + 50
    assert outcome.output.rstrip().endswith("THE-END")


def test_unreadable_bytes_do_not_break_it(tmp_path):
    outcome = run_verify(
        py("import sys; sys.stdout.buffer.write(b'\\xff\\xfe bad bytes\\n')"),
        tmp_path,
        timeout_s=30,
    )

    assert outcome.passed and "bad bytes" in outcome.output


@posix_only
def test_a_hung_command_is_stopped_with_everything_it_started(tmp_path):
    started = time.monotonic()

    outcome = run_verify("sleep 30 & wait", tmp_path, timeout_s=0.5)

    assert time.monotonic() - started < 10
    assert outcome.timed_out is True and outcome.passed is False
    assert "timed out" in outcome.output.lower()


def test_it_goes_through_the_sandbox_when_one_is_configured(tmp_path, monkeypatch):
    seen = {}

    def fake_confine(argv, project_dir, config):
        seen["argv"], seen["dir"], seen["config"] = list(argv), project_dir, config
        return ["/bin/sh", "-c", "echo ran-confined"]

    monkeypatch.setattr(verify_module, "confine", fake_confine)
    config = SandboxConfig(mode="bubblewrap")

    outcome = run_verify("pytest -q", tmp_path, timeout_s=30, sandbox=config)

    assert outcome.passed and "ran-confined" in outcome.output
    assert seen["argv"] == ["/bin/sh", "-c", "pytest -q"]
    assert seen["config"] is config and seen["dir"] == tmp_path


def test_a_sandbox_that_cannot_be_provided_means_the_command_is_not_run(tmp_path, monkeypatch):
    def unavailable(argv, project_dir, config):
        raise SandboxUnavailable("bwrap is not installed")

    monkeypatch.setattr(verify_module, "confine", unavailable)
    marker = tmp_path / "ran"

    outcome = run_verify(
        f"touch {marker}", tmp_path, timeout_s=30, sandbox=SandboxConfig("bubblewrap")
    )

    assert outcome.passed is False
    assert "bwrap is not installed" in outcome.output
    assert (
        not marker.exists()
    )  # failing closed: never run unconfined when confinement was asked for


def _bwrap_works() -> bool:
    if not (
        sys.platform.startswith("linux") and shutil.which("bwrap") and os.path.isdir("/var/tmp")
    ):
        return False
    return (
        subprocess.run(["bwrap", "--ro-bind", "/", "/", "true"], capture_output=True).returncode
        == 0
    )


@pytest.mark.skipif(not _bwrap_works(), reason="bubblewrap is not usable here")
def test_the_real_sandbox_confines_the_command(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    # /var/tmp, not /tmp: the sandbox swaps /tmp for a private one, so a write there never
    # reaches the real directory whether or not it is confined
    outside = Path(tempfile.mkdtemp(dir="/var/tmp"))
    try:
        outcome = run_verify(
            f"touch inside.txt && touch {outside}/outside.txt",
            project,
            timeout_s=30,
            sandbox=SandboxConfig(mode="bubblewrap"),
        )

        assert outcome.passed is False  # the second write is outside the project
        assert (project / "inside.txt").exists()
        assert not (outside / "outside.txt").exists()
    finally:
        shutil.rmtree(outside, ignore_errors=True)
