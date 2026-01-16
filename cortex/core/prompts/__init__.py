"""Prompt management and model-specific profiles."""

from .profiles import (
    PromptProfile,
    PROMPT_PROFILES,
    get_prompt_profile,
    get_delegation_instructions,
)

__all__ = [
    "PromptProfile",
    "PROMPT_PROFILES",
    "get_prompt_profile",
    "get_delegation_instructions",
]
