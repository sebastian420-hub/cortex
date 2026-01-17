"""Model-specific prompt adapters.

This module provides specialized prompt adaptations for different model families
to maximize their effectiveness with Cortex.
"""

import logging
from typing import Dict, Any, Optional, List

from ..model_capabilities import (
    get_model_profile,
    ModelProfile,
    PromptStyle,
    CapabilityLevel,
)

logger = logging.getLogger(__name__)


class BaseAdapter:
    """Base class for model adapters."""

    name: str = "base"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        """Check if this adapter applies to the given model."""
        return False

    @classmethod
    def get_tool_format_hint(cls) -> str:
        """Get tool formatting hints for this model family."""
        return ""

    @classmethod
    def get_response_format_hint(cls) -> str:
        """Get response formatting hints for this model family."""
        return ""

    @classmethod
    def get_special_instructions(cls) -> str:
        """Get any special instructions for this model family."""
        return ""

    @classmethod
    def adapt_prompt(cls, prompt: str, profile: ModelProfile) -> str:
        """Apply model-specific adaptations to a prompt."""
        adaptations = []

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
    """Adapter for Anthropic Claude models."""

    name = "claude"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        model_lower = model_name.lower()
        return "claude" in model_lower or "anthropic" in model_lower

    @classmethod
    def get_tool_format_hint(cls) -> str:
        # Claude has excellent tool following, minimal hints needed
        return ""

    @classmethod
    def get_response_format_hint(cls) -> str:
        return """## Response Guidelines (Claude)

- Use your full reasoning capabilities for complex tasks
- Leverage your large context window effectively
- Be thorough but avoid unnecessary verbosity
- When using tools, explain your reasoning briefly"""

    @classmethod
    def get_special_instructions(cls) -> str:
        return """## Claude-Specific Capabilities

- You excel at code analysis and generation
- Use your understanding of context to make informed decisions
- You can handle multiple tool calls efficiently
- For complex tasks, feel free to think through the problem systematically"""


class GPTAdapter(BaseAdapter):
    """Adapter for OpenAI GPT models."""

    name = "gpt"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        model_lower = model_name.lower()
        return "gpt" in model_lower or "openai" in model_lower

    @classmethod
    def get_tool_format_hint(cls) -> str:
        return ""  # GPT has excellent native function calling

    @classmethod
    def get_response_format_hint(cls) -> str:
        return """## Response Guidelines (GPT)

- Be concise and direct in your responses
- Use function calling for all tool operations
- Provide clear explanations when making changes
- Handle errors gracefully with informative messages"""

    @classmethod
    def get_special_instructions(cls) -> str:
        return ""


class DeepSeekAdapter(BaseAdapter):
    """Adapter for DeepSeek models."""

    name = "deepseek"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        return "deepseek" in model_name.lower()

    @classmethod
    def get_tool_format_hint(cls) -> str:
        return ""

    @classmethod
    def get_response_format_hint(cls) -> str:
        return """## Response Guidelines (DeepSeek)

- Use <thinking> tags for complex reasoning when helpful
- Leverage your strong code understanding capabilities
- Be systematic in your approach to problems"""

    @classmethod
    def get_special_instructions(cls) -> str:
        return """## DeepSeek Capabilities

- You have strong reasoning abilities - use them for complex problems
- Your code generation is highly capable
- When facing complex tasks, break them down systematically"""


