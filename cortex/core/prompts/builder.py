"""Dynamic prompt builder with model adaptation.

This module provides a PromptBuilder class that generates prompts
optimized for different model capabilities.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..model_capabilities import (
    get_model_profile,
    ModelProfile,
    PromptStyle,
    CapabilityLevel,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Tool Formatter
# =============================================================================


class ToolFormatter:
    """Formats tool documentation based on model capabilities."""

    def __init__(self, profile: ModelProfile):
        self.profile = profile

    def format_tools(self, tools: List[Dict[str, Any]]) -> str:
        """
        Format tool list based on model capability.

        Args:
            tools: List of tool definitions

        Returns:
            Formatted tool documentation string
        """
        if not tools:
            return ""

        # Prioritize tools if too many
        if len(tools) > self.profile.max_tools_per_prompt:
            tools = self._prioritize_tools(tools)

        # Format based on style
        if self.profile.prompt_style == PromptStyle.DETAILED:
            return self._format_detailed(tools)
        elif self.profile.prompt_style == PromptStyle.CONCISE:
            return self._format_concise(tools)
        else:  # EXPLICIT
            return self._format_explicit(tools)

    def _prioritize_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prioritize tools when there are too many for the model."""
        # Priority order for common tool categories
        priority_order = [
            # File operations - most commonly needed
            "read_file",
            "write_file",
            "edit",
            "edit_file",
            # Search operations
            "grep",
            "grep_search",
            "glob",
            "glob_files",
            "list_files",
            # Execution
            "bash",
            "execute_command",
            # Planning
            "create_plan",
            "execute_plan",
            "monitor_plan",
            "todo_write",
            # Web
            "web_search",
            "web_fetch",
            # AST
            "ast_search",
            "ast_extract",
        ]

        def get_priority(tool: Dict[str, Any]) -> int:
            name = tool.get("name", "").lower()
            try:
                return priority_order.index(name)
            except ValueError:
                return len(priority_order)  # Unknown tools go last

        sorted_tools = sorted(tools, key=get_priority)
        return sorted_tools[: self.profile.max_tools_per_prompt]

    def _format_detailed(self, tools: List[Dict[str, Any]]) -> str:
        """Full documentation with examples for capable models."""
        sections = ["# Available Tools\n"]
        sections.append("You have access to the following tools. Use them to accomplish tasks.\n")

        for tool in tools:
            # Handle both function schema and direct schema
            if "function" in tool:
                tool_data = tool["function"]
            else:
                tool_data = tool

            name = tool_data.get("name", "unknown")
            description = tool_data.get("description", "No description")
            parameters = tool_data.get("parameters", {})

            sections.append(f"## {name}\n")
            sections.append(f"{description}\n")

            # Format parameters
            if parameters:
                sections.append("**Parameters:**")
                params_info = self._format_parameters(parameters)
                sections.append(params_info)

            # Generate example
            example = self._generate_example(tool_data)
            sections.append(f"\n**Example:**\n```json\n{example}\n```\n")

        return "\n".join(sections)

    def _format_concise(self, tools: List[Dict[str, Any]]) -> str:
        """Shorter format for medium-capability models."""
        lines = ["# Tools\n"]
        lines.append("Available tools (use function calling):\n")

        for tool in tools:
            if "function" in tool:
                tool_data = tool["function"]
            else:
                tool_data = tool

            name = tool_data.get("name", "unknown")
            description = tool_data.get("description", "")
            # Truncate long descriptions
            if len(description) > 100:
                description = description[:97] + "..."

            params = tool_data.get("parameters", {})
            required = params.get("required", [])
            param_str = ", ".join(required[:3])  # Show first 3 required params
            if len(required) > 3:
                param_str += ", ..."

            lines.append(f"- **{name}**({param_str}): {description}")

        return "\n".join(lines)

    def _format_explicit(self, tools: List[Dict[str, Any]]) -> str:
        """Very explicit format with step-by-step for smaller models."""
        sections = ["# TOOLS - READ CAREFULLY\n"]
        sections.append(
            """To use a tool, you MUST format your response with a function call.

When you want to use a tool:
1. Choose the appropriate tool from the list below
2. Provide all REQUIRED parameters
3. The system will execute the tool and return results

"""
        )

        for tool in tools:
            if "function" in tool:
                tool_data = tool["function"]
            else:
                tool_data = tool

            name = tool_data.get("name", "unknown")
            description = tool_data.get("description", "")
            params = tool_data.get("parameters", {})
            required = params.get("required", [])
            properties = params.get("properties", {})

            sections.append(f"## {name}")
            sections.append(f"WHAT IT DOES: {description}")
            sections.append(f"REQUIRED PARAMETERS: {', '.join(required) if required else 'None'}")

            # Show parameter details
            if properties:
                sections.append("PARAMETERS:")
                for param_name, param_info in list(properties.items())[:5]:  # Limit to 5
                    param_type = param_info.get("type", "any")
                    param_desc = param_info.get("description", "")[:50]
                    required_marker = "*" if param_name in required else ""
                    sections.append(
                        f"  - {param_name}{required_marker} ({param_type}): {param_desc}"
                    )

            # Show example
            example = self._generate_example(tool_data)
            sections.append(f"EXAMPLE:\n{name}({example})")
            sections.append("")

        return "\n".join(sections)

    def _format_parameters(self, params: Dict[str, Any]) -> str:
        """Format parameter documentation."""
        properties = params.get("properties", {})
        required = params.get("required", [])

        if not properties:
            return "  None"

        lines = []
        for name, info in properties.items():
            param_type = info.get("type", "any")
            description = info.get("description", "")
            required_marker = " (required)" if name in required else " (optional)"
            lines.append(f"  - `{name}` ({param_type}){required_marker}: {description}")

        return "\n".join(lines)

    def _generate_example(self, tool_data: Dict[str, Any]) -> str:
        """Generate an example call for a tool."""
        params = tool_data.get("parameters", {})
        properties = params.get("properties", {})
        required = params.get("required", [])

        example = {}
        # If no required, try to use first few properties
        names_to_use = required[:3] if required else list(properties.keys())[:2]

        for name in names_to_use:
            if name in properties:
                param_type = properties[name].get("type", "string")
                if param_type == "string":
                    if "path" in name.lower() or "file" in name.lower():
                        example[name] = "/path/to/file"
                    elif "pattern" in name.lower():
                        example[name] = "*.py"
                    elif "query" in name.lower():
                        example[name] = "search query"
                    else:
                        example[name] = f"<{name}>"
                elif param_type == "boolean":
                    example[name] = True
                elif param_type == "integer" or param_type == "number":
                    example[name] = 1
                elif param_type == "array":
                    example[name] = []
                elif param_type == "object":
                    example[name] = {}

        return json.dumps(example, indent=2)


