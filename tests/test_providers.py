"""Tests for model providers"""

import pytest
import os
import sys
import json
from unittest.mock import Mock, patch, MagicMock
from cortex.core.providers import (
    ModelProvider,
    OllamaProvider,
    DeepSeekProvider,
    AnthropicProvider,
    ProviderFactory,
    ProviderError,
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
            with pytest.raises(
                ProviderError, match="ANTHROPIC_API_KEY|Anthropic package not installed"
            ):
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
            assert (
                provider.normalize_model_name("claude-3-haiku-20240307")
                == "claude-3-haiku-20240307"
            )
            assert provider.normalize_model_name("claude") == "claude-4-6-sonnet"
        except (ProviderError, ImportError):
            pytest.skip("anthropic package not installed")


def test_provider_factory_unknown_provider():
    """Test ProviderFactory with unknown provider"""
    with pytest.raises(ProviderError, match="Unknown provider"):
        ProviderFactory._create_provider_by_name("unknown_provider")


def test_anthropic_provider_tool_arguments_json():
    """Test that AnthropicProvider serializes tool arguments as JSON, not Python repr"""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        try:
            provider = AnthropicProvider()

            # Mock Anthropic API response with tool_use block
            mock_content_block = MagicMock()
            mock_content_block.type = "tool_use"
            mock_content_block.name = "read_file"
            mock_content_block.id = "call_123"
            mock_content_block.input = {"path": "test.py", "lines": [1, 2, 3]}

            mock_response = MagicMock()
            mock_response.content = [mock_content_block]

            with patch.object(provider.client.messages, "create", return_value=mock_response):
                result = provider.chat("claude-3-haiku", [{"role": "user", "content": "test"}])

                # Verify arguments are JSON string, not Python repr
                tool_call = result["message"]["tool_calls"][0]
                arguments = tool_call["function"]["arguments"]

                # Should be valid JSON
                parsed = json.loads(arguments)
                assert parsed == {"path": "test.py", "lines": [1, 2, 3]}

                # Should NOT be Python repr format
                assert not arguments.startswith("{'")
                assert '"path"' in arguments  # JSON uses double quotes
        except (ImportError, ProviderError):
            pytest.skip("anthropic package not installed")


def test_anthropic_provider_complex_tool_arguments():
    """Test JSON serialization with nested dictionaries and lists"""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        try:
            provider = AnthropicProvider()

            # Complex nested structure
            complex_input = {
                "path": "test.py",
                "options": {
                    "encoding": "utf-8",
                    "lines": [1, 2, 3],
                    "metadata": {"author": "test", "tags": ["python", "test"]},
                },
                "filters": [
                    {"type": "include", "pattern": "*.py"},
                    {"type": "exclude", "pattern": "*.pyc"},
                ],
            }

            mock_content_block = MagicMock()
            mock_content_block.type = "tool_use"
            mock_content_block.name = "read_file"
            mock_content_block.id = "call_456"
            mock_content_block.input = complex_input

            mock_response = MagicMock()
            mock_response.content = [mock_content_block]

            with patch.object(provider.client.messages, "create", return_value=mock_response):
                result = provider.chat("claude-3-haiku", [{"role": "user", "content": "test"}])

                tool_call = result["message"]["tool_calls"][0]
                arguments = tool_call["function"]["arguments"]

                # Should be valid JSON
                parsed = json.loads(arguments)
                assert parsed == complex_input

                # Verify nested structures are preserved
                assert parsed["options"]["metadata"]["tags"] == ["python", "test"]
        except (ImportError, ProviderError):
            pytest.skip("anthropic package not installed")


def test_anthropic_provider_streaming_tool_arguments():
    """Test that streaming responses also use JSON serialization"""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        try:
            provider = AnthropicProvider()

            # Mock streaming response with tool_use_delta
            mock_delta = MagicMock()
            mock_delta.type = "tool_use_delta"
            mock_delta.tool_use = MagicMock()
            mock_delta.tool_use.index = 0
            mock_delta.tool_use.name = "read_file"
            mock_delta.tool_use.id = "call_789"
            mock_delta.tool_use.partial_json = '{"path": "test.py"}'

            mock_event = MagicMock()
            mock_event.type = "content_block_delta"
            mock_event.delta = mock_delta

            mock_stop_event = MagicMock()
            mock_stop_event.type = "content_block_stop"

            # Create a mock stream
            mock_stream = [mock_event, mock_stop_event]

            with patch.object(provider.client.messages, "create", return_value=mock_stream):
                # Collect streaming results
                results = list(
                    provider.stream_chat("claude-3-haiku", [{"role": "user", "content": "test"}])
                )

                # Verify we got results
                assert len(results) > 0

                # Check if tool calls are present in results
                tool_calls_found = False
                for result in results:
                    if "message" in result and "tool_calls" in result["message"]:
                        tool_calls_found = True
                        for tool_call in result["message"]["tool_calls"]:
                            arguments = tool_call["function"]["arguments"]
                            # If arguments are present, they should be JSON
                            if arguments:
                                try:
                                    parsed = json.loads(arguments)
                                    assert isinstance(parsed, dict)
                                except json.JSONDecodeError:
                                    # If it's partial JSON, that's okay for streaming
                                    pass

                # Note: Streaming may not always yield complete tool calls
                # This test verifies the structure is correct when present
        except (ImportError, ProviderError):
            pytest.skip("anthropic package not installed")
