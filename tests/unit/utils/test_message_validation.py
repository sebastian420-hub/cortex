"""Tool-call pairing: detection, repair, safe trimming, and the conversation manager's own
truncation paths (which must never split a tool exchange)."""

import pytest

from cortex.utils.message_validation import (
    normalize_tool_messages,
    tool_order_violations,
    trim_history,
)


def _assistant(*call_ids):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": cid, "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
            for cid in call_ids
        ],
    }


def _tool(call_id, content="ok"):
    return {"role": "tool", "tool_call_id": call_id, "content": content}


USER = {"role": "user", "content": "go"}
SYSTEM = {"role": "system", "content": "sys"}


def test_valid_order_has_no_violations():
    messages = [SYSTEM, USER, _assistant("a", "b"), _tool("a"), _tool("b"), USER]
    assert tool_order_violations(messages) == []


def test_message_between_call_and_result_is_a_violation():
    messages = [SYSTEM, USER, _assistant("a"), _assistant("x"), _tool("x"), _tool("a")]
    problems = tool_order_violations(messages)
    assert problems[0]["type"] == "missing_result"
    assert problems[0]["index"] == 2
    assert problems[0]["interrupted_by"] == "assistant"


def test_unanswered_call_at_the_end_is_a_violation():
    problems = tool_order_violations([SYSTEM, USER, _assistant("a")])
    assert problems == [
        {"type": "missing_result", "index": 2, "ids": ["a"], "interrupted_by": "end"}
    ]


def test_result_with_no_call_is_an_orphan():
    problems = tool_order_violations([SYSTEM, USER, _tool("ghost")])
    assert problems[0]["type"] == "orphan_result"


def test_normalize_moves_results_next_to_their_calls():
    messages = [SYSTEM, USER, _assistant("a"), _assistant("x"), _tool("x"), _tool("a")]
    fixed, notes = normalize_tool_messages(messages)
    assert tool_order_violations(fixed) == []
    assert notes
    assert [m["role"] for m in fixed] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
    ]
    assert fixed[3]["tool_call_id"] == "a"


def test_normalize_adds_placeholder_for_missing_result_and_drops_orphans():
    messages = [SYSTEM, USER, _assistant("a"), USER, _tool("ghost")]
    fixed, notes = normalize_tool_messages(messages)
    assert tool_order_violations(fixed) == []
    assert any("placeholder" in n for n in notes)
    assert any("dropped" in n for n in notes)
    assert all(m.get("tool_call_id") != "ghost" for m in fixed)


def test_normalize_leaves_valid_history_untouched():
    messages = [SYSTEM, USER, _assistant("a"), _tool("a")]
    fixed, notes = normalize_tool_messages(messages)
    assert fixed is messages
    assert notes == []


def _long_history(exchanges, calls_per_message=2):
    history = [SYSTEM]
    for n in range(exchanges):
        history.append({"role": "user", "content": f"task {n}"})
        ids = [f"c{n}_{k}" for k in range(calls_per_message)]
        history.append(_assistant(*ids))
        history.extend(_tool(cid) for cid in ids)
        history.append({"role": "assistant", "content": f"done {n}"})
    return history


@pytest.mark.parametrize("keep_last", range(0, 14))
def test_trim_history_never_splits_a_tool_exchange(keep_last):
    trimmed = trim_history(_long_history(6), keep_last)
    assert trimmed[0]["role"] == "system"
    assert [p for p in tool_order_violations(trimmed) if p["type"] == "orphan_result"] == []


def test_trim_history_keeps_the_assistant_message_of_a_leading_tool_result():
    history = _long_history(3)
    # Cut so that the window would start on the second tool result of an exchange.
    cut = len(history) - 1  # last assistant "done"
    trimmed = trim_history(history, keep_last=len(history) - 1 - 3)
    first = trimmed[1]
    assert first["role"] != "tool"


# ---- the conversation manager's own truncation ------------------------------------------


@pytest.mark.parametrize("calls_per_message", [1, 2, 3])
@pytest.mark.parametrize("keep_recent", [2, 3, 4, 5, 7])
def test_context_truncation_never_breaks_tool_pairs(keep_recent, calls_per_message):
    from cortex.core.context import truncate_history

    history = _long_history(20, calls_per_message)
    truncated = truncate_history(
        history, max_tokens=300, keep_system=True, keep_recent=keep_recent, model="llama3.2"
    )
    assert len(truncated) < len(history)
    assert tool_order_violations(truncated) == []


@pytest.mark.parametrize("calls_per_message", [1, 2, 3])
@pytest.mark.parametrize("keep_recent", [2, 3, 4, 5, 7])
def test_summarization_split_never_breaks_tool_pairs(keep_recent, calls_per_message):
    from cortex.core.conversation import ConversationManager

    summarized = []

    class _Summary:
        def to_message(self):
            return {"role": "user", "content": "[summary]"}

    class _Summarizer:
        def should_summarize(self, *args, **kwargs):
            return True

        def summarize(self, messages, max_summary_tokens=500):
            summarized.extend(messages)
            return _Summary()

    manager = ConversationManager(
        system_prompt="sys",
        max_tokens=300,
        keep_recent=keep_recent,
        model="llama3.2",
        summarizer=_Summarizer(),
        enable_summarization=True,
    )
    manager.max_tokens = 300  # the constructor enforces a 2000-token floor; force the overflow
    manager.history = _long_history(20, calls_per_message)

    manager._optimize()

    assert summarized, "the summarization path should have run"
    assert tool_order_violations(manager.history) == []
    assert tool_order_violations(summarized) == [] or all(
        p["type"] == "missing_result" and p["interrupted_by"] == "end"
        for p in tool_order_violations(summarized)
    )