# =============================================================================
# Prompt Builder
# =============================================================================


class PromptBuilder:
    """
    Builds prompts adapted to model capabilities.

    Uses model profiles to determine:
    - How verbose the prompt should be
    - How many tools to include
    - What format to use for tool documentation
    - Whether to include examples
    """

    def __init__(self, model_name: str, project_dir: Optional[Path] = None):
        """
        Initialize prompt builder.

        Args:
            model_name: Name of the model to build prompts for
            project_dir: Project directory for context
        """
        self.model_name = model_name
        self.project_dir = project_dir or Path(".")
        self.profile = get_model_profile(model_name)
        self.tool_formatter = ToolFormatter(self.profile)

        # Date and knowledge cutoff (MiMo and similar models need this)
        self.knowledge_cutoff = "December 2024"
        self.current_date = datetime.now().strftime("%B %d, %Y")

        logger.debug(
            f"PromptBuilder initialized for {model_name} with style {self.profile.prompt_style}"
        )

    def build_system_prompt(
        self,
        tools: List[Dict[str, Any]],
        enable_planning: bool = False,
        enable_memory: bool = False,
        state_context: Optional[str] = None,
        project_context: Optional[str] = None,
        memory_bank_context: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        permission_mode: str = "NORMAL",
    ) -> str:
        """
        Build complete system prompt adapted to model.

        Args:
            tools: List of available tool definitions
            enable_planning: Include full planning engine guidance
            enable_memory: Include layered memory guidance
            state_context: Current state context to inject
            project_context: Project-specific context (from AGENT.md etc.)
            memory_bank_context: Memory bank summary
            custom_instructions: Additional custom instructions
            permission_mode: Permission mode string

        Returns:
            Complete system prompt string
        """
        sections = []

        # 1. Core identity and instructions
        sections.append(self._build_core_section(permission_mode))

        # 2. Output schema (for models that support JSON mode)
        if self.profile.supports_json_mode:
            schema_section = self._build_output_schema_section()
            if schema_section:
                sections.append(schema_section)

        # 3. Mental Model & Capabilities (The "Phase" approach)
        sections.append(self._build_mental_model_section())

        # 4. Tool documentation (adapted to model)
        if tools:
            tool_section = self.tool_formatter.format_tools(tools)
            sections.append(tool_section)
            # Add tool usage guide
            sections.append(self._build_tool_guide())

        # 5. Planning & Task Management
        # Scaling: uses todo_write for simple, create_plan for complex
        sections.append(self._build_planning_section(enable_planning))

        # 6. Memory & State context
        if enable_memory or memory_bank_context:
            sections.append(self._build_memory_section(memory_bank_context))

        if state_context:
            sections.append(f"# Current State\n\n{state_context}")

        # 7. Project context (if available)
        if project_context:
            sections.append(f"# Project Context\n\n{project_context}")

        # 8. Custom instructions (if provided)
        if custom_instructions:
            sections.append(f"# Additional Instructions\n\n{custom_instructions}")

        # 9. Model-specific adaptations
        adaptation = self._build_model_adaptation()
        if adaptation:
            sections.append(adaptation)

        return "\n\n---\n\n".join(sections)

    def _build_core_section(self, permission_mode: str) -> str:
        """Build core identity and behavior section."""
        mode_instruction = {
            "NORMAL": "Ask for user approval before making changes.",
            "AUTO_APPROVE": "You can make changes without asking. Be careful!",
            "PLAN": "You are in PLAN MODE - read-only. Do not write files or execute commands. Only analyze and create plans.",
        }.get(permission_mode.upper(), "Follow safety protocols.")

        if self.profile.prompt_style == PromptStyle.EXPLICIT:
            return f"""# CORTEX AI ASSISTANT

You are Cortex, an AI assistant that helps with software development tasks.
Project root: {self.project_dir}

Permission Mode: {permission_mode.upper()}
{mode_instruction}

IMPORTANT RULES:
1. Use the tools provided to accomplish tasks
2. Read files before editing them
3. Be precise and follow instructions exactly
4. If unsure, ask for clarification"""

        elif self.profile.prompt_style == PromptStyle.CONCISE:
            return f"""# Cortex AI Assistant

You are Cortex, an AI coding assistant with access to file and system tools.
Working in: {self.project_dir}

Permission Mode: {permission_mode.upper()}
{mode_instruction}

Key behaviors:
- Use tools to read, write, and edit files
- Search before assuming file locations
- Be concise and efficient
- Ask if requirements are unclear"""

        else:  # DETAILED
            core_prompt = f"""# Cortex AI Assistant

You are Cortex, a highly capable AI assistant specialized in software development and coding tasks. You have access to a comprehensive set of tools for file operations, code search, command execution, and more.
Project directory: {self.project_dir}

Permission Mode: {permission_mode.upper()}
{mode_instruction}

## Core Principles

1. **Read Before Edit**: Always read files before making changes to understand context
2. **Search Before Assume**: Use search tools to find code rather than guessing locations
3. **Verify Changes**: After edits, verify the changes are correct
4. **Be Precise**: Make targeted changes rather than rewriting entire files
5. **Communicate Clearly**: Explain what you're doing and why

## Approach to Tasks

1. Understand the request fully before starting
2. Gather necessary context (read files, search codebase)
3. Plan your approach for complex tasks
4. Execute changes incrementally
5. Verify results and handle errors gracefully"""

            # Add date/cutoff for models that need it (MiMo and similar)
            if self.profile.exposes_thinking or "mimo" in self.model_name.lower():
                date_section = f"""

## Date & Knowledge

Today's date: {self.current_date}
Knowledge cutoff: {self.knowledge_cutoff}

For events after the cutoff, use reasoning based on prior patterns. When uncertain, state it clearly."""

                core_prompt += date_section

            return core_prompt

    def _build_mental_model_section(self) -> str:
        """Build mental model for codebase understanding section."""
        if self.profile.prompt_style == PromptStyle.EXPLICIT:
            return """# HOW TO EXPLORE CODE

1. Use `glob` to find all files
2. Use `grep` to find where classes or functions are
3. Read ONLY the files you need to change
4. Do not guess file paths"""

        return """# Mental Model for Codebase Understanding

When exploring a new codebase, build understanding systematically:

## Phase 1: Structure Discovery
Use `glob(pattern="**/*.py")` (or similar) to map all source files. Identify entry points, core packages, and test locations.

## Phase 2: Architecture Understanding
Use `grep` to find top-level class and function definitions. Build a mental map of how data flows from entry points to utilities.

## Phase 3: Targeted Deep Dives
Only read files when you have a specific reason. Track what you've read to avoid re-reading. Use `files_with_matches` mode in grep for breadth first."""

    def _build_tool_guide(self) -> str:
        """Build tool usage guide section."""
        if self.profile.prompt_style == PromptStyle.EXPLICIT:
            return """# TOOL USAGE GUIDE

| Need to... | Use this tool |
|------------|---------------|
| Read a file | `read_file` |
| Edit a file | `edit` (read first!) |
| Create new file | `write_file` |
| Find files | `glob` |
| Search code | `grep` |
| Run command | `execute_command` |

## IMPORTANT
- ALWAYS read a file before editing it
- Use search tools to find code, don't guess paths"""

        elif self.profile.prompt_style == PromptStyle.CONCISE:
            return """# Tool Quick Reference

| Task | Tool | Notes |
|------|------|-------|
| Read file | `read_file` | Always before editing |
| Edit file | `edit` | Requires unique match |
| Search | `grep` | Regex supported |
| Find files | `glob` | Use patterns |
| Commands | `execute_command` | System operations |

Tips: Read before edit. Search before assuming paths."""

        else:  # DETAILED
            return """# Tool Usage Guide

## Quick Reference - Which Tool for What

| Task | Tool | When to Use |
|------|------|-------------|
| Read a file | `read_file` | Always before editing; to understand code |
| Edit a file | `edit` | Make targeted changes to existing files |
| Create file | `write_file` | Create new files only |
| Search code | `grep` | Find patterns, functions, classes |
| Find files | `glob` | Locate files by name patterns |
| Run command | `execute_command` | Execute system commands, tests |
| Create plan | `create_plan` | For complex multi-step tasks (4+ steps) |
| Find symbols | `ast_search` | Structural code search by definition |
| Extract code | `ast_extract` | Get functions/classes with metadata |

## Decision Tree

```
Need to understand code?
├── Know the file? → read_file
├── Know the pattern? → grep
└── Need definitions? → ast_search or ast_extract

Need to modify code?
├── Small change? → edit
└── Multiple files? → create_plan first
```

## grep vs ast_search
- **grep**: Text patterns, strings, comments, regex matching
- **ast_search**: Function/class/import definitions by structure

## Common Mistakes to Avoid
- **DON'T** edit a file you haven't read
- **DON'T** guess file paths - use search
- **DO** verify changes after edits"""

    def _build_planning_section(self, enable_planning: bool) -> str:
        """Build planning system guidance section, scaling based on capability."""
        if not enable_planning:
            # Fallback to simple todo_write guidance
            return """# Task Management (todo_write)

For multi-step tasks (3+ steps), use `todo_write` to track progress:
- Track status: pending → in_progress → completed
- Only ONE task can be in_progress at a time
- Mark tasks completed IMMEDIATELY after finishing

Example:
```python
todo_write(todos=[
    {"content": "Read auth files", "status": "completed", "activeForm": "Reading auth files"},
    {"content": "Implement feature", "status": "in_progress", "activeForm": "Implementing feature"}
])
```"""

        # Full planning engine enabled
        if self.profile.prompt_style == PromptStyle.EXPLICIT:
            return """# PLANNING TOOLS

For complex tasks, use planning tools:
1. `create_plan` - Make a plan
2. `execute_plan` - Run the plan
3. `monitor_plan` - Check progress

USE PLANNING when task is complex (4+ steps). SKIP for simple tasks."""

        elif self.profile.prompt_style == PromptStyle.CONCISE:
            return """# Planning Tools

For complex tasks (4+ steps, multiple files):
- `create_plan(goal, constraints)` - Create structured plan
- `execute_plan(plan_id)` - Execute plan steps
- `monitor_plan(plan_id)` - Check progress

Skip planning for simple, single-step tasks."""

        else:  # DETAILED
            return """# Planning System

You have access to planning tools for managing complex, multi-step tasks systematically.

## When to Use Planning

**USE planning when:**
- Task involves 4+ sequential steps
- Multiple files need coordinated changes
- Task has dependencies between steps

**Planning Tools:**
- `create_plan`: Create a structured plan with goals and constraints.
- `execute_plan`: Execute steps one by one.
- `monitor_plan`: Check progress and status.
- `update_plan`: Modify plan if approach needs adjustment.

**Note on todo_write:** Use `todo_write` for simple tracking of 2-3 steps. For everything else, use `create_plan`."""

    def _build_memory_section(self, memory_bank_context: Optional[str]) -> str:
        """Build memory system guidance section."""
        section = "# Memory System\n\n"
        if memory_bank_context:
            section += f"## Session Memory\n\n{memory_bank_context}\n\n"

        if self.profile.prompt_style in (PromptStyle.EXPLICIT, PromptStyle.CONCISE):
            section += "The system tracks files read and decisions made automatically."
        else:  # DETAILED
            section += """You have a layered memory system:
- **Working Memory**: Current files, recently identified symbols.
- **Session Memory**: Successful patterns, failed approaches, key decisions.

Use this to avoid repeating mistakes and reuse proven patterns."""

        return section

    def _build_output_schema_section(self) -> str:
        """Add JSON schema enforcement for models that support it."""
        return """## Output Format

ALL responses MUST be valid JSON matching this schema:

```json
{
  "mode": "plan" | "run_command" | "edit_file" | "answer" | "reasoning",
  "reasoning": "brief chain-of-thought (< 150 words)",
  "commands": [
    {
      "cmd": "shell command",
      "cwd": "working directory",
      "explanation": "why this is needed"
    }
  ],
  "edits": [
    {
      "file": "relative/path/to/file",
      "action": "create" | "modify" | "delete",
      "content": "file content or patch"
    }
  ],
  "answer": "natural language response"
}
```

**Security Constraints**:
- NEVER run destructive commands without explicit approval.
- ALWAYS validate file paths.
- Always output valid JSON.
"""

    def _build_model_adaptation(self) -> str:
        """Build model-specific adaptation notes."""
        notes = []

        # Add model name header for MiMo models
        if self.model_name.startswith("mimo"):
            notes.append("## MiMo Model Notes")
            notes.append("")

        # Add notes based on capability levels
        if self.profile.tool_following == CapabilityLevel.MODERATE:
            notes.append("Focus on using one tool at a time and verify results before proceeding.")

        if self.profile.tool_following == CapabilityLevel.LIMITED:
            notes.append("Use tools carefully. Follow the exact format shown in examples.")

        if self.profile.reasoning == CapabilityLevel.MODERATE:
            notes.append("Break complex problems into smaller steps.")

        if self.profile.reasoning == CapabilityLevel.EXCELLENT:
            notes.append("Think through problems explicitly and step by step before acting.")

        if not self.profile.supports_json_mode:
            notes.append("Format tool arguments carefully as JSON objects.")

        if notes:
            header = (
                "## Model-Specific Notes\n\n"
                if self.profile.prompt_style == PromptStyle.DETAILED
                else "## Notes\n\n"
            )
            if self.model_name.startswith("mimo"):
                # Remove the header since we added MiMo-specific header
                notes_to_join = notes
                return "\n".join(notes_to_join)
            return header + "\n".join(f"- {note}" for note in notes)

        return ""

    def get_profile_summary(self) -> Dict[str, Any]:
        """Get a summary of the model profile being used."""
        return {
            "model": self.model_name,
            "profile": self.profile.name,
            "prompt_style": self.profile.prompt_style.value,
            "context_window": self.profile.context_window,
            "max_tools": self.profile.max_tools_per_prompt,
            "tool_following": self.profile.tool_following.value,
            "reasoning": self.profile.reasoning.value,
        }
