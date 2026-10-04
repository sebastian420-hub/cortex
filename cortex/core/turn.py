"""The outcome of one agent turn (one user message, run to completion)."""

from dataclasses import dataclass
from typing import Optional

# How a turn can end.
STATUS_OK = "ok"  # the model gave a final answer
STATUS_ERROR = "error"  # an exception stopped the turn
STATUS_MAX_ITERATIONS = "max_iterations"  # the iteration limit was reached first
STATUS_LOOP_GUARD = "loop_guard"  # stopped after the same error kept repeating
STATUS_BLOCKED = "blocked"  # a hook refused the prompt
STATUS_INTERRUPTED = "interrupted"  # shutdown was requested


@dataclass
class TurnResult:
    """What happened in a turn. Callers (CLI exit codes, the gym, subagents, benchmarks) read
    this instead of guessing from printed output."""

    status: str
    final_text: str = ""
    error: Optional[str] = None
    iterations: int = 0
    tool_calls: int = 0

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK
