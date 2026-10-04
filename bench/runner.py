"""Run an agent (or a stand-in) against the tasks and record what happened.

For every task the runner builds the starting project in a fresh temporary directory, lets the
solver work on it, then runs the verifier. The verdict is the verifier's. Alongside it the runner
records the steps the agent took, the tokens it used, what that cost (only when prices are given)
and how long it took.
"""

import contextlib
import io
import itertools
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from cortex.headless.meter import UsageMeter

from .suite import select
from .task import Task, apply_solution, materialize, verify

FACTORS = ("planning", "memory", "metacognition")
SOLVERS = ("agent", "oracle", "noop")


@dataclass(frozen=True)
class RunConfig:
    """How one run is set up. The three factors are the agent features under test."""

    solver: str = "agent"
    model: Optional[str] = None
    provider: Optional[str] = None
    planning: bool = False
    memory: bool = False
    metacognition: bool = False
    max_iterations: int = 30
    price_in: Optional[float] = None  # USD per million input tokens
    price_out: Optional[float] = None  # USD per million output tokens
    share_memory: bool = False  # keep long-term memory across tasks in one batch

    @property
    def label(self) -> str:
        if self.solver != "agent":
            return f"solver={self.solver}"
        on = lambda flag: "on" if flag else "off"  # noqa: E731
        return (
            f"planning={on(self.planning)} memory={on(self.memory)} "
            f"metacognition={on(self.metacognition)}"
        )


@dataclass
class TaskResult:
    task_id: str
    kind: str
    run: int
    config: str
    passed: bool
    status: str  # how the agent's turn ended, or the solver name for the stand-ins
    steps: int  # model calls
    tool_calls: int
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    tokens_estimated: Optional[bool]  # True if any call reported no usage and was estimated
    cost_usd: Optional[float]
    seconds: float
    error: Optional[str] = None
    verifier_tail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------------------
# Counting tokens (the meter is shared with unattended runs: cortex/headless/meter.py)
# ---------------------------------------------------------------------------------------


def cost(
    config: RunConfig, input_tokens: Optional[int], output_tokens: Optional[int]
) -> Optional[float]:
    """Dollars spent, or None when prices were not supplied. Never guessed."""
    if config.price_in is None or config.price_out is None:
        return None
    if input_tokens is None or output_tokens is None:
        return None
    return round((input_tokens * config.price_in + output_tokens * config.price_out) / 1e6, 6)


# ---------------------------------------------------------------------------------------
# Solvers
# ---------------------------------------------------------------------------------------


@dataclass
class Attempt:
    """What a solver did to the project."""

    status: str
    steps: int = 0
    tool_calls: int = 0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    tokens_estimated: Optional[bool] = None
    error: Optional[str] = None


ProviderFactory = Callable[[Task], Any]


def solve_agent(
    task: Task,
    project: Path,
    config: RunConfig,
    scratch: Path,
    provider_factory: Optional[ProviderFactory] = None,
    memory_dir: Optional[Path] = None,
) -> Attempt:
    """Let a Cortex agent try the task."""
    from cortex.agent import Cortex
    from cortex.config import AgentConfig
    from cortex.models import PermissionMode

    semantic: Dict[str, Any] = {}
    if config.memory:
        try:
            import chromadb  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "memory=on needs the memory extra: pip install 'cortex[memory]'"
            ) from e
        semantic = {
            "enabled": True,
            "persist_directory": str(memory_dir or scratch / "memory"),
            "collection_name": "bench",
        }

    agent_config = AgentConfig(
        model=config.model or "unset",
        provider=config.provider,
        permission_mode=PermissionMode.AUTO_APPROVE,
        max_iterations=config.max_iterations,
        semantic_memory=semantic,
        enable_metacognition=config.metacognition,
        # The project is a throwaway copy: no undo information is needed
        checkpoints={"enabled": False},
        transactions={"enabled": False},
    )
    agent = Cortex(
        model=config.model or "unset",
        project_dir=str(project),
        permission_mode=PermissionMode.AUTO_APPROVE,
        config=agent_config,
        enable_planning=config.planning,
        enable_layered_memory=config.memory or config.planning,
    )
    if provider_factory is not None:
        agent.provider = provider_factory(task)
    meter = UsageMeter(agent.provider)
    agent.provider = meter

    with contextlib.redirect_stdout(io.StringIO()):  # the agent narrates; the report is the output
        turn = agent._process_message(task.prompt)

    return Attempt(
        status=turn.status,
        steps=turn.iterations or meter.calls,
        tool_calls=turn.tool_calls,
        input_tokens=meter.input_tokens,
        output_tokens=meter.output_tokens,
        tokens_estimated=meter.estimated,
        error=turn.error,
    )


