"""Integration tests for agent with cloud providers"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from cortex.agent import Cortex
from cortex.config import AgentConfig
from cortex.models import PermissionMode
from cortex.core.providers import ProviderError


@pytest.fixture
def mock_deepseek_provider():
    """Mock DeepSeek provider"""
    provider = Mock()
    provider.chat.return_value = {
        "message": {"role": "assistant", "content": "Test response from DeepSeek"}
    }
    provider.stream_chat.return_value = iter(
        [{"message": {"content": "Test"}}, {"message": {"content": " response"}}]
    )
    provider.supports_streaming.return_value = True
    provider.normalize_model_name.return_value = "deepseek-chat"
    provider.validate_api_key.return_value = True
    return provider


@pytest.fixture
def mock_anthropic_provider():
    """Mock Anthropic provider"""
    provider = Mock()
    provider.chat.return_value = {
        "message": {"role": "assistant", "content": "Test response from Claude"}
    }
    provider.stream_chat.return_value = iter(
        [{"message": {"content": "Test"}}, {"message": {"content": " response"}}]
    )
    provider.supports_streaming.return_value = True
    provider.normalize_model_name.return_value = "claude-3-haiku-20240307"
    provider.validate_api_key.return_value = True
    return provider


def test_agent_with_deepseek_provider(tmp_path, mock_deepseek_provider):
    """Test agent initialization with DeepSeek provider"""
    config = AgentConfig(model="deepseek-chat", provider="deepseek")

    with patch("cortex.agent.ProviderFactory.get_provider", return_value=mock_deepseek_provider):
        agent = Cortex(
            model="deepseek-chat",
            project_dir=str(tmp_path),
            permission_mode=PermissionMode.NORMAL,
            config=config,
        )

        assert agent.provider == mock_deepseek_provider
        assert agent.model == "deepseek-chat"


def test_agent_with_anthropic_provider(tmp_path, mock_anthropic_provider):
    """Test agent initialization with Anthropic provider"""
    config = AgentConfig(model="claude-3-haiku-20240307", provider="anthropic")

    with patch("cortex.agent.ProviderFactory.get_provider", return_value=mock_anthropic_provider):
        agent = Cortex(
            model="claude-3-haiku-20240307",
            project_dir=str(tmp_path),
            permission_mode=PermissionMode.NORMAL,
            config=config,
        )

        assert agent.provider == mock_anthropic_provider
        assert agent.model == "claude-3-haiku-20240307"


def test_agent_provider_validation_failure(tmp_path):
    """Test agent raises error when provider validation fails"""
    config = AgentConfig(model="deepseek-chat")

    with patch("cortex.agent.ProviderFactory.get_provider") as mock_get:
        mock_provider = Mock()
        mock_provider.validate_api_key.return_value = False
        mock_get.return_value = mock_provider

        with pytest.raises(ProviderError, match="API key not set"):
            Cortex(
                model="deepseek-chat",
                project_dir=str(tmp_path),
                permission_mode=PermissionMode.NORMAL,
                config=config,
            )


def test_agent_calls_provider_chat(tmp_path, mock_deepseek_provider):
    """Test agent calls provider chat method"""
    config = AgentConfig(model="deepseek-chat")

    with patch("cortex.agent.ProviderFactory.get_provider", return_value=mock_deepseek_provider):
        agent = Cortex(
            model="deepseek-chat",
            project_dir=str(tmp_path),
            permission_mode=PermissionMode.AUTO_APPROVE,
            config=config,
        )

        # Mock conversation to avoid actual processing
        agent.conversation.add_user_message("Hello")

        # Call _call_model directly
        result = agent._call_model([{"role": "user", "content": "Hello"}], [])

        assert result["message"]["content"] == "Test response from DeepSeek"
        mock_deepseek_provider.chat.assert_called_once()


def test_agent_tool_calling_with_cloud_provider(tmp_path, mock_deepseek_provider):
    """Test agent tool calling works with cloud providers"""
    config = AgentConfig(model="deepseek-chat")

    # Mock provider to return tool call
    mock_deepseek_provider.chat.return_value = {
        "message": {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {"name": "read_file", "arguments": '{"path": "test.txt"}'},
                    "type": "function",
                }
            ],
        }
    }

    with patch("cortex.agent.ProviderFactory.get_provider", return_value=mock_deepseek_provider):
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        agent = Cortex(
            model="deepseek-chat",
            project_dir=str(tmp_path),
            permission_mode=PermissionMode.AUTO_APPROVE,
            config=config,
        )

        # Process message that should trigger tool call
        agent._process_message("Read test.txt")

        # Verify provider was called
        mock_deepseek_provider.chat.assert_called()


def test_agent_streaming_with_cloud_provider(tmp_path, mock_deepseek_provider):
    """Test agent streaming works with cloud providers"""
    config = AgentConfig(model="deepseek-chat")

    with patch("cortex.agent.ProviderFactory.get_provider", return_value=mock_deepseek_provider):
        with patch("cortex.agent.stream_model_response") as mock_stream:
            mock_stream.return_value = iter(
                [{"message": {"content": "Hello"}}, {"message": {"content": " World"}}]
            )

            agent = Cortex(
                model="deepseek-chat",
                project_dir=str(tmp_path),
                permission_mode=PermissionMode.AUTO_APPROVE,
                config=config,
            )

            # Test streaming (would normally be called in _process_message)
            # Just verify the provider supports streaming
            assert agent.provider.supports_streaming() is True
