"""An unattended run, end to end, with a scripted model and a real git repository.

What matters: the result says what really happened (a run is "passed" only when the verify command
passed), your checkout is never touched, a failed run leaves nothing behind, and every budget
stops a runaway run.
"""

import json
import os
import shlex
import signal
import sys
import time

import pytest

from cortex.config import AgentConfig
from cortex.core.providers.base import ProviderError
from cortex.headless import runner
from cortex.headless.runner import HeadlessConfig, run
from tests.e2e.scripted import ScriptedProvider, final, tool_call
from tests.unit.headless.gitutil import git

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX shell and signals")

CHECK = """\
import pathlib, sys
path = pathlib.Path("out.txt")
text = path.read_text() if path.exists() else "<missing>"
print("out.txt contains:", repr(text))
sys.exit(0 if text == "good\\n" else 1)
"""
VERIFY = f"{shlex.quote(sys.executable)} check.py"


def write(path, content, call_id="w1"):
    return tool_call("write_file", {"path": path, "content": content}, call_id)


GOOD = [write("out.txt", "good\n"), final("wrote out.txt")]
BAD = [write("out.txt", "bad\n"), final("wrote out.txt")]


@pytest.fixture
def task_repo(repo):
    """The repository, with the check script committed."""
    (repo / "check.py").write_text(CHECK)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "add check")
    return repo


def branches(repo):
    return set(git(repo, "branch", "--format=%(refname:short)").split())


def execute(repo, script=(), provider=None, clock=None, agent_config=None, **overrides):
    """Run a task with a scripted model; returns (result, provider)."""
    provider = provider or ScriptedProvider(list(script))
    options = dict(task="write good output to out.txt", project_dir=repo, verify=VERIFY, retries=0)
    config = HeadlessConfig(**{**options, **overrides})
    result = run(
        config,
        agent_config or AgentConfig(model="llama3.2", provider="ollama"),
        provider_factory=lambda: provider,
        clock=clock or time.monotonic,
    )
    return result, provider


def assert_left_nothing(repo, branches_before):
    assert branches(repo) == branches_before
    assert len(git(repo, "worktree", "list").splitlines()) == 1


# ---- the outcomes -------------------------------------------------------------------------


def test_a_task_that_passes_verification_leaves_a_branch_with_the_work(task_repo):
    before = branches(task_repo)

    result, _ = execute(task_repo, GOOD)

    assert result.status == "passed" and result.exit_code == 0
    assert result.branch in branches(task_repo) - before
    assert git(task_repo, "show", f"{result.branch}:out.txt") == "good"
    assert result.files_changed == ["out.txt"]
    assert result.head == git(task_repo, "rev-parse", result.branch)
    assert result.base == git(task_repo, "rev-parse", "main")
    assert result.attempts[0]["verification"]["passed"] is True
    assert len(git(task_repo, "worktree", "list").splitlines()) == 1  # its directory is gone


def test_your_checkout_is_untouched_by_a_run(task_repo):
    head = git(task_repo, "rev-parse", "HEAD")

    execute(task_repo, GOOD)

    assert git(task_repo, "branch", "--show-current") == "main"
    assert git(task_repo, "rev-parse", "HEAD") == head
    assert not (task_repo / "out.txt").exists()
    assert git(task_repo, "status", "--porcelain") == ""


def test_failed_verification_is_fed_back_and_the_agent_gets_another_go(task_repo):
    script = BAD + [write("out.txt", "good\n", "w2"), final("fixed it")]

    result, provider = execute(task_repo, script, retries=1)

    assert result.status == "passed"
    assert [a["verification"]["passed"] for a in result.attempts] == [False, True]
    follow_up = [m for m in provider.seen[-1] if m["role"] == "user"][-1]["content"]
    assert VERIFY in follow_up
    assert "out.txt contains: 'bad\\n'" in follow_up  # what the model needs to fix it
    assert git(task_repo, "show", f"{result.branch}:out.txt") == "good"


def test_a_task_that_never_passes_is_a_failure_and_leaves_nothing(task_repo):
    before = branches(task_repo)

    result, _ = execute(task_repo, BAD + BAD, retries=1)

    assert result.status == "failed" and result.exit_code == 1
    assert len(result.attempts) == 2
    assert "verification" in result.reason and "2 attempt" in result.reason
    assert "out.txt contains: 'bad\\n'" in result.attempts[-1]["verification"]["output_tail"]
    assert result.branch is None and result.head is None
    assert result.files_changed == ["out.txt"]  # what it tried, for the report
    assert_left_nothing(task_repo, before)


