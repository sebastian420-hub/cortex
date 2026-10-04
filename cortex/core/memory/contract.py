"""The memory contract: what is allowed into long-term memory.

Long-term (vector) memory is only useful if what is in it is worth retrieving. Writing every
user request, every failed tool call and every "read_file on a.py" into it buries the few entries
that matter (a convention, a decision and its reason, how a hard problem was solved) under
noise that then gets injected into prompts.

Stored:
- decisions, preferences/conventions and explicit facts,
- summaries of solved problems (reflections),
- anything the user or the model was explicitly asked to remember.

Not stored (the session still keeps them for as long as it runs):
- the user's raw requests, progress markers, context summaries and auto-generated insights,
- raw errors and failed approaches,
- file references and "file operation" patterns,
- anything marked transient.
"""

from .core_memory import MemoryItem, MemoryType

# Metadata flags the session sets on its own bookkeeping
SESSION_BOOKKEEPING = (
    "goal_set",
    "session_insight",
    "progress_marker",
    "context_summary",
    "failed_approach",
    "transient",
)
_DURABLE_TYPES = {MemoryType.DECISION, MemoryType.PREFERENCE, MemoryType.FACT}
_MIN_CONTENT_CHARS = 8


def should_index(item: MemoryItem) -> bool:
    """True when ``item`` belongs in long-term memory."""
    content = (item.content or "").strip()
    if len(content) < _MIN_CONTENT_CHARS:
        return False

    metadata = item.metadata or {}
    if metadata.get("remembered"):  # the user (or the model, on request) said to keep it
        return True
    if any(metadata.get(flag) for flag in SESSION_BOOKKEEPING):
        return False
    if metadata.get("synthetic") or metadata.get("solved_problem"):
        return True
    return item.type in _DURABLE_TYPES
