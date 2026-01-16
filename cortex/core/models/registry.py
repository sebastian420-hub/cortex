"""
Model Registry for Self-Orchestrating Multi-Model System.

This module defines the available models, their capabilities, and delegation rules.
Models use this registry to understand their own role and what models they can delegate to.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class ModelCapability(str, Enum):
    """Capabilities that models can have."""
    GENERAL = "general"
    CHAT = "chat"
    COORDINATION = "coordination"
    TOOL_USE = "tool_use"
    PLANNING = "planning"
    REASONING = "reasoning"
    ANALYSIS = "analysis"
    COMPLEX_PROBLEMS = "complex_problems"
    CODING = "coding"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    COMPLEX_CODE = "complex_code"
    REVIEW = "review"
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    QUALITY = "quality"
    WEB_RESEARCH = "web_research"
    FAST_CODING = "fast_coding"


class ModelRole(str, Enum):
    """Role a model plays in the orchestration system."""
    COORDINATOR = "coordinator"  # Main model that orchestrates
    SPECIALIST = "specialist"    # Specialized model for specific tasks


class CostTier(str, Enum):
    """Cost tier for models."""
    FREE = "free"      # Local models (Ollama)
    LOW = "low"        # Cheap API models
    MEDIUM = "medium"  # Moderate cost
    HIGH = "high"      # Expensive models (Claude, GPT-4)


@dataclass
class ModelConfig:
    """Configuration for a model in the orchestration system."""
    name: str
    provider: str
    role: ModelRole
    capabilities: List[ModelCapability]
    can_delegate_to: List[str]
    prompt_profile: str
    cost_tier: CostTier
    # Optional configuration
    api_model_name: Optional[str] = None  # If different from name
    max_thinking_tokens: Optional[int] = None  # For reasoning models
    ollama_model: Optional[str] = None  # For local models
    enabled: bool = True
    description: str = ""

    def has_capability(self, capability: ModelCapability) -> bool:
        """Check if model has a specific capability."""
        return capability in self.capabilities

    def can_delegate_to_model(self, model_name: str) -> bool:
        """Check if this model can delegate to another model."""
        return model_name in self.can_delegate_to

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "provider": self.provider,
            "role": self.role.value,
            "capabilities": [c.value for c in self.capabilities],
            "can_delegate_to": self.can_delegate_to,
            "prompt_profile": self.prompt_profile,
            "cost_tier": self.cost_tier.value,
            "api_model_name": self.api_model_name,
            "max_thinking_tokens": self.max_thinking_tokens,
            "ollama_model": self.ollama_model,
            "enabled": self.enabled,
            "description": self.description,
        }


# Default Model Registry
# This can be extended via configuration files
MODEL_REGISTRY: Dict[str, ModelConfig] = {
    # =====================================================
    # COORDINATOR - Main orchestration model
    # =====================================================
    "mimo-v2-flash": ModelConfig(
        name="mimo-v2-flash",
        provider="openrouter",
        role=ModelRole.COORDINATOR,
        capabilities=[
            ModelCapability.GENERAL,
            ModelCapability.CHAT,
            ModelCapability.COORDINATION,
            ModelCapability.TOOL_USE,
        ],
        can_delegate_to=[
            "deepseek-reasoner",  # Planning/reasoning
            "hermes-3-405b",      # Debugging/security
            "dolphin-24b",        # Security
            "sonar-pro-search",   # Web research
            "gpt-5.1-codex-mini", # Coding
            "grok-code-fast-1",   # Fast coding
        ],
        prompt_profile="coordinator",
        cost_tier=CostTier.FREE,
        api_model_name="xiaomi/mimo-v2-flash:free",
        description="Xiaomi MiMo V2 Flash - Default coordinator for chat and orchestration",
    ),

    # =====================================================
    # PLANNING & REASONING SPECIALIST
    # =====================================================
    "deepseek-reasoner": ModelConfig(
        name="deepseek-reasoner",
        provider="deepseek",
        role=ModelRole.SPECIALIST,
        capabilities=[
            ModelCapability.PLANNING,
            ModelCapability.REASONING,
            ModelCapability.ANALYSIS,
            ModelCapability.COMPLEX_PROBLEMS,
        ],
        can_delegate_to=[
            "mimo-v2-flash",      # Return to coordinator
            "gpt-5.1-codex-mini", # Coding implementation
            "grok-code-fast-1",   # Fast coding
        ],
        prompt_profile="reasoner",
        cost_tier=CostTier.MEDIUM,
        max_thinking_tokens=8000,
        description="DeepSeek Reasoner - Deep thinking, planning, and complex reasoning",
    ),

    # =====================================================
    # DEBUGGING SPECIALIST
    # =====================================================
    "hermes-3-405b": ModelConfig(
        name="hermes-3-405b",
        provider="openrouter",
        role=ModelRole.SPECIALIST,
        capabilities=[
            ModelCapability.DEBUGGING,
            ModelCapability.ANALYSIS,
            ModelCapability.SECURITY,
            ModelCapability.REVIEW,
            ModelCapability.TOOL_USE,
        ],
        can_delegate_to=[
            "mimo-v2-flash",      # Return to coordinator
            "deepseek-reasoner",  # Complex analysis
            "gpt-5.1-codex-mini", # Fix implementation
        ],
        prompt_profile="debugger",
        cost_tier=CostTier.FREE,
        api_model_name="nousresearch/hermes-3-llama-3.1-405b:free",
        description="Hermes 3 405B - Debugging and security analysis specialist",
    ),

    # =====================================================
    # SECURITY SPECIALIST
    # =====================================================
    "dolphin-24b": ModelConfig(
        name="dolphin-24b",
        provider="openrouter",
        role=ModelRole.SPECIALIST,
        capabilities=[
            ModelCapability.SECURITY,
            ModelCapability.REVIEW,
            ModelCapability.ANALYSIS,
            ModelCapability.QUALITY,
        ],
        can_delegate_to=[
            "mimo-v2-flash",      # Return to coordinator
            "hermes-3-405b",      # Deep debugging
        ],
        prompt_profile="reviewer",
        cost_tier=CostTier.FREE,
        api_model_name="cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
        description="Dolphin 24B - Security review and vulnerability analysis",
    ),

    # =====================================================
    # WEB RESEARCH SPECIALIST
    # =====================================================
    "sonar-pro-search": ModelConfig(
        name="sonar-pro-search",
        provider="openrouter",
        role=ModelRole.SPECIALIST,
        capabilities=[
            ModelCapability.WEB_RESEARCH,
            ModelCapability.ANALYSIS,
            ModelCapability.GENERAL,
        ],
        can_delegate_to=[
            "mimo-v2-flash",      # Return to coordinator
        ],
        prompt_profile="researcher",
        cost_tier=CostTier.MEDIUM,
        api_model_name="perplexity/sonar-pro-search",
        description="Sonar Pro Search - Web research and information gathering",
    ),

    # =====================================================
    # CODING SPECIALISTS
    # =====================================================
    "gpt-5.1-codex-mini": ModelConfig(
        name="gpt-5.1-codex-mini",
        provider="openrouter",
        role=ModelRole.SPECIALIST,
        capabilities=[
            ModelCapability.CODING,
            ModelCapability.DEBUGGING,
            ModelCapability.REFACTORING,
            ModelCapability.COMPLEX_CODE,
            ModelCapability.TOOL_USE,
        ],
        can_delegate_to=[
            "mimo-v2-flash",      # Return to coordinator
            "deepseek-reasoner",  # Complex planning
            "hermes-3-405b",      # Debugging help
        ],
        prompt_profile="coder",
        cost_tier=CostTier.LOW,
        api_model_name="openai/gpt-5.1-codex-mini",
        description="GPT 5.1 Codex Mini - Primary coding and implementation model",
    ),

    "grok-code-fast-1": ModelConfig(
        name="grok-code-fast-1",
        provider="openrouter",
        role=ModelRole.SPECIALIST,
        capabilities=[
            ModelCapability.CODING,
            ModelCapability.FAST_CODING,
            ModelCapability.DEBUGGING,
            ModelCapability.TOOL_USE,
        ],
        can_delegate_to=[
            "mimo-v2-flash",      # Return to coordinator
            "gpt-5.1-codex-mini", # Complex coding
        ],
        prompt_profile="coder",
        cost_tier=CostTier.FREE,
        api_model_name="x-ai/grok-code-fast-1",
        description="Grok Code Fast - Quick coding tasks and rapid implementation",
    ),

    # =====================================================
    # LEGACY/BACKUP MODELS (kept for compatibility)
    # =====================================================
    "deepseek-chat": ModelConfig(
        name="deepseek-chat",
        provider="deepseek",
        role=ModelRole.SPECIALIST,  # Changed from coordinator
        capabilities=[
            ModelCapability.GENERAL,
            ModelCapability.CHAT,
            ModelCapability.TOOL_USE,
        ],
        can_delegate_to=["mimo-v2-flash"],
        prompt_profile="coordinator",
        cost_tier=CostTier.LOW,
        enabled=True,  # Available as backup
        description="DeepSeek Chat - Backup general chat model",
    ),

    # User's fine-tuned coding models (Ollama/local) - for future use
    "cortex-coder-14b": ModelConfig(
        name="cortex-coder-14b",
        provider="ollama",
        role=ModelRole.SPECIALIST,
        capabilities=[
            ModelCapability.CODING,
            ModelCapability.DEBUGGING,
            ModelCapability.REFACTORING,
            ModelCapability.TOOL_USE,
        ],
        can_delegate_to=["mimo-v2-flash", "deepseek-reasoner"],
        prompt_profile="coder",
        cost_tier=CostTier.FREE,
        ollama_model="cortex-coder:14b",
        enabled=False,  # Disabled until user's model is available
        description="Cortex Coder 14B - User's fine-tuned coding model (local)",
    ),

    "cortex-coder-32b": ModelConfig(
        name="cortex-coder-32b",
        provider="ollama",
        role=ModelRole.SPECIALIST,
        capabilities=[
            ModelCapability.CODING,
            ModelCapability.DEBUGGING,
            ModelCapability.REFACTORING,
            ModelCapability.COMPLEX_CODE,
            ModelCapability.TOOL_USE,
        ],
        can_delegate_to=["mimo-v2-flash", "deepseek-reasoner"],
        prompt_profile="coder",
        cost_tier=CostTier.FREE,
        ollama_model="cortex-coder:32b",
        enabled=False,  # Disabled until user's model is available
        description="Cortex Coder 32B - User's fine-tuned coding model (local, larger)",
    ),
}


class ModelRegistry:
    """
    Registry for managing models in the orchestration system.

    Provides methods to query models, check capabilities, and validate
    delegation paths.
    """

    def __init__(self, models: Optional[Dict[str, ModelConfig]] = None):
        """Initialize the registry with models."""
        self._models = models or MODEL_REGISTRY.copy()

    def get_model(self, name: str) -> Optional[ModelConfig]:
        """
        Get a model configuration by name.

        Supports lookup by:
        - Short name (e.g., 'mimo-v2-flash')
        - Full API name (e.g., 'xiaomi/mimo-v2-flash:free')
        """
        # First try direct lookup by short name
        if name in self._models:
            return self._models[name]

        # Try lookup by api_model_name (reverse lookup)
        for model in self._models.values():
            if model.api_model_name == name:
                return model

        return None

    def get_short_name(self, name: str) -> Optional[str]:
        """
        Get the short registry name for a model.

        Args:
            name: Either short name or full API name

        Returns:
            Short registry name or None if not found
        """
        # If it's already a short name
        if name in self._models:
            return name

        # Try to find by api_model_name
        for short_name, model in self._models.items():
            if model.api_model_name == name:
                return short_name

        return None

    def get_enabled_models(self) -> Dict[str, ModelConfig]:
        """Get all enabled models."""
        return {k: v for k, v in self._models.items() if v.enabled}

    def get_models_by_capability(self, capability: ModelCapability) -> List[ModelConfig]:
        """Get all models with a specific capability."""
        return [m for m in self._models.values() if m.has_capability(capability) and m.enabled]

    def get_models_by_role(self, role: ModelRole) -> List[ModelConfig]:
        """Get all models with a specific role."""
        return [m for m in self._models.values() if m.role == role and m.enabled]

    def get_coordinator(self) -> Optional[ModelConfig]:
        """Get the default coordinator model."""
        coordinators = self.get_models_by_role(ModelRole.COORDINATOR)
        return coordinators[0] if coordinators else None

    def get_delegation_targets(self, from_model: str) -> List[str]:
        """Get list of models that a model can delegate to."""
        model = self.get_model(from_model)
        if not model:
            return []
        # Filter to only enabled models
        return [m for m in model.can_delegate_to if self.is_model_available(m)]

    def is_model_available(self, name: str) -> bool:
        """Check if a model is available (exists and enabled)."""
        model = self.get_model(name)
        return model is not None and model.enabled

    def validate_delegation(self, from_model: str, to_model: str) -> tuple[bool, str]:
        """
        Validate if a delegation from one model to another is allowed.

        Supports both short names and full API names for both models.

        Returns:
            Tuple of (is_valid, reason)
        """
        source = self.get_model(from_model)
        if not source:
            return False, f"Source model '{from_model}' not found in registry"

        if not source.enabled:
            return False, f"Source model '{from_model}' is disabled"

        # Get the short name for target model to check can_delegate_to
        target_short_name = self.get_short_name(to_model)
        if not target_short_name:
            return False, f"Target model '{to_model}' not found in registry"

        # can_delegate_to uses short names
        if target_short_name not in source.can_delegate_to:
            return False, f"Model '{from_model}' cannot delegate to '{to_model}'"

        target = self.get_model(to_model)
        if not target:
            return False, f"Target model '{to_model}' not found in registry"

        if not target.enabled:
            return False, f"Target model '{to_model}' is disabled"

        return True, "Delegation allowed"

    def register_model(self, config: ModelConfig) -> None:
        """Register a new model in the registry."""
        self._models[config.name] = config

    def update_model(self, name: str, **kwargs) -> bool:
        """Update a model's configuration."""
        model = self.get_model(name)
        if not model:
            return False

        for key, value in kwargs.items():
            if hasattr(model, key):
                setattr(model, key, value)

        return True

    def enable_model(self, name: str) -> bool:
        """Enable a model."""
        return self.update_model(name, enabled=True)

    def disable_model(self, name: str) -> bool:
        """Disable a model."""
        return self.update_model(name, enabled=False)

    def get_model_for_capability(self, capability: ModelCapability, exclude: Optional[List[str]] = None) -> Optional[ModelConfig]:
        """
        Get the best model for a specific capability.

        Prefers lower cost models when multiple options available.
        """
        exclude = exclude or []
        models = [m for m in self.get_models_by_capability(capability) if m.name not in exclude]

        if not models:
            return None

        # Sort by cost tier (free first, then low, medium, high)
        tier_order = {CostTier.FREE: 0, CostTier.LOW: 1, CostTier.MEDIUM: 2, CostTier.HIGH: 3}
        models.sort(key=lambda m: tier_order[m.cost_tier])

        return models[0]

    def to_dict(self) -> Dict[str, Dict]:
        """Convert registry to dictionary for serialization."""
        return {name: config.to_dict() for name, config in self._models.items()}

    def get_delegation_summary(self, model_name: str) -> str:
        """Get a human-readable summary of delegation options for a model."""
        model = self.get_model(model_name)
        if not model:
            return f"Model '{model_name}' not found"

        targets = self.get_delegation_targets(model_name)
        if not targets:
            return f"Model '{model_name}' cannot delegate to any available models"

        lines = [f"Model '{model_name}' can delegate to:"]
        for target_name in targets:
            target = self.get_model(target_name)
            if target:
                caps = ", ".join(c.value for c in target.capabilities[:3])
                lines.append(f"  - {target_name}: {caps}")

        return "\n".join(lines)


# Global registry instance
_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Get the global model registry instance."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


def reset_model_registry() -> None:
    """Reset the global model registry (for testing)."""
    global _registry
    _registry = None
