"""Factory for creating model providers based on model name."""

from typing import Optional

from .base import ModelProvider, ProviderError
from .ollama import OllamaProvider
from .deepseek import DeepSeekProvider
from .anthropic_provider import AnthropicProvider
from .openrouter import OpenRouterProvider


class ProviderFactory:
    """Factory for creating model providers based on model name"""

    @staticmethod
    def get_provider(model_name: str, provider_override: Optional[str] = None) -> ModelProvider:
        """
        Get appropriate provider for model name.

        Args:
            model_name: Name of the model
            provider_override: Optional provider name to override auto-detection

        Returns:
            ModelProvider instance
        """
        if provider_override:
            return ProviderFactory._create_provider_by_name(provider_override)

        # Auto-detect provider from model name
        model_lower = model_name.lower()

        # Exclude models with ollama/ prefix - these are local
        if model_lower.startswith("ollama/"):
            return OllamaProvider()

        # Generic slash detection for OpenRouter models (user requested: models with slashes are OpenRouter)  # noqa: E501
        if "/" in model_name:
            return OpenRouterProvider()

        # Check for OpenRouter models first (including models with colons)
        openrouter_indicators = [
            "devstral",
            "openrouter/",
            "nvidia/",
            ":free",
            ":paid",
            "mistralai/",
            "google/",
            "anthropic/",
            "meta-llama/",
            "perplexity/",
            "cohere/",
            "jamba/",
            "qwen/",
            "x-ai/",
            "xiaomi/",
            "cognitivecomputations/",
            "openai/",
            "nousresearch/",
            "z-ai/",
        ]

        # Special case: if model contains "llama3" but looks like Ollama format, it's Ollama
        if "llama3" in model_lower and ":" in model_name:
            # Check if it matches Ollama pattern like "llama3.2:70b" or "llama3:70b"
            import re

            if re.match(r"^llama3(\.\d+)?:\d+[bB]?$", model_name):
                # This is an Ollama model, skip to Ollama detection below
                # Don't return here, let it fall through
                pass
            else:
                # Check other OpenRouter indicators
                if any(indicator in model_lower for indicator in openrouter_indicators):
                    return OpenRouterProvider()
                # If no other indicators, fall through to Ollama
        elif any(indicator in model_lower for indicator in openrouter_indicators):
            return OpenRouterProvider()

        # Check for Ollama model patterns (contains colon but not OpenRouter patterns)
        if ":" in model_name:
            # Ollama models use colons: deepseek-r1:8b, llama3.2:70b
            return OllamaProvider()

        # Check for cloud providers
        if model_lower.startswith("deepseek-"):
            return DeepSeekProvider()
        elif model_lower.startswith("claude-") or model_lower == "claude":
            return AnthropicProvider()
        else:
            # Default to Ollama for local models
            return OllamaProvider()

    @staticmethod
    def _create_provider_by_name(provider_name: str) -> ModelProvider:
        """Create provider by explicit name"""
        provider_lower = provider_name.lower()

        if provider_lower == "ollama":
            return OllamaProvider()
        elif provider_lower == "deepseek":
            return DeepSeekProvider()
        elif provider_lower in ["anthropic", "claude"]:
            return AnthropicProvider()
        elif provider_lower == "openrouter":
            return OpenRouterProvider()
        else:
            raise ProviderError(f"Unknown provider: {provider_name}")

    @staticmethod
    def is_cloud_provider(model_name: str) -> bool:
        """Check if model name indicates a cloud provider"""
        model_lower = model_name.lower()

        # Exclude models with ollama/ prefix - these are local
        if model_lower.startswith("ollama/"):
            return False

        # Generic slash detection for OpenRouter models (user requested: models with slashes are OpenRouter)  # noqa: E501
        if "/" in model_name:
            return True

        # Check for OpenRouter indicators first (including models with colons)
        openrouter_indicators = [
            "devstral",
            "openrouter/",
            "nvidia/",
            ":free",
            ":paid",
            "mistralai/",
            "google/",
            "anthropic/",
            "meta-llama/",
            "perplexity/",
            "cohere/",
            "jamba/",
            "qwen/",
            "x-ai/",
            "xiaomi/",
            "cognitivecomputations/",
            "openai/",
            "nousresearch/",
            "z-ai/",
        ]

        # Special case: if model contains "llama3" but looks like Ollama format, it's Ollama
        if "llama3" in model_lower and ":" in model_name:
            import re

            # Check if it matches Ollama pattern like "llama3.2:70b" or "llama3:70b"
            if re.match(r"^llama3(\.\d+)?:\d+[bB]?$", model_name):
                # This is an Ollama model (local)
                return False
            else:
                # Check other OpenRouter indicators
                if any(indicator in model_lower for indicator in openrouter_indicators):
                    return True
        elif any(indicator in model_lower for indicator in openrouter_indicators):
            return True

        # Check for Ollama model patterns (contains colon but not OpenRouter patterns)
        if ":" in model_name:
            return False

        # Check for other cloud providers
        if model_lower.startswith("deepseek-"):
            return True
        if model_lower.startswith("claude-") or model_lower == "claude":
            return True

        # Default to local (Ollama)
        return False

    @staticmethod
    def get_provider_name(model_name: str) -> str:
        """Get provider name for a model"""
        model_lower = model_name.lower()

        # Exclude models with ollama/ prefix - these are local
        if model_lower.startswith("ollama/"):
            return "ollama"

        # Generic slash detection for OpenRouter models (user requested: models with slashes are OpenRouter)  # noqa: E501
        if "/" in model_name:
            return "openrouter"

        # Check for OpenRouter models first (including models with colons)
        openrouter_indicators = [
            "devstral",
            "openrouter/",
            "nvidia/",
            ":free",
            ":paid",
            "mistralai/",
            "google/",
            "anthropic/",
            "meta-llama/",
            "perplexity/",
            "cohere/",
            "jamba/",
            "qwen/",
            "x-ai/",
            "xiaomi/",
            "cognitivecomputations/",
            "openai/",
            "nousresearch/",
            "z-ai/",
        ]

        # Special case: if model contains "llama3" but looks like Ollama format, it's Ollama
        if "llama3" in model_lower and ":" in model_name:
            # Check if it matches Ollama pattern like "llama3.2:70b" or "llama3:70b"
            import re

            if re.match(r"^llama3(\.\d+)?:\d+[bB]?$", model_name):
                # This is an Ollama model, skip to Ollama detection below
                pass
            else:
                # Check other OpenRouter indicators
                if any(indicator in model_lower for indicator in openrouter_indicators):
                    return "openrouter"
        elif any(indicator in model_lower for indicator in openrouter_indicators):
            return "openrouter"

        # Check for Ollama model patterns (contains colon but not OpenRouter patterns)
        if ":" in model_name:
            return "ollama"

        # Check for cloud providers
        if model_lower.startswith("deepseek-"):
            return "deepseek"
        elif model_lower.startswith("claude-") or model_lower == "claude":
            return "anthropic"
        else:
            return "ollama"
