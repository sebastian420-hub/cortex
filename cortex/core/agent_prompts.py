"""Prompt generation module - handles system prompt construction.

This module now serves as a thin wrapper around PromptBuilder to maintain
backward compatibility while utilizing the unified prompt system.
"""

import logging
from typing import TYPE_CHECKING

from ..tools.registry import get_registry
from ..ui.console import console
from .prompts.builder import PromptBuilder

if TYPE_CHECKING:
    from ..agent import Cortex

logger = logging.getLogger(__name__)


class PromptGenerator:
    """
    Legacy wrapper for generating system prompts.

    Now delegates most work to PromptBuilder while maintaining
    the original interface for the base Cortex agent.
    """

    def __init__(self, agent: "Cortex"):
        """
        Initialize with reference to parent agent.

        Args:
            agent: Parent Cortex agent instance
        """
        self.agent = agent
        self.builder = PromptBuilder(agent.model, project_dir=agent.project_dir)

    def generate(self) -> str:
        """
        Generate complete system prompt using the unified PromptBuilder.

        Returns:
            Complete system prompt string
        """
        # Get dynamic context from agent
        state_context = (
            self.agent.state_manager.get_llm_context()
            if hasattr(self.agent, "state_manager")
            else None
        )
        memory_bank_context = (
            self.agent.memory_bank.get_summary() if hasattr(self.agent, "memory_bank") else None
        )

        # Get metacognitive context
        metacognitive_context = (
            self.agent.state_manager.get_metacognitive_context()
            if hasattr(self.agent, "state_manager")
            else None
        )

        # Get all tool schemas
        tool_schemas = get_registry().get_all_schemas()

        # Delegate to the unified builder
        return self.builder.build_system_prompt(
            tools=tool_schemas,
            enable_planning=getattr(self.agent, "enable_planning", False),
            enable_memory=getattr(self.agent, "enable_layered_memory", False),
            state_context=state_context,
            project_context=getattr(self.agent, "project_context", None),
            memory_bank_context=memory_bank_context,
            metacognitive_context=metacognitive_context,
            permission_mode=self.agent.permission_mode,
        )

    def load_project_context(self) -> str:
        """
        Load AGENT.md, CLAUDE.md, or README.md for project context.

        Returns:
            Project context string (up to 2000 chars) or empty string
        """
        context_files = ["AGENT.md", "CLAUDE.md", "README.md"]

        for filename in context_files:
            filepath = self.agent.project_dir / filename
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8-sig")
                    console.print(f"[dim]Loaded project context from {filename}[/dim]")
                    return content[:2000]  # Limit context size
                except (UnicodeDecodeError, IOError, OSError) as e:
                    logger.debug(f"Failed to read {filename}: {e}")
                    continue
        return ""