def solve_oracle(task: Task, project: Path, *_: Any, **__: Any) -> Attempt:
    apply_solution(task, project)
    return Attempt(status="oracle")


def solve_noop(task: Task, project: Path, *_: Any, **__: Any) -> Attempt:
    return Attempt(status="noop")


# ---------------------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------------------


def run_task(
    task: Task,
    config: RunConfig,
    run: int = 1,
    provider_factory: Optional[ProviderFactory] = None,
    memory_dir: Optional[Path] = None,
) -> TaskResult:
    with tempfile.TemporaryDirectory(prefix=f"bench-{task.id}-") as scratch_name:
        scratch = Path(scratch_name)
        project = scratch / "project"
        materialize(task, project)

        started = time.monotonic()
        error: Optional[str] = None
        try:
            if config.solver == "oracle":
                attempt = solve_oracle(task, project)
            elif config.solver == "noop":
                attempt = solve_noop(task, project)
            else:
                attempt = solve_agent(task, project, config, scratch, provider_factory, memory_dir)
        except Exception as e:  # one broken run must not lose the rest of the batch
            attempt = Attempt(status="crashed")
            error = f"{type(e).__name__}: {e}"
        verdict = verify(task, project)
        elapsed = time.monotonic() - started

    return TaskResult(
        task_id=task.id,
        kind=task.kind,
        run=run,
        config=config.label,
        passed=verdict.passed,
        status=attempt.status,
        steps=attempt.steps,
        tool_calls=attempt.tool_calls,
        input_tokens=attempt.input_tokens,
        output_tokens=attempt.output_tokens,
        tokens_estimated=attempt.tokens_estimated,
        cost_usd=cost(config, attempt.input_tokens, attempt.output_tokens),
        seconds=round(elapsed, 2),
        error=error or attempt.error,
        verifier_tail="" if verdict.passed else verdict.output[-600:],
    )


def ablation_configs(base: RunConfig, factors: Iterable[str]) -> List[RunConfig]:
    """Every on/off combination of the chosen factors (the others keep ``base``'s setting)."""
    factors = list(factors)
    unknown = [f for f in factors if f not in FACTORS]
    if unknown:
        raise ValueError(
            f"Unknown factor(s): {', '.join(unknown)}. Choose from {', '.join(FACTORS)}."
        )
    configs = []
    for values in itertools.product((False, True), repeat=len(factors)):
        configs.append(RunConfig(**{**asdict(base), **dict(zip(factors, values))}))
    return configs


def run_batch(
    configs: List[RunConfig],
    tasks: Optional[List[Task]] = None,
    runs: int = 1,
    provider_factory: Optional[ProviderFactory] = None,
    progress: Optional[Callable[[TaskResult], None]] = None,
) -> List[TaskResult]:
    """Every config x every task x ``runs`` repetitions."""
    tasks = tasks if tasks is not None else select()
    results: List[TaskResult] = []
    for config in configs:
        for run in range(1, runs + 1):
            shared = (
                tempfile.TemporaryDirectory(prefix="bench-memory-") if config.share_memory else None
            )
            try:
                for task in tasks:
                    result = run_task(
                        task,
                        config,
                        run,
                        provider_factory,
                        Path(shared.name) if shared else None,
                    )
                    results.append(result)
                    if progress:
                        progress(result)
            finally:
                if shared:
                    shared.cleanup()
    return results
