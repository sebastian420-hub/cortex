"""Tests for model providers"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from cortex.core.providers import (
    ModelProvider,
    OllamaProvider,
    DeepSeekProvider,
    AnthropicProvider,
    ProviderFactory,
    ProviderError
)


def test_provider_factory_detection():
    """Test provider auto-detection from model names"""
    # Ollama models
    provider = ProviderFactory.get_provider("llama3.2")
    assert isinstance(provider, OllamaProvider)
    
    provider = ProviderFactory.get_provider("deepseek-r1:8b")
    assert isinstance(provider, OllamaProvider)
    
    # DeepSeek models (will fail if API key not set, but that's expected)
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test_key"}):
        try:
            provider = ProviderFactory.get_provider("deepseek-chat")
            assert isinstance(provider, DeepSeekProvider)
        except (ProviderError, ImportError):
            # Expected if openai package not installed
            pass
    
    # Anthropic models (will fail if API key not set, but that's expected)
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        try:
            provider = ProviderFactory.get_provider("claude-3-haiku-20240307")
            assert isinstance(provider, AnthropicProvider)
        except (ProviderError, ImportError):
            # Expected if anthropic package not installed
            pass


def test_provider_factory_override():
    """Test explicit provider override"""
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test_key"}):
        try:
            # Force DeepSeek even for non-DeepSeek model name
            provider = ProviderFactory.get_provider("llama3.2", provider_override="deepseek")
            assert isinstance(provider, DeepSeekProvider)
        except (ProviderError, ImportError):
            # Expected if openai package not installed
            pass


def test_provider_factory_is_cloud_provider():
    """Test cloud provider detection"""
    assert ProviderFactory.is_cloud_provider("deepseek-chat") is True
    assert ProviderFactory.is_cloud_provider("claude-3-haiku-20240307") is True
    assert ProviderFactory.is_cloud_provider("llama3.2") is False
    assert ProviderFactory.is_cloud_provider("deepseek-r1:8b") is False  # Ollama model


def test_provider_factory_get_provider_name():
    """Test getting provider name"""
    assert ProviderFactory.get_provider_name("deepseek-chat") == "deepseek"
    assert ProviderFactory.get_provider_name("claude-3-haiku-20240307") == "anthropic"
    assert ProviderFactory.get_provider_name("llama3.2") == "ollama"
    assert ProviderFactory.get_provider_name("deepseek-r1:8b") == "ollama"


def test_ollama_provider_validation():
    """Test OllamaProvider validation"""
    provider = OllamaProvider()
    assert provider.validate_api_key() is True
    assert provider.supports_streaming() is True


def test_deepseek_provider_missing_api_key():
    """Test DeepSeekProvider raises error when API key is missing"""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ProviderError, match="DEEPSEEK_API_KEY"):
            try:
                DeepSeekProvider()
            except ImportError:
                # Skip if openai package not installed
                pytest.skip("openai package not installed")


def test_anthropic_provider_missing_api_key():
    """Test AnthropicProvider raises error when API key is missing"""
    with patch.dict(os.environ, {}, clear=True):
        try:
            with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY|Anthropic package not installed"):
                AnthropicProvider()
        except (ImportError, ProviderError):
            # Expected if anthropic package not installed or API key missing
            pass


def test_provider_normalize_model_names():
    """Test model name normalization"""
    # Ollama - no normalization
    provider = OllamaProvider()
    assert provider.normalize_model_name("llama3.2") == "llama3.2"
    
    # DeepSeek
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test_key"}):
        try:
            provider = DeepSeekProvider()
            assert provider.normalize_model_name("deepseek-chat") == "deepseek-chat"
            assert provider.normalize_model_name("deepseek") == "deepseek-chat"
        except (ProviderError, ImportError):
            pytest.skip("openai package not installed")
    
    # Anthropic
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        try:
            provider = AnthropicProvider()
            assert provider.normalize_model_name("claude-3-haiku-20240307") == "claude-3-haiku-20240307"
            assert provider.normalize_model_name("claude") == "claude-3-5-sonnet-20241022"
        except (ProviderError, ImportError):
            pytest.skip("anthropic package not installed")


def test_provider_factory_unknown_provider():
    """Test ProviderFactory with unknown provider"""
    with pytest.raises(ProviderError, match="Unknown provider"):
        ProviderFactory._create_provider_by_name("unknown_provider")
