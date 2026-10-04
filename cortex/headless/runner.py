"""Run one task unattended and report what really happened.

The shape of a run:

1. Make a new branch in a separate git worktree, from the committed base. Nothing in your own
   checkout is touched.
2. Let the agent work there with every action pre-approved (nobody is there to approve), with its
   questions to the user switched off, and with budgets on steps, tokens and time.
3. Run the verify command. If it fails the agent is shown the failure and tries again, up to
   ``retries`` more times, inside the same budgets.
4. A run that verified keeps its branch, with one commit. Anything else is discarded without a
   trace in your repository (``keep_failed`` keeps it for a look), but is still reported.

The status says what is true: ``passed`` means the verify command passed, ``unverified`` means
there was no verify command, and everything else says what stopped the run. The agent's own
account of its work counts for nothing.
"""

import contextlib
import copy
import fnmatch
import os
import secrets
import signal
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from ..config import AgentConfig
from ..core.command_sandbox import SandboxConfig, SandboxUnavailable, confine
from ..core.turn import STATUS_BLOCKED, STATUS_ERROR, STATUS_INTERRUPTED, STATUS_OK
from .meter import Budget, RunMeter
from .verify import VerifyOutcome, run_verify
from .workspace import Workspace, WorkspaceError

SCHEMA = 1

# How a run can end
PASSED = "passed"  # the verify command passed; the work is on a branch
UNVERIFIED = "unverified"  # no verify command; the work is on a branch, checked by nothing
FAILED = "failed"  # verification kept failing, or protected paths were changed
NO_CHANGES = "no_changes"  # the agent finished but changed no file
AGENT_FAILED = "agent_failed"  # the agent itself stopped with an error
BUDGET_EXCEEDED = "budget_exceeded"  # a step, token or time budget ran out
INTERRUPTED = "interrupted"  # a termination signal arrived
CRASHED = "crashed"  # an unexpected error in the runner
SETUP_ERROR = "setup_error"  # could not start; the agent never ran

_SUCCESS = (PASSED, UNVERIFIED)


@dataclass
class HeadlessConfig:
    """What to run and how far to trust it. Zero budgets mean no limit."""

    task: str
    project_dir: Path
    verify: Optional[str] = None  # shell command that must exit 0; None means no verification
    retries: int = 1  # extra attempts after a failed verification
    max_steps: int = 40  # model calls over the whole run
    max_tokens: int = 1_000_000  # input plus output tokens over the whole run
    timeout_s: float = 3600  # wall-clock seconds over the whole run
    verify_timeout_s: float = 600
    base_ref: str = "HEAD"
    branch: Optional[str] = None  # default: cortex/<task words>-<id>
    keep_failed: bool = False  # keep the branch of a run that did not succeed
    protect: Tuple[str, ...] = ()  # glob patterns of paths the run must not change
    require_sandbox: bool = False  # refuse to run unless commands are confined
    price_in: Optional[float] = None  # USD per million input tokens
    price_out: Optional[float] = None  # USD per million output tokens


@dataclass
class RunResult:
    """Everything worth knowing about a run, in a form that serialises to JSON."""

    run_id: str
    task: str
    repo: Optional[str] = None
    status: str = CRASHED
    reason: str = ""
    base: Optional[str] = None
    branch: Optional[str] = None  # set only when the branch was kept
    head: Optional[str] = None
    files_changed: List[str] = field(default_factory=list)
    diff_stat: str = ""
    verify_command: Optional[str] = None
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    budget: Dict[str, Any] = field(default_factory=dict)
    model: Optional[str] = None
    provider: Optional[str] = None
    sandbox: str = "none"
    seconds: float = 0.0

    @property
    def exit_code(self) -> int:
        """0 when the run completed as asked, 2 when it could not start, 1 otherwise."""
        if self.status in _SUCCESS:
            return 0
        return 2 if self.status == SETUP_ERROR else 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA,
            "run_id": self.run_id,
            "status": self.status,
            "reason": self.reason,
            "task": self.task,
            "repo": self.repo,
            "base": self.base,
            "branch": self.branch,
            "head": self.head,
            "files_changed": self.files_changed,
            "diff_stat": self.diff_stat,
            "verify_command": self.verify_command,
            "attempts": self.attempts,
            "usage": self.usage,
            "budget": self.budget,
            "model": self.model,
            "provider": self.provider,
            "sandbox": self.sandbox,
            "seconds": self.seconds,
        }


