"""Prompt adapters for model-specific prompt adaptations."""

from typing import Optional, Dict, Any
from cortex.core.model_capabilities import get_model_profile, PromptStyle, CapabilityLevel


class BaseAdapter:
    """Base class for model-specific prompt adaptations."""

    name: str = "base"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        """Check if this adapter applies to the given model."""
        raise NotImplementedError

    @classmethod
    def get_tool_format_hint(cls) -> str:
        """Get tool formatting hints for this model."""
        return ""

    @classmethod
    def get_response_format_hint(cls) -> str:
        """Get response format hints for this model."""
        return ""

    @classmethod
    def get_special_instructions(cls) -> str:
        """Get special instructions for this model."""
        return ""

    @classmethod
    def adapt_prompt(cls, prompt: str, profile) -> str:
        """Adapt the prompt for this model."""
        adaptations = []

        # Add tool format hint for MiMo
        if cls.name == "mimo":
            tool_hint = cls.get_tool_format_hint()
            if tool_hint:
                adaptations.append(tool_hint)

        response_hint = cls.get_response_format_hint()
        if response_hint:
            adaptations.append(response_hint)

        special = cls.get_special_instructions()
        if special:
            adaptations.append(special)

        if adaptations:
            return prompt + "\n\n" + "\n\n".join(adaptations)

        return prompt


class ClaudeAdapter(BaseAdapter):
    """Adapter for Claude models."""

    name = "claude"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        return "claude" in model_name.lower()

    @classmethod
    def get_special_instructions(cls) -> str:
        return """## Claude-Specific Guidelines

- Use detailed chain-of-thought for complex reasoning
- Leverage large context window (200K tokens)
- Tool use is excellent - format carefully
- Be explicit about dependencies and file paths
"""


class GPTAdapter(BaseAdapter):
    """Adapter for GPT models."""

    name = "gpt"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        return model_name.lower().startswith("gpt")

    @classmethod
    def get_special_instructions(cls) -> str:
        return """## GPT-Specific Guidelines

- Keep responses concise and direct
- Tool use is excellent - follow JSON schemas precisely
- Use function calling when available
- Be explicit about tool parameters
"""


class DeepSeekAdapter(BaseAdapter):
    """Adapter for DeepSeek models."""

    name = "deepseek"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        return "deepseek" in model_name.lower()

    @classmethod
    def get_special_instructions(cls) -> str:
        return """## DeepSeek-Specific Guidelines

- Use thinking tags (<thinking>...</thinking>) for complex reasoning
- Strong coding capabilities - leverage for code tasks
- Good tool following - be explicit about constraints
- Reasoning mode available for complex problems
"""


class MiMoAdapter(BaseAdapter):
    """Adapter for Xiaomi MiMo-V2-Flash model."""

    name = "mimo"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        model_lower = model_name.lower()
        return "mimo" in model_lower

    @classmethod
    def get_tool_format_hint(cls) -> str:
        return """## Tool Format (MiMo)

ALL tool calls MUST be valid JSON with this structure:
{
  "mode": "plan" | "run_command" | "edit_file" | "answer" | "reasoning",
  "reasoning": "your chain-of-thought (< 150 words)",
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

**Mode semantics**:
- `plan`: Multi-step; return commands/edits without executing; ask for approval
- `run_command`: Execute immediately (safety checks pass)
- `edit_file`: Modify single file; await approval unless auto-approved
- `answer`: Return only natural language
- `reasoning`: Thinking-heavy; return chain-of-thought

**Security Constraints**:
- NEVER run destructive commands without explicit approval (rm -rf, > /dev/null, network changes)
- ALWAYS validate file paths; reject attempts to write outside allowed directories
- ALWAYS explain your reasoning in < 150 words
- Always output valid JSON; never output raw shell or code without the schema wrapper
"""

    @classmethod
    def get_response_format_hint(cls) -> str:
        return """## Response Guidelines (MiMo)

- Be explicit, never implicit - restate constraints when in doubt
- Keep reasoning sections under 150 words
- Use step-by-step planning for complex tasks
- Validate file paths and command syntax before proposing
- Reference line numbers and prior errors explicitly
"""

    @classmethod
    def get_special_instructions(cls) -> str:
        return """## MiMo-Specific Capabilities

- Use enhanced reasoning capabilities for complex problems
- For routine tasks, respond directly without over-explaining
- Knowledge cutoff: December 2024 - state when uncertain about recent changes
- SWA architecture: Keep most relevant content in accessible windows
- Multi-turn stability: Restate constraints every 3-4 turns
"""


class MistralAdapter(BaseAdapter):
    """Adapter for Mistral models."""

    name = "mistral"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        return "mistral" in model_name.lower()

    @classmethod
    def get_special_instructions(cls) -> str:
        return """## Mistral-Specific Guidelines

- Use explicit step-by-step instructions
- Format tools clearly with examples
- Keep responses structured and organized
- Tool following is moderate - provide clear guidance
"""


class CodeSpecializedAdapter(BaseAdapter):
    """Adapter for code-specialized models."""

    name = "code"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        model_lower = model_name.lower()
        return any(keyword in model_lower for keyword in ["coder", "codestral", "code"])

    @classmethod
    def get_special_instructions(cls) -> str:
        return """## Code-Specialized Model Guidelines

- Focus on code accuracy and precision
- Use clear variable names and comments
- Provide complete file contents when editing
- Validate syntax and dependencies before proposing
"""


class OllamaAdapter(BaseAdapter):
    """Adapter for Ollama/local models."""

    name = "ollama"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        return "ollama" in model_name.lower() or "/" in model_name

    @classmethod
    def get_special_instructions(cls) -> str:
        return """## Ollama/Local Model Guidelines

- Local models may have smaller context windows
- Use explicit instructions and examples
- Break complex tasks into smaller steps
- Be patient with smaller models (7B-13B)
"""


# Registry of all adapters (order matters - first match wins)
ADAPTERS = [
    ClaudeAdapter,
    GPTAdapter,
    DeepSeekAdapter,
    MiMoAdapter,  # NEW: MiMo support
    MistralAdapter,
    CodeSpecializedAdapter,
    OllamaAdapter,
]


def get_adapter(model_name: str) -> Optional[BaseAdapter]:
    """Get the appropriate adapter for a model."""
    for adapter in ADAPTERS:
        if adapter.applies_to(model_name):
            return adapter
    return None


def adapt_prompt_for_model(prompt: str, model_name: str) -> str:
    """Adapt a prompt for a specific model."""
    adapter = get_adapter(model_name)
    if adapter:
        profile = get_model_profile(model_name)
        return adapter.adapt_prompt(prompt, profile)
    return prompt


def get_adapter_info(model_name: str) -> Optional[Dict[str, Any]]:
    """Get adapter information for a model."""
    adapter = get_adapter(model_name)
    if adapter:
        profile = get_model_profile(model_name)
        return {
            "model": model_name,
            "adapter": adapter.name,
            "profile": profile.name,
            "prompt_style": profile.prompt_style.value,
            "tool_following": profile.tool_following.value,
            "reasoning": profile.reasoning.value,
        }
    return None
