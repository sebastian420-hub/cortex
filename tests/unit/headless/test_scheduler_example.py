"""The scheduling examples must work as shipped. The wrapper script is run here against a fake
`cortex` command, so what it does around a run (locking, a time limit, pushing only a branch that
verified, keeping and clearing results) is checked rather than assumed."""

import configparser
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.unit.headless.gitutil import git

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "scheduled"
SCRIPT = EXAMPLES / "run-task.sh"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or not shutil.which("bash") or not shutil.which("timeout"),
    reason="needs bash and GNU timeout",
)

FAKE_CORTEX = """#!/usr/bin/env bash
# A stand-in for `cortex`: records how it was called and writes the result it is told to.
echo "$@" > "$FAKE_ARGS_FILE"
while [ $# -gt 0 ]; do
  if [ "$1" = "--output" ]; then out="$2"; fi
  shift
done
[ -n "${FAKE_SLEEP:-}" ] && sleep "$FAKE_SLEEP"
if [ -n "${FAKE_BRANCH:-}" ]; then git -C "$FAKE_REPO" branch "$FAKE_BRANCH" >/dev/null 2>&1; fi
if [ "${FAKE_STATUS:-}" != "none" ]; then
  printf '{"status": "%s", "branch": %s}\\n' "${FAKE_STATUS:-passed}" \\
    "$([ -n "${FAKE_BRANCH:-}" ] && echo "\\"$FAKE_BRANCH\\"" || echo null)" > "$out"
fi
echo "FAKE SUMMARY"
exit "${FAKE_EXIT:-0}"
"""


@pytest.fixture
def env(tmp_path, repo):
    fake = tmp_path / "bin" / "fake-cortex"
    fake.parent.mkdir()
    fake.write_text(FAKE_CORTEX)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    task = tmp_path / "task.md"
    task.write_text("do the thing")
    results = tmp_path / "results"
    return {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "CORTEX_BIN": str(fake),
        "CORTEX_REPO": str(repo),
        "CORTEX_TASK_FILE": str(task),
        "CORTEX_VERIFY": "true",
        "CORTEX_RESULTS": str(results),
        "FAKE_ARGS_FILE": str(tmp_path / "args.txt"),
        "FAKE_REPO": str(repo),
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }  # fmt: skip


def run_script(env, *args, timeout=60):
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=timeout
    )


def results_in(env, suffix):
    return sorted(Path(env["CORTEX_RESULTS"]).glob(f"*{suffix}"))


def test_the_script_is_valid_shell_and_executable():
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0
    assert os.access(SCRIPT, os.X_OK)


@pytest.mark.parametrize("name", ["CORTEX_REPO", "CORTEX_TASK_FILE", "CORTEX_VERIFY"])
def test_a_missing_required_setting_is_named(env, name):
    del env[name]

    process = run_script(env)

    assert process.returncode != 0 and name in process.stderr


def test_it_passes_the_settings_and_extra_arguments_to_cortex(env):
    process = run_script(env, "--provider", "openai", "--protect", "tests/*")

    assert process.returncode == 0, process.stderr
    args = Path(env["FAKE_ARGS_FILE"]).read_text()
    assert args.startswith("run ")
    for expected in (
        f"--project-dir {env['CORTEX_REPO']}",
        f"--task-file {env['CORTEX_TASK_FILE']}",
        "--verify true",
        "--provider openai",
        "--protect tests/*",
    ):
        assert expected in args


def test_it_keeps_the_result_the_summary_and_the_log_and_reports_the_status(env):
    process = run_script(env)

    assert process.returncode == 0
    (result,) = results_in(env, ".json")
    assert json.loads(result.read_text())["status"] == "passed"
    assert "FAKE SUMMARY" in results_in(env, ".summary")[0].read_text()
    assert len(results_in(env, ".log")) == 1
    assert "passed (exit 0)" in process.stdout and "FAKE SUMMARY" in process.stdout


@pytest.mark.parametrize("code", [1, 2])
def test_the_exit_code_of_cortex_is_passed_on(env, code):
    env.update(FAKE_EXIT=str(code), FAKE_STATUS="failed")

    process = run_script(env)

    assert process.returncode == code
    assert "failed (exit" in process.stdout


def test_a_run_that_wrote_no_result_is_reported_as_such(env):
    env.update(FAKE_STATUS="none", FAKE_EXIT="1")

    process = run_script(env)

    assert process.returncode == 1 and "no result was written" in process.stdout


def test_the_time_limit_stops_a_run_that_goes_on_too_long(env):
    env.update(FAKE_SLEEP="30", CORTEX_WALL_TIMEOUT="1")
    started = time.monotonic()

    process = run_script(env)

    assert time.monotonic() - started < 20
    assert process.returncode == 124  # `timeout`'s code for "stopped by the limit"
    assert "no result was written" in process.stdout