# ---- what the agent is told ---------------------------------------------------------------


def initial_prompt(task: str, verify: Optional[str]) -> str:
    lines = [
        task.strip(),
        "",
        "You are running unattended: nobody can answer questions or approve anything, so make "
        "reasonable assumptions and state them in your final message.",
    ]
    if verify:
        lines.append(
            f"When you finish, this command will be run to check your work, and it must exit 0: "
            f"{verify}"
        )
    return "\n".join(lines)


def feedback_prompt(verify: str, outcome: VerifyOutcome) -> str:
    how = "timed out" if outcome.timed_out else f"exited with code {outcome.exit_code}"
    return (
        f"The verification command failed ({how}).\n\n"
        f"Command: {verify}\n\n"
        f"Output (the end of it):\n{outcome.output}\n\n"
        "Fix the cause in the code so the command passes. Do not weaken or delete tests, or "
        "change the command, just to make it pass."
    )


def commit_message(
    config: HeadlessConfig, run_id: str, status: str, reason: str, success: bool
) -> str:
    first_line = next((line.strip() for line in config.task.splitlines() if line.strip()), "task")
    if len(first_line) > 60:
        first_line = first_line[:57].rstrip() + "..."
    subject = f"cortex: {first_line}" if success else f"cortex [{status}]: {first_line}"
    checked = (
        f"Verified by: {config.verify}"
        if config.verify and status == PASSED
        else "Not verified." if not config.verify else f"Not verified: {reason}"
    )
    return f"{subject}\n\nTask:\n{config.task.strip()[:2000]}\n\n{checked}\nRun: {run_id}\n"


# ---- the run ------------------------------------------------------------------------------


@contextlib.contextmanager
def _prefer_worktree_imports(path: Path) -> Iterator[None]:
    """Make Python code run during the task import the worktree's code.

    A project installed in editable mode points at your own checkout, so tests run in the worktree
    would import the code that was there before the task: a correct fix would fail, and worse, a
    regression the agent introduced would pass. Putting the worktree (and its ``src`` directory,
    for that layout) first on ``PYTHONPATH`` makes it win. It applies to the agent's own commands
    and to the verify command alike, and is undone afterwards.
    """
    entries = [str(path)] + ([str(path / "src")] if (path / "src").is_dir() else [])
    previous = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = os.pathsep.join(entries + ([previous] if previous else []))
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = previous


def _new_run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + secrets.token_hex(3)


