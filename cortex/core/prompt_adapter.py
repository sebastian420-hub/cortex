"""Prompt adapter for model-specific optimizations.

This module provides utilities to adapt prompts based on model capabilities
without replacing the core system prompt.
"""

import logging
from typing import Optional

from .model_capabilities import (
    get_model_profile,
    PromptStyle,
    CapabilityLevel,
    ModelProfile,
)

logger = logging.getLogger(__name__)


def get_model_adaptation_notes(model_name: str) -> str:
    """
    Get model-specific adaptation notes to append to system prompt.

    For models with lower capability, adds explicit guidance.
    For capable models, returns minimal or no additions.

    Args:
        model_name: Name of the model

    Returns:
        Adaptation notes string (may be empty for capable models)
    """
    profile = get_model_profile(model_name)
    notes = []

    # Add notes for limited tool following
    if profile.tool_following in (CapabilityLevel.MODERATE, CapabilityLevel.LIMITED):
        notes.append("""
## Tool Usage Reminders

- Use ONE tool at a time
- Wait for results before next action
- Follow exact parameter formats
- Check results before proceeding""")

    # Add notes for limited reasoning
    if profile.reasoning in (CapabilityLevel.MODERATE, CapabilityLevel.LIMITED):
        notes.append("""
## Problem-Solving Approach

- Break complex tasks into simple steps
- Complete one step before starting the next
- Verify each step's result""")

    # Add explicit formatting for smaller models
    if profile.prompt_style == PromptStyle.EXPLICIT:
        notes.append("""
## Response Format

When using tools, format carefully:
1. State what you're doing
2. Call the tool with correct parameters
3. Wait for the result
4. Explain what happened""")

    if notes:
        return "\n".join(notes)
    return ""


def should_simplify_tools(model_name: str, tool_count: int) -> bool:
    """
    Check if tools should be simplified/reduced for this model.

    Args:
        model_name: Name of the model
        tool_count: Number of tools being provided

    Returns:
        True if tools should be reduced
    """
    profile = get_model_profile(model_name)
    return tool_count > profile.max_tools_per_prompt


def get_tool_priority_list(model_name: str) -> list:
    """
    Get prioritized list of tool names for this model.

    Args:
        model_name: Name of the model

    Returns:
        List of tool names in priority order
    """
    profile = get_model_profile(model_name)

    # Core tools always included
    core_tools = [
        "read_file",
        "edit_file",
        "write_file",
        "grep_search",
        "glob_files",
        "bash",
    ]

    # Extended tools for capable models
    extended_tools = [
        "create_plan",
        "execute_plan",
        "monitor_plan",
        "update_plan",
        "web_search",
        "web_fetch",
        "ast_analyze",
    ]

    if profile.max_tools_per_prompt >= 30:
        return core_tools + extended_tools
    elif profile.max_tools_per_prompt >= 15:
        return core_tools + extended_tools[:4]
    else:
        return core_tools


def get_context_budget(model_name: str) -> dict:
    """
    Get recommended context budget allocation for this model.

    Args:
        model_name: Name of the model

    Returns:
        Dict with budget allocations
    """
    profile = get_model_profile(model_name)
    context = profile.context_window

    # Reserve portions for different content
    # More conservative for smaller context windows
    if context >= 100000:
        return {
            "system_prompt": int(context * 0.15),
            "tools": int(context * 0.10),
            "conversation": int(context * 0.60),
            "state_context": int(context * 0.10),
            "reserve": int(context * 0.05),
        }
    elif context >= 32000:
        return {
            "system_prompt": int(context * 0.15),
            "tools": int(context * 0.10),
            "conversation": int(context * 0.55),
            "state_context": int(context * 0.10),
            "reserve": int(context * 0.10),
        }
    else:  # < 32000
        return {
            "system_prompt": int(context * 0.20),
            "tools": int(context * 0.10),
            "conversation": int(context * 0.50),
            "state_context": int(context * 0.10),
            "reserve": int(context * 0.10),
        }


def adapt_system_prompt(
    base_prompt: str,
    model_name: str,
    include_adaptations: bool = True,
) -> str:
    """
    Adapt a system prompt based on model capabilities.

    Args:
        base_prompt: The base system prompt
        model_name: Name of the model
        include_adaptations: Whether to include model-specific notes

    Returns:
        Adapted system prompt
    """
    if not include_adaptations:
        return base_prompt

    adaptations = get_model_adaptation_notes(model_name)
    if adaptations:
        return f"{base_prompt}\n\n{adaptations}"

    return base_prompt


def get_profile_info(model_name: str) -> dict:
    """
    Get profile information for logging/debugging.

    Args:
        model_name: Name of the model

    Returns:
        Dict with profile information
    """
    profile = get_model_profile(model_name)
    return {
        "model": model_name,
        "profile_name": profile.name,
        "prompt_style": profile.prompt_style.value,
        "context_window": profile.context_window,
        "max_tools": profile.max_tools_per_prompt,
        "tool_following": profile.tool_following.value,
        "reasoning": profile.reasoning.value,
        "supports_json_mode": profile.supports_json_mode,
        "supports_streaming": profile.supports_streaming,
    }
