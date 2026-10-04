"""Running the command that decides whether a task succeeded.

The agent saying it is done proves nothing; the verify command (the project's tests, a linter, a
build) exiting 0 does. It runs in the task's own directory with no terminal, and is stopped,
together with everything it started, if it hangs.

It also runs code the agent wrote (the tests it added or changed, a conftest, a build script), so
when a command sandbox is configured the verify command goes through it too. If the sandbox is
asked for and cannot be provided, the command is not run at all.
"""

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..core.command_sandbox import SandboxConfig, SandboxUnavailable, confine, shell_argv

# How much of the end of the output is kept: enough to see the failures, small enough to send back
# to the model
TAIL_CHARS = 4000


@dataclass
class VerifyOutcome:
    passed: bool
    exit_code: Optional[int]  # None when it timed out or was not run
    output: str  # the end of its combined stdout and stderr
    seconds: float
    timed_out: bool = False


def _kill_tree(process: "subprocess.Popen[str]") -> None:
    try:
        if sys.platform == "win32":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)  # it leads its own process group
    except (ProcessLookupError, PermissionError):
        process.kill()


def run_verify(
    command: str,
    cwd: Path,
    timeout_s: float,
    sandbox: Optional[SandboxConfig] = None,
) -> VerifyOutcome:
    """Run ``command`` (a shell command line) in ``cwd``; it passes when it exits 0."""
    started = time.monotonic()
    try:
        confined = confine(shell_argv(command), cwd, sandbox)
    except SandboxUnavailable as e:
        return VerifyOutcome(False, None, f"The verify command was not run: {e}", 0.0)

    options: Dict[str, Any] = {
        "cwd": cwd,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "errors": "replace",
    }
    if sys.platform != "win32":
        options["start_new_session"] = True  # so a timeout can stop everything it started
    process = (
        subprocess.Popen(command, shell=True, **options)  # nosec B602 - the operator's command
        if confined is None
        else subprocess.Popen(confined, **options)
    )

    timed_out = False
    try:
        output, _ = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(process)
        output, _ = process.communicate()

    tail = (output or "")[-TAIL_CHARS:]
    if timed_out:
        tail += f"\n[the verify command timed out after {timeout_s:g}s and was stopped]"
    return VerifyOutcome(
        passed=not timed_out and process.returncode == 0,
        exit_code=None if timed_out else process.returncode,
        output=tail,
        seconds=round(time.monotonic() - started, 2),
        timed_out=timed_out,
    )
