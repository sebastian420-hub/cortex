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
            "read_file", "write_file", "edit_file",
            # Search operations
            "grep_search", "glob_files", "find_files",
            # Execution
            "bash", "run_command",
            # Planning
            "create_plan", "execute_plan", "monitor_plan", "update_plan",
            # Web
            "web_search", "web_fetch",
            # Memory
            "memory_store", "memory_recall",
        ]

        def get_priority(tool: Dict[str, Any]) -> int:
            name = tool.get("name", "").lower()
            try:
                return priority_order.index(name)
            except ValueError:
                return len(priority_order)  # Unknown tools go last

        sorted_tools = sorted(tools, key=get_priority)
        return sorted_tools[:self.profile.max_tools_per_prompt]

    def _format_detailed(self, tools: List[Dict[str, Any]]) -> str:
        """Full documentation with examples for capable models."""
        sections = ["# Available Tools\n"]
        sections.append("You have access to the following tools. Use them to accomplish tasks.\n")

        for tool in tools:
            name = tool.get("name", "unknown")
            description = tool.get("description", "No description")
            parameters = tool.get("parameters", {})

            sections.append(f"## {name}\n")
            sections.append(f"{description}\n")

            # Format parameters
            if parameters:
                sections.append("**Parameters:**")
                params_info = self._format_parameters(parameters)
                sections.append(params_info)

            # Generate example
            example = self._generate_example(tool)
            sections.append(f"\n**Example:**\n```json\n{example}\n```\n")

        return "\n".join(sections)

    def _format_concise(self, tools: List[Dict[str, Any]]) -> str:
        """Shorter format for medium-capability models."""
        lines = ["# Tools\n"]
        lines.append("Available tools (use function calling):\n")

        for tool in tools:
            name = tool.get("name", "unknown")
            description = tool.get("description", "")
            # Truncate long descriptions
            if len(description) > 100:
                description = description[:97] + "..."

            params = tool.get("parameters", {})
            required = params.get("required", [])
            param_str = ", ".join(required[:3])  # Show first 3 required params
            if len(required) > 3:
                param_str += ", ..."

            lines.append(f"- **{name}**({param_str}): {description}")

        return "\n".join(lines)

    def _format_explicit(self, tools: List[Dict[str, Any]]) -> str:
        """Very explicit format with step-by-step for smaller models."""
        sections = ["# TOOLS - READ CAREFULLY\n"]
        sections.append("""To use a tool, you MUST format your response with a function call.

When you want to use a tool:
1. Choose the appropriate tool from the list below
2. Provide all REQUIRED parameters
3. The system will execute the tool and return results

""")

        for tool in tools:
            name = tool.get("name", "unknown")
            description = tool.get("description", "")
            params = tool.get("parameters", {})
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
                    sections.append(f"  - {param_name}{required_marker} ({param_type}): {param_desc}")

            # Show example
            example = self._generate_example(tool)
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

    def _generate_example(self, tool: Dict[str, Any]) -> str:
        """Generate an example call for a tool."""
        params = tool.get("parameters", {})
        properties = params.get("properties", {})
        required = params.get("required", [])

        example = {}
        for name in required[:3]:  # Show up to 3 required params
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

        logger.debug(f"PromptBuilder initialized for {model_name} with style {self.profile.prompt_style}")

    def build_system_prompt(
        self,
        tools: List[Dict[str, Any]],
        enable_planning: bool = False,
        enable_memory: bool = False,
        state_context: Optional[str] = None,
        project_context: Optional[str] = None,
        custom_instructions: Optional[str] = None,
    ) -> str:
        """
        Build complete system prompt adapted to model.

        Args:
            tools: List of available tool definitions
            enable_planning: Include planning system guidance
            enable_memory: Include memory system guidance
            state_context: Current state context to inject
            project_context: Project-specific context (from AGENT.md etc.)
            custom_instructions: Additional custom instructions

        Returns:
            Complete system prompt string
        """
        sections = []

        # 1. Core identity and instructions
        sections.append(self._build_core_section())

        # 2. Output schema (for models that support JSON mode)
        if self.profile.supports_json_mode:
            schema_section = self._build_output_schema_section()
            if schema_section:
                sections.append(schema_section)

        # 3. Tool documentation (adapted to model)
        if tools:
            tool_section = self.tool_formatter.format_tools(tools)
            sections.append(tool_section)
            # Add tool usage guide
            sections.append(self._build_tool_guide())

        # 4. Planning guidance (if enabled)
        if enable_planning:
            sections.append(self._build_planning_section())

        # 5. Memory guidance (if enabled)
        if enable_memory:
            sections.append(self._build_memory_section())

        # 6. State context (if available)
        if state_context:
            sections.append(f"## Current State\n\n{state_context}")

        # 7. Project context (if available)
        if project_context:
            sections.append(f"## Project Context\n\n{project_context}")

        # 8. Custom instructions (if provided)
        if custom_instructions:
            sections.append(f"## Additional Instructions\n\n{custom_instructions}")

        # 9. Model-specific adaptations
        adaptation = self._build_model_adaptation()
        if adaptation:
            sections.append(adaptation)

        return "\n\n---\n\n".join(sections)

    def _build_core_section(self) -> str:
        """Build core identity and behavior section."""
        if self.profile.prompt_style == PromptStyle.EXPLICIT:
            return """# CORTEX AI ASSISTANT

You are Cortex, an AI assistant that helps with software development tasks.

IMPORTANT RULES:
1. Use the tools provided to accomplish tasks
2. Read files before editing them
3. Be precise and follow instructions exactly
4. If unsure, ask for clarification

Your job is to help the user with their coding tasks efficiently."""

        elif self.profile.prompt_style == PromptStyle.CONCISE:
            return """# Cortex AI Assistant

You are Cortex, an AI coding assistant with access to file and system tools.

Key behaviors:
- Use tools to read, write, and edit files
- Search before assuming file locations
- Be concise and efficient
- Ask if requirements are unclear"""

        else:  # DETAILED
            core_prompt = """# Cortex AI Assistant

You are Cortex, a highly capable AI assistant specialized in software development and coding tasks. You have access to a comprehensive set of tools for file operations, code search, command execution, and more.

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

    def _build_tool_guide(self) -> str:
        """Build tool usage guide section."""
        if self.profile.prompt_style == PromptStyle.EXPLICIT:
            return """# TOOL USAGE GUIDE