class OllamaAdapter(BaseAdapter):
    """Adapter for local Ollama models (Llama, Mistral, etc.)."""

    name = "ollama"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        model_lower = model_name.lower()
        # Match common Ollama models
        ollama_models = [
            "llama", "mistral", "mixtral", "codellama", "phi",
            "gemma", "qwen", "starcoder", "codestral", "devstral",
            "deepseek", "command-r", "neural-chat", "vicuna"
        ]
        # Also check for ollama/ prefix
        if model_lower.startswith("ollama/"):
            return True
        return any(m in model_lower for m in ollama_models)

    @classmethod
    def get_tool_format_hint(cls) -> str:
        return """## Tool Usage (Local Model)

When calling tools:
1. Use the function calling format provided
2. Ensure all required parameters are included
3. Wait for tool results before continuing
4. If a tool fails, try an alternative approach"""

    @classmethod
    def get_response_format_hint(cls) -> str:
        return """## Response Guidelines (Local Model)

- Focus on one task at a time
- Verify your actions before proceeding
- If uncertain, ask for clarification
- Keep responses focused and relevant"""

    @classmethod
    def get_special_instructions(cls) -> str:
        return """## Working Effectively

- Break complex tasks into simple steps
- Use search tools to find information before making assumptions
- Verify file contents before editing
- Test changes when possible"""


class MistralAdapter(BaseAdapter):
    """Adapter specifically for Mistral models."""

    name = "mistral"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        model_lower = model_name.lower()
        return "mistral" in model_lower or "mixtral" in model_lower

    @classmethod
    def get_tool_format_hint(cls) -> str:
        return """## Tool Format (Mistral)

When using tools, format function calls carefully:
- Include all required parameters
- Use proper JSON formatting for arguments
- Handle tool results before making additional calls"""

    @classmethod
    def get_response_format_hint(cls) -> str:
        return """## Response Format (Mistral)

- Be direct and efficient in responses
- Explain your reasoning briefly
- Use tools systematically"""

    @classmethod
    def get_special_instructions(cls) -> str:
        return ""


class CodeSpecializedAdapter(BaseAdapter):
    """Adapter for code-specialized models."""

    name = "code"

    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        model_lower = model_name.lower()
        code_models = ["codellama", "codestral", "starcoder", "coder", "codex"]
        return any(m in model_lower for m in code_models)

    @classmethod
    def get_tool_format_hint(cls) -> str:
        return ""

    @classmethod
    def get_response_format_hint(cls) -> str:
        return """## Code Task Guidelines

- Focus on clean, working code
- Follow existing patterns in the codebase
- Add minimal necessary comments
- Test your changes when possible"""

    @classmethod
    def get_special_instructions(cls) -> str:
        return """## Code-Specific Approach

You are optimized for code tasks:
1. Read relevant files before making changes
2. Understand the codebase patterns
3. Make targeted, surgical edits
4. Verify syntax and logic"""


# Registry of all adapters (order matters - more specific first)
ADAPTERS: List[type] = [
    ClaudeAdapter,
    GPTAdapter,
    DeepSeekAdapter,
    MistralAdapter,
    CodeSpecializedAdapter,
    OllamaAdapter,  # Catch-all for local models
]


def get_adapter(model_name: str) -> Optional[type]:
    """
    Get the appropriate adapter for a model.

    Args:
        model_name: Name of the model

    Returns:
        Adapter class or None if no specific adapter applies
    """
    for adapter in ADAPTERS:
        if adapter.applies_to(model_name):
            logger.debug(f"Using {adapter.name} adapter for model {model_name}")
            return adapter
    return None


def adapt_prompt_for_model(prompt: str, model_name: str) -> str:
    """
    Apply model-specific adaptations to a prompt.

    Args:
        prompt: Base prompt to adapt
        model_name: Name of the model

    Returns:
        Adapted prompt
    """
    profile = get_model_profile(model_name)
    adapter = get_adapter(model_name)

    if adapter:
        return adapter.adapt_prompt(prompt, profile)
    return prompt


def get_adapter_info(model_name: str) -> Dict[str, Any]:
    """
    Get information about the adapter being used for a model.

    Args:
        model_name: Name of the model

    Returns:
        Dict with adapter information
    """
    adapter = get_adapter(model_name)
    profile = get_model_profile(model_name)

    return {
        "model": model_name,
        "adapter": adapter.name if adapter else "none",
        "profile": profile.name,
        "prompt_style": profile.prompt_style.value,
        "tool_following": profile.tool_following.value,
        "reasoning": profile.reasoning.value,
    }