@pytest.mark.skipif(not shutil.which("flock"), reason="needs flock")
def test_a_second_run_does_not_start_while_the_first_is_still_going(env):
    env.update(FAKE_SLEEP="5")
    first = subprocess.Popen(
        ["bash", str(SCRIPT)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    second_args = Path(env["CORTEX_RESULTS"]).parent / "second-args.txt"
    try:
        time.sleep(1.0)  # let it take the lock
        second = run_script({**env, "FAKE_SLEEP": "", "FAKE_ARGS_FILE": str(second_args)})
    finally:
        first.terminate()
        first.wait(timeout=30)

    assert second.returncode == 0
    assert "still going" in second.stderr
    assert not second_args.exists()  # cortex was never started the second time


# ---- pushing --------------------------------------------------------------------------------


@pytest.fixture
def remote(env, repo, tmp_path):
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(repo, "remote", "add", "origin", str(bare))
    return bare


def pushed(bare):
    out = subprocess.run(
        ["git", "branch", "--format=%(refname:short)"], cwd=bare, capture_output=True, text=True
    ).stdout
    return set(out.split())


def test_a_verified_branch_is_pushed_only_when_asked(env, remote):
    env.update(FAKE_BRANCH="cortex/fix-1", FAKE_STATUS="passed")

    run_script(env)  # CORTEX_PUSH is not set
    assert pushed(remote) == set()

    process = run_script({**env, "CORTEX_PUSH": "1"})
    assert process.returncode == 0, process.stderr
    assert "cortex/fix-1" in pushed(remote)


@pytest.mark.parametrize("status", ["unverified", "failed", "interrupted"])
def test_a_branch_that_did_not_verify_is_never_pushed(env, remote, status):
    env.update(FAKE_BRANCH="cortex/not-verified", FAKE_STATUS=status, CORTEX_PUSH="1")

    run_script(env)

    assert pushed(remote) == set()


def test_a_failed_push_is_reported_with_its_own_exit_code(env, repo):
    git(repo, "remote", "add", "origin", "/no/such/remote")
    env.update(FAKE_BRANCH="cortex/fix-2", FAKE_STATUS="passed", CORTEX_PUSH="1")

    process = run_script(env)

    assert process.returncode == 3 and "pushing cortex/fix-2 failed" in process.stderr


# ---- results over time ----------------------------------------------------------------------


def test_old_results_are_cleared_and_recent_ones_kept(env):
    results = Path(env["CORTEX_RESULTS"])
    results.mkdir()
    old, recent = results / "20200101T000000Z.json", results / "20990101T000000Z.json"
    old.write_text("{}")
    recent.write_text("{}")
    long_ago = time.time() - 90 * 86400
    os.utime(old, (long_ago, long_ago))

    run_script(env)

    assert not old.exists() and recent.exists()


def test_the_retention_period_can_be_changed(env):
    results = Path(env["CORTEX_RESULTS"])
    results.mkdir()
    old = results / "20200101T000000Z.json"
    old.write_text("{}")
    long_ago = time.time() - 5 * 86400
    os.utime(old, (long_ago, long_ago))

    run_script({**env, "CORTEX_KEEP_DAYS": "3"})

    assert not old.exists()


# ---- the other files ------------------------------------------------------------------------


def parse_unit(path):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str  # keep the case of keys
    parser.read(path)
    return parser


def test_the_systemd_units_fit_together():
    service = parse_unit(EXAMPLES / "cortex-nightly.service")
    timer = parse_unit(EXAMPLES / "cortex-nightly.timer")

    assert service["Service"]["Type"] == "oneshot"
    assert "run-task.sh" in service["Service"]["ExecStart"]
    assert "EnvironmentFile" in service["Service"]
    assert timer["Timer"]["OnCalendar"] and timer["Timer"]["Persistent"] == "true"
    assert timer["Install"]["WantedBy"] == "timers.target"


def test_the_example_settings_name_every_setting_the_script_requires():
    text = (EXAMPLES / "nightly.env.example").read_text() + (
        EXAMPLES / "crontab.example"
    ).read_text()

    for name in ("CORTEX_REPO", "CORTEX_TASK_FILE", "CORTEX_VERIFY"):
        assert name in text


def test_the_crontab_example_points_at_the_script_with_a_provider():
    cron = (EXAMPLES / "crontab.example").read_text()

    assert "run-task.sh" in cron and "--provider openai" in cron


def test_the_sample_task_tells_the_agent_not_to_weaken_tests():
    text = (EXAMPLES / "tasks" / "fix-failing-tests.md").read_text().lower()

    assert "do not delete, skip or weaken a test" in text
