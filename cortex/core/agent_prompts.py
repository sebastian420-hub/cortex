"""Prompt generation module - handles system prompt construction"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ..models import PermissionMode
from ..ui.console import console
from .prompts import adapt_prompt_for_model

if TYPE_CHECKING:
    from ..agent import Cortex

logger = logging.getLogger(__name__)


class PromptGenerator:
    """
    Generates system prompts with context and memory.

    Responsibilities:
    - Generate base system prompts
    - Include project context from AGENT.md/CLAUDE.md/README.md
    - Add memory bank contents
    - Include state manager context
    - Add permission mode instructions
    - Model-specific adaptations
    """

    def __init__(self, agent: 'Cortex'):
        """
        Initialize with reference to parent agent.

        Args:
            agent: Parent Cortex agent instance
        """
        self.agent = agent

    def generate(self) -> str:
        """
        Generate complete system prompt.

        Returns:
            Complete system prompt with all context
        """
        sections = []

        # Base prompt with permission mode
        sections.append(self._get_base_prompt())

        # Project context (from AGENT.md, CLAUDE.md, or README.md)
        if self.agent.project_context:
            sections.append(self._format_project_context())

        # Memory bank summary
        if hasattr(self.agent, 'memory_bank') and self.agent.memory_bank:
            memory_summary = self.agent.memory_bank.get_summary()
            if memory_summary:
                sections.append(self._format_memory_bank(memory_summary))

        # State manager context
        if hasattr(self.agent, 'state_manager') and self.agent.state_manager:
            state_context = self.agent.state_manager.get_llm_context()
            if state_context:
                sections.append(self._format_state_context(state_context))

        # Orchestration prompt (if enabled)
        orchestration_prompt = self._get_orchestration_prompt()
        if orchestration_prompt:
            sections.append(orchestration_prompt)

        # Combine all sections
        prompt = "\n\n".join(sections)

        # Apply model-specific adaptations
        return adapt_prompt_for_model(prompt, self.agent.model)

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

    def _get_base_prompt(self) -> str:
        """Get base system prompt with capabilities and instructions"""
        mode_instructions = {
            PermissionMode.NORMAL: "Ask for user approval before making changes.",
            PermissionMode.AUTO_APPROVE: "You can make changes without asking. Be careful!",
            PermissionMode.PLAN: "You are in PLAN MODE - read-only. Do not write files or execute commands. Only analyze and create plans.",
        }

        return f"""You are Cortex, a powerful AI coding assistant working in: {self.agent.project_dir}

Permission Mode: {self.agent.permission_mode.upper()}
{mode_instructions[self.agent.permission_mode]}

# Mental Model for Codebase Understanding

When exploring a new codebase, build understanding systematically:

## Phase 1: Structure Discovery (1-2 tool calls)
```
glob(pattern="**/*.py")  # Map all source files
```
From this, identify:
- Entry points (main.py, cli.py, app.py, __main__.py)
- Core packages (src/, lib/, cortex/)
- Tests location (tests/, test_*)
- Config files (*.yaml, *.json, *.toml)

## Phase 2: Architecture Understanding (2-3 tool calls)
```
grep(pattern="^class ", file_type="py")           # Find all classes
grep(pattern="^def |^async def ", file_type="py") # Find top-level functions
```
Build a mental map:
- Entry points -> Core logic -> Utilities -> Data models

## Phase 3: Targeted Deep Dives
Only read files when you have a specific reason. Track what you've read to avoid re-reading.

**Efficiency Rule**: Always use `files_with_matches` mode first for breadth, then `content` mode only when narrowing down.

# Self-Awareness

## Your Capabilities
- **Search**: glob for files, grep for content - these are your eyes
- **Read**: Deep understanding of specific files
- **Edit**: Surgical changes with exact string replacement
- **Write**: Create new files or replace content entirely
- **Execute**: Run commands, tests, git operations
- **AST Analysis**: Structural code understanding with ast_search, ast_extract, ast_analyze

## AST Tools (Code Analysis)
Use these for deeper code understanding beyond text search:

- **ast_search**: Find functions/classes/imports by structure (better than grep for code patterns)
  - `ast_search(pattern="process_", search_type="function")` - find all functions starting with "process_"
  - `ast_search(pattern="Manager", search_type="class")` - find all Manager classes

- **ast_extract**: Get full code structures with metadata (docstrings, decorators, parameters)
  - `ast_extract(path="src/", extract_type="function")` - list all functions with details
  - `ast_extract(path="file.py", pattern="main", extract_type="function")` - get specific function

- **ast_analyze**: Code complexity and quality analysis
  - `ast_analyze(path="src/", analysis_type="complexity")` - get metrics (lines, functions, complexity)
  - `ast_analyze(analysis_type="issues")` - find code smells (long functions, too many params)

**When to use grep vs ast_search:**
- grep: text patterns, strings, comments, quick searches
- ast_search: function/class definitions, imports, structural patterns

## Your Limitations
- Cannot see file changes until you re-read them
- Cannot run interactive commands (vi, less, etc.)
- Cannot access external URLs without web tools
- Token-limited: be efficient, avoid reading entire codebases

## Decision Making
- **Confident action**: When you know exactly what to do, do it
- **Ask first**: When requirements are ambiguous or risky
- **Investigate first**: When you need more context before deciding

# Efficiency Patterns

## Minimize Tool Calls
BAD: Read every file to find a function
GOOD: grep(pattern="def target_function") -> read only the matching file

BAD: Multiple greps for related things
GOOD: Single grep with OR pattern: "class.*Service|def.*service"

## Optimal Search Strategy
1. Start broad: glob to map the codebase
2. Narrow down: grep to find specific patterns
3. Deep dive: read only the files that matter
4. Act: edit/write with precision

# Output Guidelines
- Be concise and actionable
- Show your reasoning when making decisions
- Use code blocks for code
- Explain complex changes
"""

    def _format_project_context(self) -> str:
        """Format project context section"""
        return f"""# Project Context

{self.agent.project_context}
"""

    def _format_memory_bank(self, memory_summary: str) -> str:
        """Format memory bank section"""
        return f"""# Session Memory

{memory_summary}
"""

    def _format_state_context(self, state_context: str) -> str:
        """Format state manager context"""
        return f"""# Current State

{state_context}
"""

    def _get_orchestration_prompt(self) -> str:
        """
        Generate orchestration-specific prompt injection for current model.

        Returns:
            Orchestration prompt or empty string if not enabled
        """
        # Check if orchestration has been initialized yet
        if not hasattr(self.agent, "_orchestration_enabled") or not self.agent._orchestration_enabled:
            return ""
        if not hasattr(self.agent, "_model_registry") or not self.agent._model_registry:
            return ""

        # Get model config
        model_config = self.agent._model_registry.get_model(self.agent.model)
        if not model_config:
            return ""

        # Get available delegation targets
        available_delegates = self.agent._model_registry.get_delegation_targets(self.agent.model)

        # Get remaining delegations
        remaining = 5  # Default
        if hasattr(self.agent, '_delegation_tracker') and self.agent._delegation_tracker:
            remaining = self.agent._delegation_tracker.get_remaining()

        # Get delegation instructions
        from .prompts import get_delegation_instructions
        profile_name = model_config.prompt_profile
        prompt = get_delegation_instructions(
            current_model=self.agent.model,
            available_delegates=available_delegates,
            remaining_delegations=remaining,
            profile_name=profile_name
        )

        return prompt
