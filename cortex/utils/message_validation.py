"""Keep tool-call messages valid for chat APIs.

OpenAI-style and Anthropic APIs enforce a pairing rule: an assistant message that requests tool
calls must be followed *immediately* by one ``tool`` message per call id, before any other
message. A conversation that breaks it is rejected (HTTP 400) by strict providers.

Anything that edits history can break the rule: inserting messages while a tool call is
pending, truncating or summarizing the middle of a conversation, or trimming after an overflow.
This module detects violations, repairs them, and trims history without splitting a tool
exchange.
"""

from typing import Any, Dict, List, Tuple

Message = Dict[str, Any]

MISSING_RESULT_TEXT = "[no result was recorded for this tool call]"


def tool_order_violations(messages: List[Message]) -> List[Dict[str, Any]]:
    """Find every place the tool-call pairing rule is broken.

    Returns one dict per problem; an empty list means the order is valid:

    - ``missing_result``: an assistant message's tool calls were not all answered right after
      it. ``index`` is the assistant message, ``ids`` the unanswered call ids,
      ``interrupted_by`` the role of the message that got in the way (or ``"end"``).
    - ``orphan_result``: a ``tool`` message answers no pending call. ``index`` is that message.
    """
    problems: List[Dict[str, Any]] = []
    pending: set = set()
    pending_index = -1

    def close_pending(interrupted_by: str) -> None:
        nonlocal pending
        if pending:
            problems.append(
                {
                    "type": "missing_result",
                    "index": pending_index,
                    "ids": sorted(pending),
                    "interrupted_by": interrupted_by,
                }
            )
            pending = set()

    for i, message in enumerate(messages):
        role = message.get("role")
        if role == "tool":
            call_id = message.get("tool_call_id")
            if call_id in pending:
                pending.discard(call_id)
            else:
                problems.append({"type": "orphan_result", "index": i, "ids": [call_id]})
            continue

        close_pending(str(role))
        if role == "assistant" and message.get("tool_calls"):
            pending = {call.get("id") for call in message["tool_calls"]}
            pending_index = i

    close_pending("end")
    return problems


def normalize_tool_messages(messages: List[Message]) -> Tuple[List[Message], List[str]]:
    """Repair the pairing rule.

    Each tool result is moved to directly follow the assistant message that requested it, a
    placeholder result is added for any call that has none, and results that answer no call
    are dropped. Returns ``(messages, notes)``; when nothing needed fixing the original list is
    returned unchanged with no notes.
    """
    if not tool_order_violations(messages):
        return messages, []

    results_by_id: Dict[Any, Message] = {}
    for message in messages:
        if message.get("role") == "tool":
            results_by_id.setdefault(message.get("tool_call_id"), message)

    fixed: List[Message] = []
    notes: List[str] = []
    used: set = set()

    for message in messages:
        role = message.get("role")
        if role == "tool":
            continue  # re-emitted below, next to the assistant message that asked for it
        fixed.append(message)
        if role == "assistant" and message.get("tool_calls"):
            for call in message["tool_calls"]:
                call_id = call.get("id")
                if call_id in results_by_id and call_id not in used:
                    fixed.append(results_by_id[call_id])
                    used.add(call_id)
                else:
                    fixed.append(
                        {"role": "tool", "tool_call_id": call_id, "content": MISSING_RESULT_TEXT}
                    )
                    notes.append(f"added a placeholder result for tool call {call_id}")

    for call_id in results_by_id:
        if call_id not in used:
            notes.append(f"dropped a tool result that answers no tool call ({call_id})")

    if not notes:
        notes.append("moved tool results to directly follow their tool calls")
    return fixed, notes


def tail_start(messages: List[Message], keep_last: int) -> int:
    """Index where the last ``keep_last`` messages begin, without splitting a tool exchange.

    A plain ``messages[-keep_last:]`` can start on a tool result whose request was cut off,
    which strict chat APIs reject. If the window would start on a tool result, it grows
    backwards until it includes the assistant message that requested it.
    """
    start = max(0, len(messages) - max(keep_last, 0))
    while 0 < start < len(messages) and messages[start].get("role") == "tool":
        start -= 1
    return start


def trim_history(history: List[Message], keep_last: int) -> List[Message]:
    """Keep the system prompt and roughly the last ``keep_last`` messages (see tail_start)."""
    if not history:
        return []
    has_system = history[0].get("role") == "system"
    system = [history[0]] if has_system else []
    body = history[1:] if has_system else list(history)
    return system + body[tail_start(body, keep_last) :]
