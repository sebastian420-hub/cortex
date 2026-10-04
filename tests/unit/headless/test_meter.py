"""The meter counts what a run spends and stops it when a budget is used up. It stops the run by
asking the agent to shut down, not by raising: the agent's retry logic would swallow an error."""

from typing import Any, Dict, List, Optional

import pytest

from cortex.headless.meter import Budget, RunMeter, UsageMeter


class FakeProvider:
    """Returns the queued responses; carries attributes a real provider has."""

    context_window = 4096

    def __init__(self, responses: List[Dict[str, Any]]):
        self.responses = list(responses)

    def chat(self, model, messages, tools=None):
        return self.responses.pop(0)

    def normalize_model_name(self, model):
        return model


def answer(text="done", usage: Optional[Dict[str, int]] = None):
    response: Dict[str, Any] = {"message": {"role": "assistant", "content": text}}
    if usage:
        response["usage"] = usage
    return response


def wants_more(usage: Optional[Dict[str, int]] = None):
    response = answer("", usage)
    response["message"]["tool_calls"] = [
        {"id": "c", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
    ]
    return response


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def meter(responses, budget=None, clock=None, hits=None):
    clock = clock or Clock()
    return RunMeter(
        FakeProvider(responses),
        budget or Budget(),
        started=clock(),
        clock=clock,
        on_exceeded=(hits.append if hits is not None else (lambda reason: None)),
    )


# ---- counting -----------------------------------------------------------------------------


def test_it_adds_up_the_usage_providers_report():
    m = UsageMeter(
        FakeProvider(
            [
                answer(usage={"input_tokens": 100, "output_tokens": 20}),
                answer(usage={"input_tokens": 50, "output_tokens": 5}),
            ]
        )
    )

    m.chat("m", [])
    m.chat("m", [])

    assert (m.calls, m.input_tokens, m.output_tokens, m.estimated) == (2, 150, 25, False)


def test_a_call_with_no_usage_is_estimated_and_flagged():
    m = UsageMeter(FakeProvider([answer("some reply text")]))

    m.chat("m", [{"role": "user", "content": "a question"}])

    assert m.estimated is True
    assert m.input_tokens > 0 and m.output_tokens > 0


def test_it_behaves_like_the_provider_it_wraps():
    m = UsageMeter(FakeProvider([]))

    assert m.context_window == 4096
    assert m.normalize_model_name("x") == "x"
    assert m.supports_streaming() is False  # every call must go through chat() to be counted


# ---- budgets ------------------------------------------------------------------------------


def test_the_run_is_cut_when_the_step_limit_is_reached_and_the_agent_wants_more():
    hits = []
    m = meter([wants_more(), wants_more(), wants_more()], Budget(max_steps=2), hits=hits)

    m.chat("m", [])
    assert hits == []
    m.chat("m", [])

    assert hits == ["steps"] and m.exceeded == "steps"


def test_the_run_is_cut_when_the_token_limit_is_reached():
    hits = []
    usage = {"input_tokens": 60, "output_tokens": 40}
    m = meter([wants_more(usage), wants_more(usage)], Budget(max_tokens=150), hits=hits)

    m.chat("m", [])
    assert hits == []
    m.chat("m", [])

    assert hits == ["tokens"]


def test_the_run_is_cut_when_the_time_limit_is_reached():
    clock, hits = Clock(), []
    m = meter([wants_more(), wants_more()], Budget(timeout_s=60), clock, hits)

    clock.now = 30
    m.chat("m", [])
    assert hits == []
    clock.now = 61
    m.chat("m", [])

    assert hits == ["time"]


def test_a_final_answer_that_crosses_a_limit_is_not_cut():
    hits = []
    m = meter([answer("all done")], Budget(max_steps=1), hits=hits)

    m.chat("m", [])

    assert hits == [] and m.exceeded is None
    assert m.reached() == "steps"  # but nothing more may be started


def test_a_limit_of_zero_means_no_limit():
    hits = []
    m = meter([wants_more()] * 5, Budget(max_steps=0, max_tokens=0, timeout_s=0), hits=hits)

    for _ in range(5):
        m.chat("m", [])

    assert hits == [] and m.reached() is None


def test_the_budget_is_reported_once():
    hits = []
    m = meter([wants_more(), wants_more()], Budget(max_steps=1), hits=hits)

    m.chat("m", [])
    m.chat("m", [])

    assert hits == ["steps"]


def test_the_response_is_passed_through_untouched():
    response = wants_more({"input_tokens": 1, "output_tokens": 1})
    m = meter([response], Budget(max_steps=1))

    assert m.chat("m", []) is response


@pytest.mark.parametrize(
    "budget,calls,tokens,elapsed,expected",
    [
        (Budget(max_steps=3), 3, 0, 0, "steps"),
        (Budget(max_tokens=100), 0, 100, 0, "tokens"),
        (Budget(timeout_s=5), 0, 0, 5, "time"),
        (Budget(max_steps=3, max_tokens=100, timeout_s=5), 1, 10, 1, None),
    ],
)
def test_reached_names_the_limit_that_is_used_up(budget, calls, tokens, elapsed, expected):
    clock = Clock()
    m = meter([], budget, clock)
    m.calls, m.input_tokens = calls, tokens
    clock.now = elapsed

    assert m.reached() == expected
