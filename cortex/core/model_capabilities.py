"""Model capability profiles for prompt optimization.

This module defines capability profiles for different models, enabling
dynamic prompt adaptation based on model strengths and limitations.

Each profile includes:
- context_window: Maximum context length
- tool_following: How well the model follows tool call instructions
- reasoning: Reasoning and planning capability
- prompt_style: Recommended prompt verbosity (detailed/concise/explicit)
- supports_json_mode: Native JSON output support
- max_tools_per_prompt: Recommended maximum tools to include
- supports_streaming: Whether streaming is supported
- supports_vision: Whether the model can process images
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class PromptStyle(str, Enum):
    """Prompt verbosity style based on model capability."""

    DETAILED = "detailed"  # Full documentation, examples, verbose guidance
    CONCISE = "concise"  # Shorter format, key information only
    EXPLICIT = "explicit"  # Very explicit step-by-step, for smaller models


class CapabilityLevel(str, Enum):
    """Capability level for a specific feature."""

    EXCELLENT = "excellent"  # Top-tier capability
    GOOD = "good"  # Reliable capability
    MODERATE = "moderate"  # Works but may need guidance
    LIMITED = "limited"  # Basic support, needs explicit guidance
    NONE = "none"  # Not supported


@dataclass
class ModelProfile:
    """Capability profile for a model."""

    name: str
    context_window: int
    tool_following: CapabilityLevel
    reasoning: CapabilityLevel
    prompt_style: PromptStyle
    supports_json_mode: bool
    max_tools_per_prompt: int
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_function_calling: bool = True
    recommended_temperature: float = 0.7
    notes: str = ""
    exposes_thinking: bool = False  # Whether model exposes thinking process
    thinking_field: Optional[str] = (
        None  # API field name for thinking content (e.g., "reasoning_content", "reasoning")
    )
    recommended_temperatures: Optional[Dict[str, float]] = None  # Temperature for different tasks
    reasoning_budget: Optional[Dict[str, int]] = (
        None  # Thinking token budget for different complexity levels
    )

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "context_window": self.context_window,
            "tool_following": self.tool_following.value,
            "reasoning": self.reasoning.value,
            "prompt_style": self.prompt_style.value,
            "supports_json_mode": self.supports_json_mode,
            "max_tools_per_prompt": self.max_tools_per_prompt,
            "supports_streaming": self.supports_streaming,
            "supports_vision": self.supports_vision,
            "supports_function_calling": self.supports_function_calling,
            "recommended_temperature": self.recommended_temperature,
            "notes": self.notes,
            "exposes_thinking": self.exposes_thinking,
            "thinking_field": self.thinking_field,
        }


# =============================================================================
# Model Profile Registry
# =============================================================================

MODEL_PROFILES: Dict[str, ModelProfile] = {
    # -------------------------------------------------------------------------
    # Anthropic Models (Claude)
    # -------------------------------------------------------------------------
    "claude-3-5-sonnet": ModelProfile(
        name="Claude 3.5 Sonnet",
        context_window=200000,
        tool_following=CapabilityLevel.EXCELLENT,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=64,
        supports_vision=True,
        notes="Best for complex coding tasks, excellent tool use",
    ),
    "claude-3-opus": ModelProfile(
        name="Claude 3 Opus",
        context_window=200000,
        tool_following=CapabilityLevel.EXCELLENT,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=64,
        supports_vision=True,
        notes="Most capable Claude model, best for complex reasoning",
    ),
    "claude-3-haiku": ModelProfile(
        name="Claude 3 Haiku",
        context_window=200000,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=True,
        max_tools_per_prompt=32,
        supports_vision=True,
        notes="Fast and efficient, good for simpler tasks",
    ),
    # -------------------------------------------------------------------------
    # OpenAI Models
    # -------------------------------------------------------------------------
    "gpt-4-turbo": ModelProfile(
        name="GPT-4 Turbo",
        context_window=128000,
        tool_following=CapabilityLevel.EXCELLENT,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=128,
        supports_vision=True,
        notes="Strong all-around model with excellent tool use",
    ),
    "gpt-4o": ModelProfile(
        name="GPT-4o",
        context_window=128000,
        tool_following=CapabilityLevel.EXCELLENT,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=128,
        supports_vision=True,
        notes="Optimized GPT-4 with multimodal capabilities",
    ),
    "gpt-4o-mini": ModelProfile(
        name="GPT-4o Mini",
        context_window=128000,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=True,
        max_tools_per_prompt=64,
        supports_vision=True,
        notes="Smaller, faster GPT-4o variant",
    ),
    "gpt-3.5-turbo": ModelProfile(
        name="GPT-3.5 Turbo",
        context_window=16385,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.MODERATE,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=True,
        max_tools_per_prompt=32,
        notes="Fast and cost-effective for simpler tasks",
    ),
    # -------------------------------------------------------------------------
    # DeepSeek Models
    # -------------------------------------------------------------------------
    "deepseek-chat": ModelProfile(
        name="DeepSeek Chat",
        context_window=64000,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=32,
        notes="Strong reasoning with thinking mode support",
    ),
    "deepseek-coder": ModelProfile(
        name="DeepSeek Coder",
        context_window=64000,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=32,
        notes="Specialized for code generation and understanding",
    ),
    "deepseek-reasoner": ModelProfile(
        name="DeepSeek Reasoner",
        context_window=64000,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=32,
        notes="Enhanced reasoning with chain-of-thought",
    ),
    # -------------------------------------------------------------------------
    # Ollama / Local Models - Llama Family
    # -------------------------------------------------------------------------
    "llama3.2": ModelProfile(
        name="Llama 3.2",
        context_window=8192,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=False,
        max_tools_per_prompt=20,
        notes="Good local model, needs clear tool formatting",
    ),
    "llama3.1": ModelProfile(
        name="Llama 3.1",
        context_window=8192,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=False,
        max_tools_per_prompt=20,
        notes="Solid local model with good instruction following",
    ),
    "llama3": ModelProfile(
        name="Llama 3",
        context_window=8192,
        tool_following=CapabilityLevel.MODERATE,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=False,
        max_tools_per_prompt=15,
        notes="Good general-purpose local model",
    ),
    "llama2": ModelProfile(
        name="Llama 2",
        context_window=4096,
        tool_following=CapabilityLevel.MODERATE,
        reasoning=CapabilityLevel.MODERATE,
        prompt_style=PromptStyle.EXPLICIT,
        supports_json_mode=False,
        max_tools_per_prompt=10,
        notes="Older model, needs explicit guidance",
    ),
    # -------------------------------------------------------------------------
    # Ollama / Local Models - Mistral Family
    # -------------------------------------------------------------------------
    "mistral": ModelProfile(
        name="Mistral 7B",
        context_window=8192,
        tool_following=CapabilityLevel.MODERATE,
        reasoning=CapabilityLevel.MODERATE,
        prompt_style=PromptStyle.EXPLICIT,
        supports_json_mode=False,
        max_tools_per_prompt=10,
        notes="Efficient 7B model, needs explicit tool formatting",
    ),
    "mistral-nemo": ModelProfile(
        name="Mistral Nemo",
        context_window=128000,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=False,
        max_tools_per_prompt=20,
        notes="12B parameter model with large context",
    ),
    "mixtral": ModelProfile(
        name="Mixtral 8x7B",
        context_window=32768,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=False,
        max_tools_per_prompt=20,
        notes="MoE model with good performance",
    ),
    "codestral": ModelProfile(
        name="Codestral",
        context_window=32768,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=False,
        max_tools_per_prompt=20,
        notes="Specialized for code, good tool following",
    ),
    "devstral": ModelProfile(
        name="Devstral",
        context_window=32768,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=False,
        max_tools_per_prompt=20,
        notes="Development-focused Mistral variant",
    ),
    # -------------------------------------------------------------------------
    # Ollama / Local Models - Code Specialized
    # -------------------------------------------------------------------------
    "codellama": ModelProfile(
        name="Code Llama",
        context_window=16384,
        tool_following=CapabilityLevel.MODERATE,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=False,
        max_tools_per_prompt=15,
        notes="Specialized for code generation",
    ),
    "qwen2.5-coder": ModelProfile(
        name="Qwen 2.5 Coder",
        context_window=32768,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=False,
        max_tools_per_prompt=20,
        notes="Strong code model with good instruction following",
    ),
    "starcoder2": ModelProfile(
        name="StarCoder2",
        context_window=16384,
        tool_following=CapabilityLevel.MODERATE,
        reasoning=CapabilityLevel.MODERATE,
        prompt_style=PromptStyle.EXPLICIT,
        supports_json_mode=False,
        max_tools_per_prompt=15,
        notes="Code-focused model, needs explicit formatting",
    ),
    # -------------------------------------------------------------------------
    # Ollama / Local Models - Other
    # -------------------------------------------------------------------------
    "phi3": ModelProfile(
        name="Phi-3",
        context_window=4096,
        tool_following=CapabilityLevel.MODERATE,
        reasoning=CapabilityLevel.MODERATE,
        prompt_style=PromptStyle.EXPLICIT,
        supports_json_mode=False,
        max_tools_per_prompt=10,
        notes="Small but capable Microsoft model",
    ),
    "gemma2": ModelProfile(
        name="Gemma 2",
        context_window=8192,
        tool_following=CapabilityLevel.MODERATE,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=False,
        max_tools_per_prompt=15,
        notes="Google's efficient open model",
    ),
    "command-r": ModelProfile(
        name="Command R",
        context_window=128000,
        tool_following=CapabilityLevel.GOOD,
        reasoning=CapabilityLevel.GOOD,
        prompt_style=PromptStyle.CONCISE,
        supports_json_mode=True,
        max_tools_per_prompt=20,
        notes="Cohere model with RAG capabilities",
    ),
    # -------------------------------------------------------------------------
    # OpenRouter Models
    # -------------------------------------------------------------------------
    "anthropic/claude-3.5-sonnet": ModelProfile(
        name="Claude 3.5 Sonnet (OpenRouter)",
        context_window=200000,
        tool_following=CapabilityLevel.EXCELLENT,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=64,
        supports_vision=True,
        notes="Claude via OpenRouter",
    ),
    "openai/gpt-4-turbo": ModelProfile(
        name="GPT-4 Turbo (OpenRouter)",
        context_window=128000,
        tool_following=CapabilityLevel.EXCELLENT,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=128,
        supports_vision=True,
        notes="GPT-4 Turbo via OpenRouter",
    ),
    "meta-llama/llama-3.1-405b-instruct": ModelProfile(
        name="Llama 3.1 405B (OpenRouter)",
        context_window=128000,
        tool_following=CapabilityLevel.EXCELLENT,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=50,
        notes="Largest Llama model via OpenRouter",
    ),
    "nousresearch/hermes-3-llama-3.1-405b": ModelProfile(
        name="Hermes 3 405B (OpenRouter)",
        context_window=128000,
        tool_following=CapabilityLevel.EXCELLENT,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=50,
        notes="Fine-tuned Llama 3.1 for function calling",
    ),
    # MiMo Models (Xiaomi)
    "mimo-v2-flash": ModelProfile(
        name="MiMo-V2-Flash",
        context_window=256000,
        tool_following=CapabilityLevel.EXCELLENT,
        reasoning=CapabilityLevel.EXCELLENT,
        prompt_style=PromptStyle.DETAILED,
        supports_json_mode=True,
        max_tools_per_prompt=64,
        supports_streaming=True,
        supports_vision=False,
        supports_function_calling=True,
        recommended_temperature=0.3,
        notes="Use JSON schema enforcement; supports reasoning mode via enable_thinking",
        exposes_thinking=True,
        thinking_field="reasoning_content",
        recommended_temperatures={
            "coding_planning": 0.3,
            "debugging": 0.5,
            "reasoning": 0.7,
            "creative": 0.9,
        },
        reasoning_budget={
            "simple": 2000,
            "moderate": 4000,
            "complex": 8000,
        },
    ),
}

# Default profile for unknown models
DEFAULT_PROFILE = ModelProfile(
    name="Unknown Model",
    context_window=4096,
    tool_following=CapabilityLevel.MODERATE,
    reasoning=CapabilityLevel.MODERATE,
    prompt_style=PromptStyle.CONCISE,
    supports_json_mode=False,
    max_tools_per_prompt=15,
    notes="Default profile for unrecognized models",
)


# =============================================================================
# Public API
# =============================================================================


def get_model_profile(model_name: str) -> ModelProfile:
    """
    Get capability profile for a model.

    Args:
        model_name: Model identifier (e.g., "llama3.2", "claude-3-5-sonnet")

    Returns:
        ModelProfile with capability information
    """
    # Normalize model name
    model_lower = model_name.lower().strip()

    # Remove common prefixes
    if model_lower.startswith("ollama/"):
        model_lower = model_lower[7:]

    # Try exact match first
    if model_lower in MODEL_PROFILES:
        return MODEL_PROFILES[model_lower]

    # Try prefix/substring match
    for key, profile in MODEL_PROFILES.items():
        # Check if model name starts with or contains the key
        if model_lower.startswith(key) or key in model_lower:
            logger.debug(f"Matched model '{model_name}' to profile '{key}'")
            return profile
        # Check reverse (key starts with model name)
        if key.startswith(model_lower):
            logger.debug(f"Matched model '{model_name}' to profile '{key}'")
            return profile

    # Try matching model family patterns
    family_patterns = {
        "llama": "llama3.2",
        "mistral": "mistral",
        "mixtral": "mixtral",
        "claude": "claude-3-5-sonnet",
        "gpt-4": "gpt-4-turbo",
        "gpt-3": "gpt-3.5-turbo",
        "deepseek": "deepseek-chat",
        "qwen": "qwen2.5-coder",
        "codellama": "codellama",
        "phi": "phi3",
        "gemma": "gemma2",
    }

    for pattern, profile_key in family_patterns.items():
        if pattern in model_lower:
            logger.debug(f"Matched model '{model_name}' to family profile '{profile_key}'")
            return MODEL_PROFILES.get(profile_key, DEFAULT_PROFILE)

    # Return default profile
    logger.warning(f"No profile found for model '{model_name}', using default")
    return DEFAULT_PROFILE


def get_prompt_style(model_name: str) -> PromptStyle:
    """Get recommended prompt style for a model."""
    profile = get_model_profile(model_name)
    return profile.prompt_style


def get_max_tools(model_name: str) -> int:
    """Get recommended maximum tools for a model."""
    profile = get_model_profile(model_name)
    return profile.max_tools_per_prompt


def get_context_window(model_name: str) -> int:
    """Get context window size for a model."""
    profile = get_model_profile(model_name)
    return profile.context_window


def supports_json_mode(model_name: str) -> bool:
    """Check if model supports native JSON mode."""
    profile = get_model_profile(model_name)
    return profile.supports_json_mode


def list_all_profiles() -> List[str]:
    """List all available model profile names."""
    return list(MODEL_PROFILES.keys())


def get_temperature_for_task(model_name: str, task_type: str) -> float:
    """
    Get recommended temperature for a specific task type.

    Args:
        model_name: Model identifier
        task_type: "coding_planning", "debugging", "reasoning", "creative"

    Returns:
        Recommended temperature
    """
    profile = get_model_profile(model_name)

    # Use model-specific temperature mapping if available
    if hasattr(profile, "recommended_temperatures") and profile.recommended_temperatures:
        return profile.recommended_temperatures.get(task_type, profile.recommended_temperature)

    # Default fallback
    return profile.recommended_temperature


def get_models_by_capability(
    min_tool_following: CapabilityLevel = CapabilityLevel.MODERATE,
    min_reasoning: CapabilityLevel = CapabilityLevel.MODERATE,
) -> List[str]:
    """
    Get models that meet minimum capability requirements.

    Args:
        min_tool_following: Minimum tool following capability
        min_reasoning: Minimum reasoning capability

    Returns:
        List of model names meeting requirements
    """
    capability_order = [
        CapabilityLevel.NONE,
        CapabilityLevel.LIMITED,
        CapabilityLevel.MODERATE,
        CapabilityLevel.GOOD,
        CapabilityLevel.EXCELLENT,
    ]

    def meets_requirement(actual: CapabilityLevel, minimum: CapabilityLevel) -> bool:
        return capability_order.index(actual) >= capability_order.index(minimum)

    matching = []
    for name, profile in MODEL_PROFILES.items():
        if meets_requirement(profile.tool_following, min_tool_following) and meets_requirement(
            profile.reasoning, min_reasoning
        ):
            matching.append(name)

    return matching
