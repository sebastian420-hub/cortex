"""Prompt management and model-specific profiles.

This module provides:
- PromptProfile: Role-based prompt profiles for model orchestration
- PromptBuilder: Dynamic prompt generation based on model capabilities
- ToolFormatter: Model-adaptive tool documentation formatting
"""

from .profiles import (
    PromptProfile,
    PROMPT_PROFILES,
    get_prompt_profile,
    get_delegation_instructions,
    get_delegation_context_prompt,
)
from .builder import (
    PromptBuilder,
    ToolFormatter,
)

__all__ = [
    # Role-based profiles
    "PromptProfile",
    "PROMPT_PROFILES",
    "get_prompt_profile",
    "get_delegation_instructions",
    "get_delegation_context_prompt",
    # Dynamic prompt builder
    "PromptBuilder",
    "ToolFormatter",
]
