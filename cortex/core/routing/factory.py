"""
Enhanced Provider Factory with configurable routing rules.

This extends the basic ProviderFactory with:
- Configurable provider detection rules
- Support for additional providers (OpenAI, Azure, Gemini)
- Model alias support
- Provider health checks and fallback
"""

import os
import logging
from typing import Dict, Any, Optional, List, Type
from dataclasses import dataclass, field
from enum import Enum

from ..providers import (
    ModelProvider,
    OllamaProvider,
    DeepSeekProvider,
    AnthropicProvider,
    OpenRouterProvider,
    ProviderError,
    ProviderFactory as LegacyProviderFactory
)

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Types of model providers."""
    OLLAMA = "ollama"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    AZURE = "azure"
    GEMINI = "gemini"
    CUSTOM = "custom"


@dataclass
class ProviderConfig:
    """Configuration for a model provider."""
    provider_type: ProviderType
    enabled: bool = True
    priority: int = 0
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    default_models: List[str] = field(default_factory=list)
    aliases: Dict[str, str] = field(default_factory=dict)
    health_check_enabled: bool = True
    fallback_providers: List[ProviderType] = field(default_factory=list)


@dataclass
class RoutingRule:
    """Rule for routing models to providers."""
    pattern: str  # Regex pattern or simple wildcard
    provider_type: ProviderType
    priority: int = 0
    description: Optional[str] = None


class EnhancedProviderFactory:
    """
    Enhanced provider factory with configurable routing rules.
    
    This factory extends the basic ProviderFactory with:
    - Configurable routing rules via regex/wildcard patterns
    - Model alias resolution
    - Provider health checks
    - Fallback mechanisms
    - Support for additional providers
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the enhanced provider factory.
        
        Args:
            config: Configuration dictionary with provider settings
        """
        self.config = config or {}
        self.provider_configs: Dict[ProviderType, ProviderConfig] = {}
        self.routing_rules: List[RoutingRule] = []
        self.provider_cache: Dict[ProviderType, ModelProvider] = {}
        
        self._load_default_config()
        self._load_routing_rules()
        
    def _load_default_config(self) -> None:
        """Load default provider configurations."""
        # Ollama configuration
        self.provider_configs[ProviderType.OLLAMA] = ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            enabled=True,
            priority=0,  # Highest priority for local models
            api_key_env=None,
            default_models=["llama3.2", "llama3.3:70b", "qwen2.5:32b"],
            aliases={
                "llama": "llama3.2",
                "deepseek-r1": "deepseek-r1:8b",
                "qwen": "qwen2.5:32b"
            }
        )
        
        # DeepSeek configuration
        self.provider_configs[ProviderType.DEEPSEEK] = ProviderConfig(
            provider_type=ProviderType.DEEPSEEK,
            enabled=True,
            priority=1,
            api_key_env="DEEPSEEK_API_KEY",
            base_url="https://api.deepseek.com",
            default_models=["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
            aliases={
                "deepseek": "deepseek-chat"
            }
        )
        
        # Anthropic configuration
        self.provider_configs[ProviderType.ANTHROPIC] = ProviderConfig(
            provider_type=ProviderType.ANTHROPIC,
            enabled=True,
            priority=2,
            api_key_env="ANTHROPIC_API_KEY",
            default_models=[
                "claude-3-5-sonnet-20241022",
                "claude-3-haiku-20240307",
                "claude-3-opus-20240229"
            ],
            aliases={
                "claude": "claude-3-5-sonnet-20241022",
                "claude-sonnet": "claude-3-5-sonnet-20241022",
                "claude-haiku": "claude-3-haiku-20240307",
                "claude-opus": "claude-3-opus-20240229"
            }
        )
        
        # OpenRouter configuration
        self.provider_configs[ProviderType.OPENROUTER] = ProviderConfig(
            provider_type=ProviderType.OPENROUTER,
            enabled=True,
            priority=3,
            api_key_env="OPENROUTER_API_KEY",
            base_url="https://openrouter.ai/api/v1",
            default_models=["openrouter/auto"],
            aliases={}
        )
        
        # Load custom configurations from config dict
        if "providers" in self.config:
            for provider_name, provider_cfg in self.config["providers"].items():
                try:
                    provider_type = ProviderType(provider_name.lower())
                    if provider_type in self.provider_configs:
                        # Update existing config
                        cfg = self.provider_configs[provider_type]
                        if "enabled" in provider_cfg:
                            cfg.enabled = provider_cfg["enabled"]
                        if "priority" in provider_cfg:
                            cfg.priority = provider_cfg["priority"]
                        if "aliases" in provider_cfg:
                            cfg.aliases.update(provider_cfg["aliases"])
                except ValueError:
                    logger.warning(f"Unknown provider type in config: {provider_name}")
    
    def _load_routing_rules(self) -> None:
        """Load default routing rules."""
        # Default routing rules (similar to legacy ProviderFactory logic)
        self.routing_rules = [
            # OpenRouter models
            RoutingRule(
                pattern=r".*devstral.*",
                provider_type=ProviderType.OPENROUTER,
                description="Devstral models via OpenRouter"
            ),
            RoutingRule(
                pattern=r"^openrouter/.*",
                provider_type=ProviderType.OPENROUTER,
                description="OpenRouter model prefix"
            ),
            
            # Ollama models (contain colon)
            RoutingRule(
                pattern=r".*:.*",
                provider_type=ProviderType.OLLAMA,
                description="Ollama models use colon syntax"
            ),
            
            # DeepSeek models
            RoutingRule(
                pattern=r"^deepseek-.*",
                provider_type=ProviderType.DEEPSEEK,
                description="DeepSeek model prefix"
            ),
            
            # Anthropic/Claude models
            RoutingRule(
                pattern=r"^claude-.*",
                provider_type=ProviderType.ANTHROPIC,
                description="Claude model prefix"
            ),
            RoutingRule(
                pattern=r"^claude$",
                provider_type=ProviderType.ANTHROPIC,
                description="Claude shorthand"
            ),
            
            # Default fallback to Ollama
            RoutingRule(
                pattern=r".*",
                provider_type=ProviderType.OLLAMA,
                priority=100,  # Lowest priority
                description="Default fallback to Ollama"
            )
        ]
        
        # Load custom routing rules from config
        if "routing_rules" in self.config:
            for rule_cfg in self.config["routing_rules"]:
                try:
                    provider_type = ProviderType(rule_cfg["provider"])
                    rule = RoutingRule(
                        pattern=rule_cfg["pattern"],
                        provider_type=provider_type,
                        priority=rule_cfg.get("priority", 0),
                        description=rule_cfg.get("description")
                    )
                    self.routing_rules.append(rule)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Invalid routing rule config: {e}")
        
        # Sort rules by priority (lower = higher priority)
        self.routing_rules.sort(key=lambda r: r.priority)
    
    def get_provider(self, model_name: str, provider_override: Optional[str] = None) -> ModelProvider:
        """
        Get appropriate provider for model name with enhanced routing logic.
        
        Args:
            model_name: Name of the model
            provider_override: Optional provider name to override auto-detection
            
        Returns:
            ModelProvider instance
            
        Raises:
            ProviderError: If provider cannot be determined or created
        """
        # Use override if specified
        if provider_override:
            return self._create_provider_by_name(provider_override)
        
        # Resolve model alias
        resolved_model = self._resolve_model_alias(model_name)
        
        # Find matching routing rule
        provider_type = self._route_model(resolved_model)
        
        # Check if provider is enabled
        if not self._is_provider_enabled(provider_type):
            # Try to find fallback provider
            fallback = self._find_fallback_provider(provider_type)
            if fallback:
                logger.warning(
                    f"Provider {provider_type.value} is disabled, "
                    f"falling back to {fallback.value}"
                )
                provider_type = fallback
            else:
                raise ProviderError(f"Provider {provider_type.value} is disabled and no fallback available")
        
        # Create provider instance
        return self._create_provider(provider_type)
    
    def _resolve_model_alias(self, model_name: str) -> str:
        """
        Resolve model alias to actual model name.
        
        Args:
            model_name: Input model name or alias
            
        Returns:
            Resolved model name
        """
        for provider_type, config in self.provider_configs.items():
            if model_name in config.aliases:
                resolved = config.aliases[model_name]
                logger.debug(f"Resolved model alias {model_name} -> {resolved}")
                return resolved
        return model_name
    
    def _route_model(self, model_name: str) -> ProviderType:
        """
        Route model to provider based on routing rules.
        
        Args:
            model_name: Model name to route
            
        Returns:
            ProviderType for the model
            
        Raises:
            ProviderError: If no routing rule matches
        """
        import re
        
        for rule in self.routing_rules:
            # Simple wildcard matching for now (convert * to .*)
            pattern = rule.pattern.replace("*", ".*")
            if re.match(pattern, model_name, re.IGNORECASE):
                logger.debug(
                    f"Routed model '{model_name}' to {rule.provider_type.value} "
                    f"(rule: {rule.description or rule.pattern})"
                )
                return rule.provider_type
        
        # This should never happen due to catch-all rule
        raise ProviderError(f"No routing rule matched for model: {model_name}")
    
    def _is_provider_enabled(self, provider_type: ProviderType) -> bool:
        """Check if provider is enabled."""
        config = self.provider_configs.get(provider_type)
        if not config:
            return False
        return config.enabled
    
    def _find_fallback_provider(self, original_provider: ProviderType) -> Optional[ProviderType]:
        """Find fallback provider when original is disabled."""
        config = self.provider_configs.get(original_provider)
        if not config:
            return None
        
        for fallback_type in config.fallback_providers:
            if self._is_provider_enabled(fallback_type):
                return fallback_type
        
        # Default fallback chain
        fallback_chain = [
            ProviderType.OLLAMA,
            ProviderType.DEEPSEEK,
            ProviderType.ANTHROPIC,
            ProviderType.OPENROUTER
        ]
        
        for provider_type in fallback_chain:
            if provider_type != original_provider and self._is_provider_enabled(provider_type):
                return provider_type
        
        return None
    
    def _create_provider(self, provider_type: ProviderType) -> ModelProvider:
        """
        Create provider instance with caching.
        
        Args:
            provider_type: Type of provider to create
            
        Returns:
            ModelProvider instance
            
        Raises:
            ProviderError: If provider cannot be created
        """
        # Check cache first
        if provider_type in self.provider_cache:
            return self.provider_cache[provider_type]
        
        # Create new provider
        provider = self._create_provider_by_type(provider_type)
        
        # Cache for future use
        self.provider_cache[provider_type] = provider
        
        return provider
    
    def _create_provider_by_type(self, provider_type: ProviderType) -> ModelProvider:
        """Create provider by type."""
        # Check API key for cloud providers
        config = self.provider_configs.get(provider_type)
        if config and config.api_key_env:
            api_key = os.getenv(config.api_key_env)
            if not api_key:
                raise ProviderError(
                    f"{config.api_key_env} environment variable not set. "
                    f"Please set it to use {provider_type.value} provider."
                )
        
        # Create provider instance
        if provider_type == ProviderType.OLLAMA:
            return OllamaProvider()
        elif provider_type == ProviderType.DEEPSEEK:
            return DeepSeekProvider()
        elif provider_type == ProviderType.ANTHROPIC:
            return AnthropicProvider()
        elif provider_type == ProviderType.OPENROUTER:
            return OpenRouterProvider()
        else:
            # For now, use legacy factory for unknown providers
            # In the future, we'll add support for OpenAI, Azure, Gemini
            try:
                return LegacyProviderFactory._create_provider_by_name(provider_type.value)
            except ProviderError:
                raise ProviderError(f"Unsupported provider type: {provider_type.value}")
    
    def _create_provider_by_name(self, provider_name: str) -> ModelProvider:
        """Create provider by name (for backward compatibility)."""
        try:
            provider_type = ProviderType(provider_name.lower())
            return self._create_provider(provider_type)
        except ValueError:
            # Try legacy factory
            return LegacyProviderFactory._create_provider_by_name(provider_name)
    
    def get_provider_name(self, model_name: str) -> str:
        """
        Get provider name for a model.
        
        Args:
            model_name: Model name
            
        Returns:
            Provider name as string
        """
        try:
            provider_type = self._route_model(model_name)
            return provider_type.value
        except ProviderError:
            # Fallback to legacy method
            return LegacyProviderFactory.get_provider_name(model_name)
    
    def is_cloud_provider(self, model_name: str) -> bool:
        """
        Check if model name indicates a cloud provider.
        
        Args:
            model_name: Model name to check
            
        Returns:
            True if model uses a cloud provider
        """
        try:
            provider_type = self._route_model(model_name)
            # Consider Ollama as local, others as cloud
            return provider_type != ProviderType.OLLAMA
        except ProviderError:
            # Fallback to legacy method
            return LegacyProviderFactory.is_cloud_provider(model_name)
    
    def register_provider(self, provider_type: ProviderType, provider_class: Type[ModelProvider]) -> None:
        """
        Register a custom provider class.
        
        Args:
            provider_type: Provider type to register
            provider_class: Provider class to use
        """
        # This will be implemented when we add support for custom providers
        logger.warning(f"Custom provider registration not yet implemented for {provider_type}")
    
    def add_routing_rule(self, rule: RoutingRule) -> None:
        """
        Add a custom routing rule.
        
        Args:
            rule: Routing rule to add
        """
        self.routing_rules.append(rule)
        # Re-sort rules by priority
        self.routing_rules.sort(key=lambda r: r.priority)
        logger.debug(f"Added routing rule: {rule.description or rule.pattern}")


# Global instance for backward compatibility
_default_factory: Optional[EnhancedProviderFactory] = None

def get_provider_factory(config: Optional[Dict[str, Any]] = None) -> EnhancedProviderFactory:
    """
    Get or create the global provider factory instance.
    
    Args:
        config: Optional configuration to initialize factory
        
    Returns:
        EnhancedProviderFactory instance
    """
    global _default_factory
    if _default_factory is None or config is not None:
        _default_factory = EnhancedProviderFactory(config)
    return _default_factory

# Backward compatibility functions
def get_provider(model_name: str, provider_override: Optional[str] = None) -> ModelProvider:
    """Backward compatibility wrapper."""
    factory = get_provider_factory()
    return factory.get_provider(model_name, provider_override)

def get_provider_name(model_name: str) -> str:
    """Backward compatibility wrapper."""
    factory = get_provider_factory()
    return factory.get_provider_name(model_name)

def is_cloud_provider(model_name: str) -> bool:
    """Backward compatibility wrapper."""
    factory = get_provider_factory()
    return factory.is_cloud_provider(model_name)