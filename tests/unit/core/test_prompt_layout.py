"""The system prompt is a stable prefix followed by a changing suffix.

Providers cache prompts by prefix, so anything that changes during a session (memory summaries,
retrieved context, state, mood) has to come *after* everything that does not (identity, tool
documentation, planning guidance, project context). Otherwise every iteration of the agent loop
re-bills the whole prompt.
"""

import os
from pathlib import Path

from cortex.core.prompts.builder import PromptBuilder
from cortex.tools import get_registry

TOOLS = get_registry().get_all_schemas()
STABLE_MARKERS = ("PROJECT-CONTEXT-TEXT", "CUSTOM-INSTRUCTIONS-TEXT", "read_file", "# Memory System")


def _build(**dynamic):
    builder = PromptBuilder("llama3.2", project_dir=Path("/work/project"))
    return builder.build_system_prompt(
        tools=TOOLS,
        enable_planning=True,
        enable_memory=True,
        project_context="PROJECT-CONTEXT-TEXT",
        custom_instructions="CUSTOM-INSTRUCTIONS-TEXT",
        **dynamic,
    )


def test_changing_context_only_affects_the_end_of_the_prompt():
    first = _build(
        state_context="STATE-ONE",
        memory_bank_context="BANK-ONE",
        semantic_context="SEMANTIC-ONE",
        metacognitive_context="MOOD-ONE",
    )
    second = _build(
        state_context="STATE-TWO",
        memory_bank_context="BANK-TWO",
        semantic_context="SEMANTIC-TWO",
        metacognitive_context="MOOD-TWO",
    )

    shared = os.path.commonprefix([first, second])

    for marker in STABLE_MARKERS:
        assert marker in shared, f"{marker!r} should be part of the cacheable prefix"
    for dynamic in ("STATE-ONE", "BANK-ONE", "SEMANTIC-ONE", "MOOD-ONE"):
        assert dynamic not in shared
        assert first.index(dynamic) > first.index("PROJECT-CONTEXT-TEXT")


def test_same_inputs_give_an_identical_prompt():
    kwargs = dict(state_context="S", memory_bank_context="B", semantic_context="X")
    assert _build(**kwargs) == _build(**kwargs)


def test_no_empty_dynamic_sections_when_there_is_no_dynamic_context():
    prompt = _build()

    assert "# Current State" not in prompt
    assert "Relevant Historical Context" not in prompt
    assert "Internal Metacognition" not in prompt


def test_dynamic_sections_keep_their_headings():
    prompt = _build(
        state_context="STATE-ONE",
        memory_bank_context="BANK-ONE",
        semantic_context="SEMANTIC-ONE",
        metacognitive_context="MOOD-ONE",
    )

    for heading in (
        "# Current State",
        "Session Memory",
        "Relevant Historical Context",
        "# Internal Metacognition",
    ):
        assert heading in prompt
