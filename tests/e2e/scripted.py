"""A scripted fake model provider for deterministic end-to-end tests.

``ScriptedProvider`` replays a fixed list of assistant messages, one per model call, and
records every conversation it was sent. That lets a test drive the *real* agent loop (tool
dispatch, permissions, memory, planning) with no network and no real model.
"""

import json
from typing import Any, Dict, Iterator, List, Optional

from cortex.core.providers.base import ModelProvider


class ScriptedProvider(ModelProvider):
    """Replays scripted assistant messages and records the messages it receives."""

    def __init__(self, script: List[Dict[str, Any]]):
        self.script = list(script)
        # Deep copies of the message list sent on each call, in call order.
        self.seen: List[List[Dict[str, Any]]] = []

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        self.seen.append(json.loads(json.dumps(messages, default=str)))
        if not self.script:
            return {"message": {"role": "assistant", "content": "done (script exhausted)"}}
        return {"message": self.script.pop(0)}

    def stream_chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError("ScriptedProvider does not stream")

    def supports_streaming(self) -> bool:
        return False

    def normalize_model_name(self, model: str) -> str:
        return model

    def validate_api_key(self) -> bool:
        return True


def tool_call(name: str, arguments: Dict[str, Any], call_id: str = "call_1") -> Dict[str, Any]:
    """An assistant message that requests one tool call."""
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


def final(text: str) -> Dict[str, Any]:
    """An assistant message with a final text answer and no tool calls."""
    return {"role": "assistant", "content": text}


def tool_order_violations(messages: List[Dict[str, Any]]) -> List[tuple]:
    """Check the OpenAI/Anthropic pairing rule for tool calls.

    An assistant message with ``tool_calls`` must be *immediately* followed by one ``tool``
    message per call id, before any other message. Returns ``(index, missing_ids, next_role)``
    for every assistant message that breaks the rule; an empty list means the order is valid.
    """
    problems = []
    for i, message in enumerate(messages):
        if message.get("role") != "assistant" or not message.get("tool_calls"):
            continue
        needed = {call["id"] for call in message["tool_calls"]}
        j = i + 1
        while needed and j < len(messages) and messages[j].get("role") == "tool":
            needed.discard(messages[j].get("tool_call_id"))
            j += 1
        if needed:
            next_role = messages[j]["role"] if j < len(messages) else "END"
            problems.append((i, sorted(needed), next_role))
    return problems