## Which Tool to Use

| Need to... | Use this tool |
|------------|---------------|
| Read a file | `read_file` |
| Edit a file | `edit_file` (read first!) |
| Create new file | `write_file` |
| Find files | `glob_files` |
| Search code | `grep_search` |
| Run command | `bash` |

## IMPORTANT
- ALWAYS read a file before editing it
- Use search tools to find code, don't guess paths
- Check tool results before continuing"""

        elif self.profile.prompt_style == PromptStyle.CONCISE:
            return """# Tool Quick Reference

| Task | Tool | Notes |
|------|------|-------|
| Read file | `read_file` | Always before editing |
| Edit file | `edit_file` | Requires unique match |
| Search | `grep_search` | Regex supported |
| Find files | `glob_files` | Use patterns |
| Commands | `bash` | System operations |

Tips: Read before edit. Search before assuming paths."""

        else:  # DETAILED
            return """# Tool Usage Guide

## Quick Reference - Which Tool for What

| Task | Tool | When to Use |
|------|------|-------------|
| Read a file | `read_file` | Always before editing; to understand code |
| Edit a file | `edit_file` | Make targeted changes to existing files |
| Create file | `write_file` | Create new files only |
| Search code | `grep_search` | Find patterns, functions, classes |
| Find files | `glob_files` | Locate files by name patterns |
| Run command | `bash` | Execute system commands, tests |
| Create plan | `create_plan` | For complex multi-step tasks |
| Execute plan | `execute_plan` | Run through plan steps |
| Find functions/classes | `ast_search` | Structural code search by definition |
| Extract code structure | `ast_extract` | Get functions/classes with metadata |
| Analyze code quality | `ast_analyze` | Complexity metrics, issues, dependencies |

## Decision Tree

```
Need to understand code?
├── Know the file? → read_file
├── Know the pattern? → grep_search
├── Know the extension? → glob_files
└── Need function/class definitions? → ast_search or ast_extract

Need to modify code?
├── Small change? → edit_file
├── New file? → write_file
└── Multiple files? → create_plan first

Need to run something?
├── Tests? → bash command
├── Build? → bash command
└── Other? → bash command

Need code analysis?
├── Find code structure? → ast_search (search_type="function" or "class")
├── Get full definitions? → ast_extract (with docstrings, decorators)
└── Analyze complexity? → ast_analyze
```

