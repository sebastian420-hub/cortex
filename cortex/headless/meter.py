"""Counting what a run spends, and stopping it when a budget is used up.

The meter wraps the model provider, so it sees every call. It uses the usage the provider reports;
a call that reports none is estimated from its text and the totals are flagged as estimates.

A budget stops a run by asking the agent to shut down (the same request SIGTERM makes), which ends
the turn cleanly at the next step. Raising an error instead would be swallowed by the agent's
retry logic. A limit only counts as having cut a run when the agent still wanted to continue: a
final answer that happens to cross a limit is a finished run.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

# Names of the limits, as they appear in a run's result
STEPS = "steps"
TOKENS = "tokens"
TIME = "time"


@dataclass(frozen=True)
class Budget:
    """What a run may spend. Zero means no limit."""

    max_steps: int = 0  # model calls, over the whole run
    max_tokens: int = 0  # input plus output tokens, over the whole run
    timeout_s: float = 0  # wall-clock seconds, over the whole run


class UsageMeter:
    """Wraps a provider and adds up the tokens its calls used."""

    def __init__(self, inner: Any):
        self._inner = inner
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.estimated = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        from cortex.core.context import estimate_tokens
        from cortex.core.providers.usage import usage_of_response

        response: Dict[str, Any] = self._inner.chat(model, messages, tools)
        self.calls += 1
        usage = usage_of_response(response)
        if usage:
            self.input_tokens += usage["input_tokens"]
            self.output_tokens += usage["output_tokens"]
        else:
            self.estimated = True
            self.input_tokens += sum(estimate_tokens(str(m.get("content", ""))) for m in messages)
            reply = response.get("message", {}) if isinstance(response, dict) else {}
            self.output_tokens += estimate_tokens(str(reply.get("content", "")))
        self._after_call(response)
        return response

    def _after_call(self, response: Any) -> None:
        """Hook for subclasses; runs after each call has been counted."""

    def supports_streaming(self) -> bool:  # every call must go through chat() to be counted
        return False


class RunMeter(UsageMeter):
    """A usage meter that enforces a :class:`Budget`."""

    def __init__(
        self,
        inner: Any,
        budget: Budget,
        started: float,
        clock: Callable[[], float],
        on_exceeded: Callable[[str], None],
    ):
        super().__init__(inner)
        self.budget = budget
        self._started = started
        self._clock = clock
        self._on_exceeded = on_exceeded
        self.exceeded: Optional[str] = None  # the limit that cut the run, if one did

    def reached(self) -> Optional[str]:
        """The first limit that is used up now, or None. Nothing new should be started then."""
        b = self.budget
        if b.max_steps and self.calls >= b.max_steps:
            return STEPS
        if b.max_tokens and self.input_tokens + self.output_tokens >= b.max_tokens:
            return TOKENS
        if b.timeout_s and self._clock() - self._started >= b.timeout_s:
            return TIME
        return None

    def _after_call(self, response: Any) -> None:
        if self.exceeded is not None:
            return
        reply = response.get("message", {}) if isinstance(response, dict) else {}
        wants_to_continue = bool(reply.get("tool_calls"))
        reason = self.reached()
        if reason and wants_to_continue:
            self.exceeded = reason
            self._on_exceeded(reason)