def test_a_failed_branch_can_be_kept_for_a_look(task_repo):
    result, _ = execute(task_repo, BAD, keep_failed=True)

    assert result.status == "failed"
    assert result.branch in branches(task_repo)
    assert git(task_repo, "show", f"{result.branch}:out.txt") == "bad"


def test_an_agent_that_changes_nothing_has_not_done_the_task(task_repo):
    before = branches(task_repo)
    (task_repo / "out.txt").write_text("good\n")
    git(task_repo, "add", ".")
    git(task_repo, "commit", "-qm", "already good")  # verification would pass without any work
    before = branches(task_repo)

    result, _ = execute(task_repo, [final("nothing to do")])

    assert result.status == "no_changes" and result.exit_code == 1
    assert result.branch is None
    assert_left_nothing(task_repo, before)


def test_without_a_verify_command_the_result_says_unverified(task_repo):
    result, _ = execute(task_repo, GOOD, verify=None)

    assert result.status == "unverified" and result.exit_code == 0
    assert result.verify_command is None
    assert all(a["verification"] is None for a in result.attempts)
    assert git(task_repo, "show", f"{result.branch}:out.txt") == "good"


def test_a_model_that_cannot_be_reached_is_an_agent_failure(task_repo):
    class Unreachable(ScriptedProvider):
        def chat(self, model, messages, tools=None):
            raise ProviderError("connection refused")

    before = branches(task_repo)

    result, _ = execute(task_repo, provider=Unreachable([]))

    assert result.status == "agent_failed" and result.exit_code == 1
    assert "connection refused" in result.reason or "error" in result.reason
    assert_left_nothing(task_repo, before)


def test_edits_to_protected_paths_fail_the_run_even_if_verification_passes(task_repo):
    script = [
        write("out.txt", "good\n", "w1"),
        tool_call(
            "write_file", {"path": "tests/test_a.py", "content": "def test_a(): pass\n"}, "w2"
        ),
        final("done"),
    ]
    before = branches(task_repo)

    result, _ = execute(task_repo, script, protect=("tests/*",))

    assert result.status == "failed"
    assert "tests/test_a.py" in result.reason and "protected" in result.reason
    assert result.attempts[0]["verification"]["passed"] is True  # it did pass; that is not enough
    assert_left_nothing(task_repo, before)


def test_unprotected_paths_may_change(task_repo):
    result, _ = execute(task_repo, GOOD, protect=("tests/*",))

    assert result.status == "passed"


@posix_only
def test_a_verify_command_that_hangs_counts_as_failing(task_repo):
    result, _ = execute(task_repo, GOOD, verify="sleep 30", verify_timeout_s=0.5)

    assert result.status == "failed"
    assert result.attempts[0]["verification"]["timed_out"] is True


# ---- budgets ------------------------------------------------------------------------------


def endless_reads(n=20):
    return [tool_call("read_file", {"path": "a.py"}, f"r{i}") for i in range(n)]


def test_a_run_that_uses_up_its_steps_is_stopped_and_discarded(task_repo):
    before = branches(task_repo)

    result, provider = execute(task_repo, endless_reads(), max_steps=3)

    assert result.status == "budget_exceeded" and result.exit_code == 1
    assert result.budget["exceeded"] == "steps"
    assert result.usage["steps"] == len(provider.seen) == 3
    assert "steps" in result.reason
    assert_left_nothing(task_repo, before)


class Counting(ScriptedProvider):
    """Reports usage with every reply."""

    def chat(self, model, messages, tools=None):
        response = super().chat(model, messages, tools)
        response["usage"] = {"input_tokens": 60, "output_tokens": 40}
        return response


def test_a_run_that_uses_up_its_tokens_is_stopped(task_repo):
    result, _ = execute(task_repo, provider=Counting(endless_reads()), max_tokens=150, max_steps=0)

    assert result.status == "budget_exceeded"
    assert result.budget["exceeded"] == "tokens"
    assert result.usage["input_tokens"] == 120 and result.usage["output_tokens"] == 80
    assert result.usage["estimated"] is False


def test_a_run_that_uses_up_its_time_is_stopped(task_repo):
    class Clock:
        now = 0.0

        def __call__(self):
            return self.now

    clock = Clock()

    class Slow(ScriptedProvider):
        def chat(self, model, messages, tools=None):
            clock.now += 10  # every model call takes ten "seconds"
            return super().chat(model, messages, tools)

    result, provider = execute(
        task_repo, provider=Slow(endless_reads()), clock=clock, timeout_s=25, max_steps=0
    )

    assert result.status == "budget_exceeded" and result.budget["exceeded"] == "time"
    assert len(provider.seen) == 3  # stopped after the call that crossed 25s
    assert result.seconds >= 25


def test_the_budget_covers_retries_too(task_repo):
    # two calls for the first attempt use the whole budget, so there is nothing left for a retry
    result, provider = execute(task_repo, BAD + GOOD, max_steps=2, retries=3)

    assert result.status == "budget_exceeded"
    assert "verification" in result.reason and "steps" in result.reason
    assert len(provider.seen) == 2


def test_cost_is_reported_only_when_prices_are_given(task_repo):
    priced, _ = execute(task_repo, provider=Counting(list(GOOD)), price_in=3.0, price_out=15.0)
    unpriced, _ = execute(task_repo, provider=Counting(list(GOOD)))

    assert priced.usage["cost_usd"] == pytest.approx((120 * 3.0 + 80 * 15.0) / 1e6)
    assert unpriced.usage["cost_usd"] is None


def test_tokens_are_flagged_as_estimates_when_the_provider_reports_none(task_repo):
    result, _ = execute(task_repo, GOOD)

    assert result.usage["estimated"] is True
    assert result.usage["input_tokens"] > 0


# ---- what the agent is told and given -----------------------------------------------------


class Recording(ScriptedProvider):
    def __init__(self, script):
        super().__init__(script)
        self.tool_names = []

    def chat(self, model, messages, tools=None):
        self.tool_names.append([t["function"]["name"] for t in (tools or [])])
        return super().chat(model, messages, tools)


def test_the_agent_cannot_ask_questions_nobody_will_answer(task_repo):
    provider = Recording(list(GOOD))

    execute(task_repo, provider=provider)

    assert provider.tool_names[0], "the agent was given tools"
    assert "ask_user_question" not in provider.tool_names[0]


def test_the_agent_is_told_it_is_unattended_and_how_it_will_be_checked(task_repo):
    result, provider = execute(task_repo, GOOD, task="Make out.txt say good")

    first = [m for m in provider.seen[0] if m["role"] == "user"][0]["content"]
    assert "Make out.txt say good" in first
    assert "unattended" in first
    assert VERIFY in first


def test_no_undo_information_is_written_into_your_repository(task_repo):
    execute(task_repo, GOOD)

    assert git(task_repo, "for-each-ref", "refs/cortex") == ""


def test_the_configuration_you_gave_is_not_modified(task_repo):
    config = AgentConfig(model="llama3.2", provider="ollama", max_iterations=7)

    execute(task_repo, GOOD, agent_config=config)

    assert config.max_iterations == 7
    assert "ask_user_question" not in config.tools_disabled
    assert config.checkpoints.get("enabled") is not False


# ---- interruption and failure -------------------------------------------------------------


@posix_only
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_a_termination_signal_or_ctrl_c_stops_the_run_cleanly(task_repo, sig):
    class Terminated(ScriptedProvider):
        def chat(self, model, messages, tools=None):
            os.kill(os.getpid(), sig)  # e.g. the scheduler's time-out fires, or Ctrl-C
            return super().chat(model, messages, tools)

    before_handlers = (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT))
    before = branches(task_repo)

    result, _ = execute(task_repo, provider=Terminated(endless_reads()))

    assert result.status == "interrupted" and result.exit_code == 1
    assert (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)) == before_handlers
    assert_left_nothing(task_repo, before)


def test_an_unexpected_error_is_reported_and_cleaned_up(task_repo):
    def boom():
        raise RuntimeError("provider exploded")

    before = branches(task_repo)
    config = HeadlessConfig(task="t", project_dir=task_repo, verify=VERIFY)

    result = run(config, AgentConfig(model="llama3.2", provider="ollama"), provider_factory=boom)

    assert result.status == "crashed" and result.exit_code == 1
    assert "provider exploded" in result.reason
    assert_left_nothing(task_repo, before)