## grep vs ast_search
- **grep**: Text patterns, strings, comments, regex matching
- **ast_search**: Function/class/import definitions by structure

## Common Mistakes to Avoid

- **DON'T** edit a file you haven't read
- **DON'T** guess file paths - use search
- **DON'T** make large changes without understanding context
- **DO** verify changes after edits
- **DO** handle errors gracefully"""

    def _build_planning_section(self) -> str:
        """Build planning system guidance section."""
        if self.profile.prompt_style == PromptStyle.EXPLICIT:
            return """# PLANNING TOOLS

For complex tasks with 4+ steps, use planning tools:

1. `create_plan` - Make a plan
   - goal: What to achieve
   - constraints: Any limitations

2. `execute_plan` - Run the plan
   - plan_id: From create_plan

3. `monitor_plan` - Check progress
   - plan_id: The plan to check

USE PLANNING when task is complex. SKIP for simple tasks."""

        elif self.profile.prompt_style == PromptStyle.CONCISE:
            return """# Planning Tools

For complex tasks (4+ steps, multiple files):
- `create_plan(goal, constraints)` - Create structured plan
- `execute_plan(plan_id)` - Execute plan steps
- `monitor_plan(plan_id)` - Check progress

Skip planning for simple, single-step tasks."""

        else:  # DETAILED
            return """# Planning System

You have access to planning tools for managing complex, multi-step tasks.

## When to Use Planning

**USE planning when:**
- Task involves 4+ sequential steps
- Multiple files need coordinated changes
- Task has dependencies between steps
- You need to track progress

**SKIP planning when:**
- Task is simple (1-3 steps)
- Single file change
- Quick lookup or read operation

## Planning Tools

### create_plan
Create a structured plan for achieving a goal.
```
create_plan(
    goal="Description of what to achieve",
    constraints=["Must not break tests", "Use existing patterns"],
    assumptions=["Python 3.10+"]
)
```

### execute_plan
Execute a plan step by step.
```
execute_plan(
    plan_id="plan_xxx",
    max_steps=10,
    stop_on_failure=True
)
```

### monitor_plan
Check plan progress at any time.
```
monitor_plan(plan_id="plan_xxx")
```

### update_plan
Modify a plan if needed.
```
update_plan(
    plan_id="plan_xxx",
    add_steps=[...],
    remove_step_ids=[...]
)
```"""

    def _build_memory_section(self) -> str:
        """Build memory system guidance section."""
        if self.profile.prompt_style in (PromptStyle.EXPLICIT, PromptStyle.CONCISE):
            return """# Memory System

The system tracks:
- Files you've read
- Patterns that worked
- Decisions made

This context is provided automatically to help you."""

        else:  # DETAILED
            return """# Memory System

You have a layered memory system that tracks context across the conversation:

## Working Memory
- Current task and sub-goals
- Recently accessed files
- Active hypotheses and insights

## Session Memory
- Failed approaches (to avoid repeating)
- Successful patterns (to reuse)
- Key decisions made

This context is automatically provided. Use it to:
- Avoid repeating failed approaches
- Reuse patterns that worked
- Stay focused on the current goal"""

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

**Mode semantics**:
- `plan`: Multiple steps needed; return commands + edits without executing yet; ask for approval
- `run_command`: Execute shell command immediately (only if safety checks pass)
- `edit_file`: Modify a single file (propose change, await approval unless auto-approved)
- `answer`: Return only natural language answer in the "answer" field
- `reasoning`: Thinking-heavy response; return chain-of-thought in "reasoning"

**Security Constraints**:
- NEVER run destructive commands without explicit approval (rm -rf, > /dev/null, network changes)
- ALWAYS validate file paths; reject attempts to write outside allowed directories
- ALWAYS explain your reasoning in < 150 words
- Always output valid JSON; never output raw shell or code without the schema wrapper
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
            header = "## Model-Specific Notes\n\n" if self.profile.prompt_style == PromptStyle.DETAILED else "## Notes\n\n"
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
