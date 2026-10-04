"""A benchmark task, and how it is checked.

The verifier restores the task's own test files before running them, so an agent cannot pass by
editing or deleting tests, and refuses to run if the agent added files that could change what the
tests do (a conftest.py, a pytest.py, a config file).
"""

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Mapping, Tuple

# Files that, if the agent created them, could change how the tests run
TAMPER_NAMES = (
    "conftest.py",
    "pytest.py",
    "sitecustomize.py",
    "usercustomize.py",
    "pytest.ini",
    "tox.ini",
    "setup.cfg",
    "pyproject.toml",
)


@dataclass(frozen=True)
class Task:
    id: str
    kind: str  # "bugfix" or "refactor"
    title: str
    prompt: str  # what the agent is asked, in the words a user would use
    files: Mapping[str, str]  # the starting project (path -> content)
    solution: Mapping[str, str]  # files the reference solution changes or adds
    protected: Tuple[str, ...]  # test files: restored, then run, by the verifier
    timeout: int = 60  # seconds the verifier may take


@dataclass
class VerifyResult:
    passed: bool
    output: str
    seconds: float
    tampered: Tuple[str, ...] = ()


def _write(root: Path, files: Mapping[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def materialize(task: Task, destination: Path) -> None:
    """Create the starting project in ``destination``."""
    destination.mkdir(parents=True, exist_ok=True)
    _write(destination, task.files)


def apply_solution(task: Task, project: Path) -> None:
    """Apply the reference solution (used to prove the task can be solved)."""
    _write(project, task.solution)


def restore_protected(task: Task, project: Path) -> None:
    _write(project, {name: task.files[name] for name in task.protected})


def tampering(task: Task, project: Path) -> List[str]:
    """Files the agent added that could change how the tests run."""
    found = []
    for path in project.rglob("*"):
        if path.is_file() and path.name in TAMPER_NAMES:
            relative = path.relative_to(project).as_posix()
            if relative not in task.files:
                found.append(relative)
    return sorted(found)


def verify(task: Task, project: Path) -> VerifyResult:
    """Run the task's tests against ``project``. Passing means the tests pass, nothing more."""
    started = time.monotonic()
    tampered = tampering(task, project)
    if tampered:
        return VerifyResult(
            False,
            "refused to run: the project contains files that could change the tests: "
            + ", ".join(tampered),
            time.monotonic() - started,
            tuple(tampered),
        )

    restore_protected(task, project)
    environment = {
        k: v
        for k, v in os.environ.items()
        if k not in ("PYTEST_ADDOPTS", "PYTHONPATH", "PYTEST_PLUGINS")
    }
    environment["PYTHONPATH"] = str(project)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="bench-ini-") as ini_dir:
        empty_config = Path(ini_dir) / "pytest.ini"
        empty_config.write_text("[pytest]\n")
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-x",
            "--noconftest",
            "-p",
            "no:cacheprovider",
            "-c",
            str(empty_config),
            "--rootdir",
            str(project),
            *task.protected,
        ]
        try:
            done = subprocess.run(
                command,
                cwd=project,
                env=environment,
                capture_output=True,
                text=True,
                timeout=task.timeout,
            )
            passed, output = done.returncode == 0, done.stdout + done.stderr
        except subprocess.TimeoutExpired:
            passed, output = False, f"timed out after {task.timeout} seconds"
    return VerifyResult(passed, output, time.monotonic() - started)