# ---- could not start ----------------------------------------------------------------------


def test_a_directory_that_is_not_a_repository_is_a_setup_error(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()

    result, _ = execute(plain, GOOD)

    assert result.status == "setup_error" and result.exit_code == 2
    assert "git repository" in result.reason


def test_requiring_a_sandbox_when_none_is_configured_is_a_setup_error(task_repo):
    before = branches(task_repo)

    result, provider = execute(task_repo, GOOD, require_sandbox=True)

    assert result.status == "setup_error" and result.exit_code == 2
    assert "command_sandbox" in result.reason
    assert provider.seen == []  # the model was never called
    assert_left_nothing(task_repo, before)


def test_a_sandbox_that_cannot_be_provided_is_a_setup_error(task_repo, monkeypatch):
    from cortex.core import command_sandbox

    def missing():
        raise command_sandbox.SandboxUnavailable("bwrap is not installed")

    monkeypatch.setattr(command_sandbox, "_find_bwrap", missing)
    config = AgentConfig(
        model="llama3.2", provider="ollama", command_sandbox={"mode": "bubblewrap"}
    )
    before = branches(task_repo)

    result, provider = execute(task_repo, GOOD, agent_config=config)

    assert result.status == "setup_error"
    assert "bwrap is not installed" in result.reason
    assert provider.seen == []
    assert_left_nothing(task_repo, before)


def test_an_unknown_sandbox_mode_is_a_setup_error(task_repo):
    config = AgentConfig(model="llama3.2", provider="ollama", command_sandbox={"mode": "magic"})

    result, _ = execute(task_repo, GOOD, agent_config=config)

    assert result.status == "setup_error" and "magic" in result.reason


def test_the_sandbox_in_use_is_reported(task_repo):
    result, _ = execute(task_repo, GOOD)

    assert result.sandbox == "none"


# ---- the result ---------------------------------------------------------------------------


def test_the_result_is_json_with_a_stable_set_of_fields(task_repo):
    result, _ = execute(task_repo, GOOD, branch="cortex/nightly")

    data = json.loads(json.dumps(result.to_dict()))

    assert set(data) == {
        "schema", "run_id", "status", "reason", "task", "repo", "base", "branch", "head",
        "files_changed", "diff_stat", "verify_command", "attempts", "usage", "budget", "model",
        "provider", "sandbox", "seconds",
    }  # fmt: skip
    assert data["schema"] == 1
    assert data["branch"] == "cortex/nightly"
    assert data["verify_command"] == VERIFY
    assert data["model"] == "llama3.2" and data["provider"] == "ollama"
    assert set(data["usage"]) == {
        "steps", "tool_calls", "input_tokens", "output_tokens", "estimated", "cost_usd"
    }  # fmt: skip
    assert set(data["budget"]) == {"max_steps", "max_tokens", "timeout_s", "exceeded"}
    assert data["usage"]["tool_calls"] == 1
    assert "out.txt" in data["diff_stat"]


def test_every_run_has_its_own_id(task_repo):
    first, _ = execute(task_repo, GOOD)
    second, _ = execute(task_repo, GOOD)

    assert first.run_id != second.run_id and first.branch != second.branch


def test_the_commit_says_what_was_asked_and_how_it_was_checked(task_repo):
    result, _ = execute(task_repo, GOOD, task="Make out.txt say good\n\nMore detail here.")

    message = git(task_repo, "log", "-1", "--format=%B", result.branch)
    assert message.splitlines()[0] == "cortex: Make out.txt say good"
    assert "More detail here." in message and VERIFY in message and result.run_id in message


def test_a_run_can_start_from_another_base(task_repo):
    git(task_repo, "branch", "release")
    (task_repo / "later.txt").write_text("x")
    git(task_repo, "add", ".")
    git(task_repo, "commit", "-qm", "later")

    result, _ = execute(task_repo, GOOD, base_ref="release")

    assert result.base == git(task_repo, "rev-parse", "release")
    assert git(task_repo, "merge-base", "--is-ancestor", "release", result.branch) == ""
    assert "later.txt" not in git(task_repo, "ls-tree", "--name-only", result.branch)


# ---- details that are easy to get wrong ---------------------------------------------------


@pytest.mark.parametrize("strategy", ["llm", "hybrid"])
def test_model_calls_made_by_summarization_go_through_the_meter(task_repo, monkeypatch, strategy):
    """Otherwise they would escape the step and token budgets."""
    captured = {}
    build = runner._Run._build_agent

    def spy(self):
        captured["agent"] = build(self)
        return captured["agent"]

    monkeypatch.setattr(runner._Run, "_build_agent", spy)
    config = AgentConfig(
        model="llama3.2", provider="ollama", summarization={"enabled": True, "strategy": strategy}
    )

    execute(task_repo, GOOD, agent_config=config)

    agent = captured["agent"]
    summarizer = agent.conversation.summarizer
    llm = summarizer if strategy == "llm" else summarizer.llm
    assert llm.provider is agent.provider  # the meter the run installed, not the original
    assert type(agent.provider).__name__ == "RunMeter"


@posix_only
def test_a_termination_signal_during_verification_is_not_a_pass(task_repo):
    before = branches(task_repo)
    verify = f"kill -TERM {os.getpid()}; exit 0"  # the scheduler's timeout fires mid-verification

    result, _ = execute(task_repo, GOOD, verify=verify)

    assert result.status == "interrupted" and result.exit_code == 1
    assert "verifying" in result.reason
    assert_left_nothing(task_repo, before)


def test_a_failure_while_collecting_the_result_does_not_hide_why_the_run_failed(
    task_repo, monkeypatch
):
    from cortex.headless.workspace import Workspace

    def broken(self):
        raise RuntimeError("index is locked")

    monkeypatch.setattr(Workspace, "stage", broken)
    before = branches(task_repo)

    result, _ = execute(task_repo, BAD)

    assert result.status == "failed"
    assert "verification still failing" in result.reason  # the real reason is kept
    assert "index is locked" in result.reason
    assert_left_nothing(task_repo, before)


def test_a_failure_while_collecting_a_good_result_is_a_crash_not_a_pass(task_repo, monkeypatch):
    from cortex.headless.workspace import Workspace

    def broken(self):
        raise RuntimeError("index is locked")

    monkeypatch.setattr(Workspace, "stage", broken)
    before = branches(task_repo)

    result, _ = execute(task_repo, GOOD)

    assert result.status == "crashed" and result.exit_code == 1
    assert "index is locked" in result.reason
    assert_left_nothing(task_repo, before)


# ---- tests must see the task's code, not the checkout the project was installed from -------


@pytest.fixture
def installed_package(task_repo, tmp_path):
    """A src-layout package that is "installed" the way an editable install is: a .pth file in
    site-packages points at the ORIGINAL checkout, not at the task's worktree."""
    package = task_repo / "src" / "mypkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 1\n")
    git(task_repo, "add", ".")
    git(task_repo, "commit", "-qm", "add package")

    site = tmp_path / "site"
    site.mkdir()
    (site / "mypkg-editable.pth").write_text(str(task_repo / "src"))
    code = (
        f"import site, sys; site.addsitedir({str(site)!r}); import mypkg; "
        "sys.exit(0 if mypkg.VALUE == {expected} else 1)"
    )
    return (
        lambda expected: f"{shlex.quote(sys.executable)} -c {shlex.quote(code.format(expected=expected))}"
    )


def test_a_correct_fix_is_seen_by_tests_despite_an_editable_install(task_repo, installed_package):
    script = [write("src/mypkg/__init__.py", "VALUE = 2\n"), final("fixed")]

    result, _ = execute(task_repo, script, verify=installed_package(expected=2))

    assert result.status == "passed", result.reason  # it used to fail: the tests saw VALUE = 1


def test_a_regression_is_not_hidden_by_an_editable_install(task_repo, installed_package):
    # The agent breaks the package. Tests that still imported the original checkout would pass.
    script = [write("src/mypkg/__init__.py", "VALUE = 99\n"), final("changed")]

    result, _ = execute(task_repo, script, verify=installed_package(expected=1))

    assert result.status == "failed", "the regression must not pass"


def test_the_import_path_is_put_back_after_the_run(task_repo, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/some/where")
    execute(task_repo, GOOD)
    assert os.environ["PYTHONPATH"] == "/some/where"

    monkeypatch.delenv("PYTHONPATH")
    execute(task_repo, GOOD)
    assert "PYTHONPATH" not in os.environ
