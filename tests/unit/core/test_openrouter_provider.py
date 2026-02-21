"""Unit tests for OpenRouterProvider."""

import os
import pytest
from unittest.mock import MagicMock, patch
from cortex.core.providers import OpenRouterProvider, ProviderError, ProviderFactory
from cortex.config import AgentConfig


@pytest.fixture
def mock_openai_client():
    """Mocks the OpenAI client used by OpenRouterProvider."""
    with patch("openai.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        yield mock_client


@pytest.fixture(autouse=True)
def cleanup_env_vars():
    """Ensure environment variables are clean before and after tests."""
    old_api_key = os.getenv("OPENROUTER_API_KEY")
    old_referer = os.getenv("OPENROUTER_HTTP_REFERER")
    old_title = os.getenv("OPENROUTER_X_TITLE")

    if old_api_key:
        del os.environ["OPENROUTER_API_KEY"]
    if old_referer:
        del os.environ["OPENROUTER_HTTP_REFERER"]
    if old_title:
        del os.environ["OPENROUTER_X_TITLE"]

    yield

    if old_api_key:
        os.environ["OPENROUTER_API_KEY"] = old_api_key
    else:
        if "OPENROUTER_API_KEY" in os.environ:
            del os.environ["OPENROUTER_API_KEY"]

    if old_referer:
        os.environ["OPENROUTER_HTTP_REFERER"] = old_referer
    else:
        if "OPENROUTER_HTTP_REFERER" in os.environ:
            del os.environ["OPENROUTER_HTTP_REFERER"]

    if old_title:
        os.environ["OPENROUTER_X_TITLE"] = old_title
    else:
        if "OPENROUTER_X_TITLE" in os.environ:
            del os.environ["OPENROUTER_X_TITLE"]


class TestOpenRouterProvider:
    def test_initialization_success(self, mock_openai_client):
        """Test OpenRouterProvider initializes successfully with API key."""
        os.environ["OPENROUTER_API_KEY"] = "test_api_key"
        provider = OpenRouterProvider()
        assert provider.client == mock_openai_client
        mock_openai_client.chat.completions.create.assert_not_called()

    def test_initialization_no_api_key(self):
        """Test OpenRouterProvider raises error if API key is not set."""
        with pytest.raises(ProviderError, match="OPENROUTER_API_KEY environment variable not set."):
            OpenRouterProvider()

    def test_chat_success(self, mock_openai_client):
        """Test the chat method for successful response."""
        os.environ["OPENROUTER_API_KEY"] = "test_api_key"
        provider = OpenRouterProvider()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock(role="assistant", content="Mocked OpenRouter response")
        mock_response.choices[0].message.tool_calls = [] # No tool calls
        mock_openai_client.chat.completions.create.return_value = mock_response

        messages = [{"role": "user", "content": "Hello"}]
        tools = [{"name": "test_tool"}]
        response = provider.chat("devstral-2512", messages, tools)

        mock_openai_client.chat.completions.create.assert_called_once_with(
            model="devstral-2512",
            messages=messages,
            tools=tools
        )
        assert response["message"]["role"] == "assistant"
        assert response["message"]["content"] == "Mocked OpenRouter response"
        assert "tool_calls" not in response["message"]

    def test_chat_with_tool_calls(self, mock_openai_client):
        """Test chat method when model returns tool calls."""
        os.environ["OPENROUTER_API_KEY"] = "test_api_key"
        provider = OpenRouterProvider()

        mock_tool_call_obj = MagicMock(id="call_1")
        mock_tool_call_obj.function = MagicMock()
        mock_tool_call_obj.function.name = "test_tool"
        mock_tool_call_obj.function.arguments = '{"param": "value"}'
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock(role="assistant", content=None, tool_calls=[mock_tool_call_obj])
        mock_openai_client.chat.completions.create.return_value = mock_response

        messages = [{"role": "user", "content": "Use tool"}]
        response = provider.chat("devstral-2512", messages)

        assert response["message"]["role"] == "assistant"
        assert response["message"]["content"] == ""
        assert len(response["message"]["tool_calls"]) == 1
        assert response["message"]["tool_calls"][0]["function"]["name"] == "test_tool"
        assert response["message"]["tool_calls"][0]["function"]["arguments"] == '{"param": "value"}'

    def test_stream_chat_success(self, mock_openai_client):
        """Test the stream_chat method for successful streaming response."""
        os.environ["OPENROUTER_API_KEY"] = "test_api_key"
        provider = OpenRouterProvider()

        # Mock stream chunks
        chunk1 = MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello ", tool_calls=[]))])
        chunk2 = MagicMock(choices=[MagicMock(delta=MagicMock(content="World", tool_calls=[]))])
        mock_openai_client.chat.completions.create.return_value = [chunk1, chunk2]

        messages = [{"role": "user", "content": "Stream response"}]
        stream_gen = provider.stream_chat("devstral-2512", messages)

        chunks = list(stream_gen)
        assert len(chunks) == 2
        assert chunks[0]["message"]["content"] == "Hello "
        assert chunks[1]["message"]["content"] == "World"

    def test_stream_chat_with_tool_calls(self, mock_openai_client):
        """Test stream_chat method handles streaming tool calls."""
        os.environ["OPENROUTER_API_KEY"] = "test_api_key"
        provider = OpenRouterProvider()

        mock_tool_call_delta = MagicMock(
            function=MagicMock(),
            id="call_stream_1", index=0, type="function"
        )
        mock_tool_call_delta.function.name = "test_tool_stream"
        mock_tool_call_delta.function.arguments = '{"param": "value"}'
        chunk_tool = MagicMock(choices=[MagicMock(delta=MagicMock(content=None, tool_calls=[mock_tool_call_delta]))])
        mock_openai_client.chat.completions.create.return_value = [chunk_tool]

        messages = [{"role": "user", "content": "Stream tool call"}]
        stream_gen = provider.stream_chat("devstral-2512", messages)

        chunks = list(stream_gen)
        assert len(chunks) == 1
        assert "tool_calls" in chunks[0]["message"]
        assert chunks[0]["message"]["tool_calls"][0]["function"]["name"] == "test_tool_stream"


    def test_supports_streaming(self):
        """Test supports_streaming returns True."""
        os.environ["OPENROUTER_API_KEY"] = "test_api_key"
        provider = OpenRouterProvider()
        assert provider.supports_streaming() is True

    def test_normalize_model_name(self):
        """Test normalize_model_name returns model name as-is."""
        os.environ["OPENROUTER_API_KEY"] = "test_api_key"
        provider = OpenRouterProvider()
        assert provider.normalize_model_name("devstral-2512") == "devstral-2512"
        assert provider.normalize_model_name("openrouter/test-model") == "openrouter/test-model"

    def test_validate_api_key_set(self):
        """Test validate_api_key returns True when API key is set."""
        os.environ["OPENROUTER_API_KEY"] = "test_api_key"
        provider = OpenRouterProvider()
        assert provider.validate_api_key() is True

class TestProviderFactoryOpenRouter:
    @pytest.fixture(autouse=True)
    def reset_provider_factory(self):
        """Ensure ProviderFactory is clean before each test."""
        # No specific reset needed for ProviderFactory as it uses static methods,
        # but cleanup_env_vars fixture already handles API keys.
        pass

    def test_get_provider_by_model_name_devstral(self):
        """Test ProviderFactory gets OpenRouterProvider for devstral models."""
        os.environ["OPENROUTER_API_KEY"] = "dummy_key"
        provider = ProviderFactory.get_provider("devstral-2512")
        assert isinstance(provider, OpenRouterProvider)

    def test_get_provider_by_model_name_explicit_openrouter(self):
        """Test ProviderFactory gets OpenRouterProvider when 'openrouter' is in model name."""
        os.environ["OPENROUTER_API_KEY"] = "dummy_key"
        provider = ProviderFactory.get_provider("openrouter/another-model")
        assert isinstance(provider, OpenRouterProvider)

    def test_get_provider_by_override(self):
        """Test ProviderFactory gets OpenRouterProvider by explicit override."""
        os.environ["OPENROUTER_API_KEY"] = "dummy_key"
        provider = ProviderFactory.get_provider("any-model", provider_override="openrouter")
        assert isinstance(provider, OpenRouterProvider)

    def test_create_provider_by_name(self):
        """Test _create_provider_by_name instantiates OpenRouterProvider."""
        os.environ["OPENROUTER_API_KEY"] = "dummy_key"
        provider = ProviderFactory._create_provider_by_name("openrouter")
        assert isinstance(provider, OpenRouterProvider)

    def test_is_cloud_provider_openrouter(self):
        """Test is_cloud_provider identifies OpenRouter models as cloud."""
        assert ProviderFactory.is_cloud_provider("devstral-2512") is True
        assert ProviderFactory.is_cloud_provider("openrouter/test-model") is True
        # Ensure it doesn't incorrectly identify ollama models
        assert ProviderFactory.is_cloud_provider("ollama/devstral:latest") is False

    def test_get_provider_name_openrouter(self):
        """Test get_provider_name returns 'openrouter' for OpenRouter models."""
        assert ProviderFactory.get_provider_name("devstral-2512") == "openrouter"
        assert ProviderFactory.get_provider_name("openrouter/test-model") == "openrouter"