class _Run:
    def __init__(
        self,
        config: HeadlessConfig,
        agent_config: Optional[AgentConfig],
        provider_factory: Optional[Callable[[], Any]],
        clock: Callable[[], float],
    ):
        self.config = config
        self.provider_factory = provider_factory
        self.clock = clock
        self.started = clock()

        # Never modify the caller's configuration
        self.agent_config = copy.deepcopy(agent_config) if agent_config else AgentConfig()
        self.result = RunResult(
            run_id=_new_run_id(),
            task=config.task.strip()[:200],
            verify_command=config.verify,
            budget={
                "max_steps": config.max_steps,
                "max_tokens": config.max_tokens,
                "timeout_s": config.timeout_s,
                "exceeded": None,
            },
        )
        self.workspace: Optional[Workspace] = None
        self.agent: Any = None
        self.meter: Optional[RunMeter] = None
        self.sandbox: Optional[SandboxConfig] = None
        self.signalled = False
        self.tool_calls = 0

    # -- setup ---------------------------------------------------------------------------

    def _setup_error(self, reason: str) -> RunResult:
        self.result.status, self.result.reason = SETUP_ERROR, reason
        return self._finish()

    def _prepare_configuration(self) -> Optional[str]:
        """Apply what an unattended run needs. Returns a reason if it cannot run."""
        from ..models import PermissionMode

        cfg = self.agent_config
        try:
            self.sandbox = SandboxConfig.from_dict(cfg.get_command_sandbox_config())
        except ValueError as e:
            return str(e)
        self.result.sandbox = self.sandbox.mode

        if self.sandbox.mode != "none":
            try:  # fail now rather than on the first command
                confine(["true"], self.config.project_dir, self.sandbox)
            except SandboxUnavailable as e:
                return str(e)
        elif self.config.require_sandbox:
            return (
                "A sandbox was required but command_sandbox.mode is 'none', so commands would "
                "run with your own permissions. Set command_sandbox.mode to 'bubblewrap' in the "
                "config (Linux), or run Cortex in a container or VM and drop --require-sandbox."
            )

        cfg.permission_mode = PermissionMode.AUTO_APPROVE  # nobody is there to approve
        cfg.max_iterations_continue_default = False  # nobody is there to ask either
        if self.config.max_steps:
            cfg.max_iterations = self.config.max_steps  # per turn; the meter limits the total
        # The worktree is thrown away on failure, which is the undo; no refs in your repository
        cfg.checkpoints = {**cfg.checkpoints, "enabled": False}
        cfg.transactions = {**cfg.transactions, "enabled": False}
        cfg.tools_disabled = sorted(set(cfg.tools_disabled) | {"ask_user_question"})
        return None

    def _build_agent(self) -> Any:
        from ..agent import Cortex
        from ..models import PermissionMode

        cfg = self.agent_config
        agent = Cortex(
            model=cfg.model,
            project_dir=str(self.workspace.path),  # type: ignore[union-attr]
            permission_mode=PermissionMode.AUTO_APPROVE,
            config=cfg,
            enable_planning=cfg.enable_planning,
            enable_layered_memory=cfg.enable_layered_memory,
        )
        if self.provider_factory is not None:
            agent.provider = self.provider_factory()
        return agent

    # -- driving the agent ---------------------------------------------------------------

    def _request_stop(self) -> None:
        self.signalled = True
        if self.agent is not None:
            self.agent.request_shutdown()

    @contextlib.contextmanager
    def _stop_on_signal(self) -> Iterator[None]:
        """A termination signal (a scheduler's time-out) or Ctrl-C stops the run at the next step,
        so the worktree is still cleaned up and a result is still written. A second signal does
        what it normally would, in case the run is stuck. Only possible from the main thread."""
        names = [n for n in ("SIGTERM", "SIGINT") if hasattr(signal, n)]
        if threading.current_thread() is not threading.main_thread() or not names:
            yield
            return
        previous = {n: signal.getsignal(getattr(signal, n)) for n in names}

        def restore() -> None:
            for name, handler in previous.items():
                signal.signal(getattr(signal, name), handler)

        def on_signal(signum: int, frame: Any) -> None:
            self._request_stop()
            restore()

        for name in names:
            signal.signal(getattr(signal, name), on_signal)
        try:
            yield
        finally:
            restore()

    def _budget_reason(self, which: str) -> str:
        meter, config = self.meter, self.config
        assert meter is not None
        if which == "steps":
            return f"budget exceeded: {meter.calls} steps (limit {config.max_steps})"
        if which == "tokens":
            used = meter.input_tokens + meter.output_tokens
            return f"budget exceeded: {used} tokens (limit {config.max_tokens})"
        return f"budget exceeded: time limit of {config.timeout_s:g}s"

    def _stop_reason(self, turn: Any) -> Optional[Tuple[str, str]]:
        """Why a finished turn means the run cannot go on, or None to carry on to verification."""
        assert self.meter is not None
        if self.signalled:
            return INTERRUPTED, "stopped by a termination signal"
        if self.meter.exceeded:
            self.result.budget["exceeded"] = self.meter.exceeded
            return BUDGET_EXCEEDED, self._budget_reason(self.meter.exceeded)
        if turn.status == STATUS_INTERRUPTED:
            return INTERRUPTED, "the agent was asked to shut down"
        if turn.status in (STATUS_ERROR, STATUS_BLOCKED):
            return (
                AGENT_FAILED,
                f"the agent stopped with '{turn.status}': {turn.error or 'no detail'}",
            )
        return None

    def _route_model_calls(self) -> None:
        """Make every model call the agent can make go through the meter, or it would escape the
        budgets. Besides the agent loop, the only caller is LLM-based summarization, which was
        built holding the provider the agent started with."""
        summarizer = getattr(self.agent.conversation, "summarizer", None)
        for holder in (summarizer, getattr(summarizer, "llm", None)):
            if holder is not None and hasattr(holder, "provider"):
                holder.provider = self.meter

    def _drive(self) -> Tuple[str, str]:
        config = self.config
        self.agent = self._build_agent()
        self.result.model = self.agent.model
        self.meter = RunMeter(
            self.agent.provider,
            Budget(config.max_steps, config.max_tokens, config.timeout_s),
            started=self.started,
            clock=self.clock,
            on_exceeded=lambda reason: self.agent.request_shutdown(),
        )
        self.agent.provider = self.meter
        self._route_model_calls()
        if self.signalled:
            return INTERRUPTED, "stopped by a termination signal before the agent started"

        sandbox = self.sandbox if self.sandbox and self.sandbox.mode != "none" else None
        allowed = max(0, config.retries) + 1
        prompt = initial_prompt(config.task, config.verify)

        for number in range(1, allowed + 1):
            turn = self.agent._process_message(prompt)
            attempt: Dict[str, Any] = {
                "turn": turn.status,
                "turn_error": turn.error,
                "verification": None,
            }
            self.result.attempts.append(attempt)
            self.tool_calls += turn.tool_calls

            stop = self._stop_reason(turn)
            if stop:
                return stop

            if not config.verify:
                if turn.status != STATUS_OK:
                    return AGENT_FAILED, (
                        f"the agent's turn ended with '{turn.status}' and there is no verify "
                        "command to say whether what it did is usable"
                    )
                return (
                    UNVERIFIED,
                    "the agent finished; no verify command was given, so nothing checked the work",
                )

            outcome = run_verify(
                config.verify, self.workspace.path, config.verify_timeout_s, sandbox  # type: ignore[union-attr]
            )
            attempt["verification"] = {
                "passed": outcome.passed,
                "exit_code": outcome.exit_code,
                "timed_out": outcome.timed_out,
                "seconds": outcome.seconds,
                "output_tail": outcome.output,
            }
            if self.signalled:  # the signal arrived while the command was running
                return INTERRUPTED, "stopped by a termination signal while verifying"
            if outcome.passed:
                return PASSED, f"verification passed (attempt {number} of {allowed})"
            how = "timed out" if outcome.timed_out else f"exit code {outcome.exit_code}"
            if number == allowed:
                return FAILED, f"verification still failing after {number} attempt(s): {how}"
            limit = self.meter.reached()
            if limit:
                self.result.budget["exceeded"] = limit
                return BUDGET_EXCEEDED, (
                    f"verification failed ({how}) and the {limit} budget is used up, so there is "
                    "nothing left to retry with"
                )
            prompt = feedback_prompt(config.verify, outcome)

        raise AssertionError("unreachable: the last attempt always returns")

    # -- concluding ----------------------------------------------------------------------

    def _conclude(self, status: str, reason: str) -> Tuple[str, str, bool]:
        """Look at what the agent left, settle the final status, and commit it if it is kept.

        Returns (status, reason, keep_branch).
        """
        workspace = self.workspace
        assert workspace is not None
        config = self.config
        success = status in _SUCCESS

        workspace.stage()
        changed = workspace.files_changed()
        self.result.files_changed = changed
        self.result.diff_stat = workspace.diff_stat()

        if success:
            if not changed:
                return NO_CHANGES, "the agent finished without changing any file", False
            protected = sorted(
                {
                    p
                    for p in changed
                    for pattern in config.protect
                    if fnmatch.fnmatchcase(p, pattern)
                }
            )
            if protected:
                return (
                    FAILED,
                    "changed protected path(s): " + ", ".join(protected),
                    config.keep_failed,
                )
        keep = success or (config.keep_failed and bool(changed))
        if keep:
            workspace.commit(commit_message(config, self.result.run_id, status, reason, success))
        return status, reason, keep

    def _finish(self) -> RunResult:
        result = self.result
        meter = self.meter
        result.seconds = round(self.clock() - self.started, 2)
        result.usage = {
            "steps": meter.calls if meter else 0,
            "tool_calls": self.tool_calls,
            "input_tokens": meter.input_tokens if meter else 0,
            "output_tokens": meter.output_tokens if meter else 0,
            "estimated": meter.estimated if meter else False,
            "cost_usd": self._cost(),
        }
        return result

    def _cost(self) -> Optional[float]:
        meter, config = self.meter, self.config
        if meter is None or config.price_in is None or config.price_out is None:
            return None
        return round(
            (meter.input_tokens * config.price_in + meter.output_tokens * config.price_out) / 1e6, 6
        )

    # -- the whole run -------------------------------------------------------------------

    def execute(self) -> RunResult:
        config, result = self.config, self.result
        result.repo = str(config.project_dir)

        problem = self._prepare_configuration()
        if problem:
            return self._setup_error(problem)
        from ..core.providers import ProviderFactory

        result.provider = ProviderFactory.get_provider_name(
            self.agent_config.model, getattr(self.agent_config, "provider", None)
        )
        result.model = self.agent_config.model

        try:
            self.workspace = Workspace.create(
                config.project_dir, config.task, config.base_ref, config.branch
            )
        except WorkspaceError as e:
            return self._setup_error(str(e))
        workspace = self.workspace
        result.repo, result.base = str(workspace.repo), workspace.base

        keep = False
        try:
            with self._stop_on_signal(), _prefer_worktree_imports(workspace.path):
                try:
                    status, reason = self._drive()
                except Exception as e:  # one broken run must not take the scheduler down
                    status, reason = CRASHED, f"{type(e).__name__}: {e}"
                try:
                    status, reason, keep = self._conclude(status, reason)
                except Exception as e:
                    note = f"could not collect the result: {e}"
                    if status in _SUCCESS:
                        status, reason = CRASHED, note
                    else:  # keep the real reason the run failed
                        reason = f"{reason}; {note}"
                    keep = False
            result.status, result.reason = status, reason
            if keep:
                result.branch, result.head = workspace.branch, workspace.head()
        finally:
            workspace.remove(keep_branch=keep)
        return self._finish()


def setup_error(task: str, project_dir: Path, reason: str) -> RunResult:
    """The result for a run that could not start before the runner was reached (an unreadable task
    file or configuration, a provider that is not set up). It has the same shape as any other."""
    return RunResult(
        run_id=_new_run_id(),
        task=task.strip()[:200],
        repo=str(project_dir),
        status=SETUP_ERROR,
        reason=reason,
        usage={
            "steps": 0,
            "tool_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated": False,
            "cost_usd": None,
        },
        budget={"max_steps": None, "max_tokens": None, "timeout_s": None, "exceeded": None},
    )


def run(
    config: HeadlessConfig,
    agent_config: Optional[AgentConfig] = None,
    provider_factory: Optional[Callable[[], Any]] = None,
    clock: Callable[[], float] = time.monotonic,
) -> RunResult:
    """Run ``config.task`` unattended and return what happened.

    ``agent_config`` is the Cortex configuration to use (it is copied, not modified).
    ``provider_factory`` replaces the model provider, which is how the tests use a scripted one.
    """
    return _Run(config, agent_config, provider_factory, clock).execute()
