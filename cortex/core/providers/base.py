"""Base provider classes and errors for model provider abstraction layer."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Iterator, Optional

from ...utils.encoding import sanitize_string, sanitize_object


class ProviderError(Exception):
    """Error related to model provider operations"""

    pass


def positive_int(value: Any) -> Optional[int]:
    """``value`` as a positive integer, or None when it is not one (unset, text, zero, negative)."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


class ModelProvider(ABC):
    """Abstract base class for model providers"""

    # The configuration section (``ollama``, ``openai``) handed to configure(); None for providers
    # with nothing to configure
    config_section: Optional[str] = None

    @abstractmethod
    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Send a chat request to the model.

        Args:
            model: Model name
            messages: Conversation history
            tools: Optional list of tool definitions

        Returns:
            Response dictionary with 'message' key containing assistant response
        """
        pass

    @abstractmethod
    def stream_chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Stream chat responses from the model.

        Args:
            model: Model name
            messages: Conversation history
            tools: Optional list of tool definitions

        Yields:
            Response chunks
        """
        pass

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Check if provider supports streaming"""
        pass

    @abstractmethod
    def normalize_model_name(self, model: str) -> str:
        """Normalize model name for this provider"""
        pass

    @abstractmethod
    def validate_api_key(self) -> bool:
        """Validate that API key is set (for cloud providers)"""
        pass

    @property
    def context_window(self) -> Optional[int]:
        """Tokens of context the server really gives the model, when the provider fixes it.

        None means the provider does not fix a window (a cloud API with its own limits).
        """
        return None

    def configure(self, options: Optional[Dict[str, Any]] = None) -> None:
        """Apply provider-specific settings from the configuration (default: none to apply)."""

    def window_advice(self, needed: int) -> str:
        """What to change when the context window is too small for Cortex (used in a warning)."""
        return f"Give the model a context window of at least {needed} tokens"

    def _sanitize_request(self, messages, tools=None):
        """Sanitize messages and tools to remove invalid UTF-8 characters."""
        sanitized_messages = sanitize_object(messages)
        sanitized_tools = sanitize_object(tools) if tools else None
        return sanitized_messages, sanitized_tools

    def extract_thinking_content(self, response: Any) -> Optional[str]:
        """
        Extract thinking/reasoning content from provider response.

        Args:
            response: Raw provider response

        Returns:
            Thinking content string if available, None otherwise
        """
        return None

    def supports_thinking(self, model: str) -> bool:
        """
        Check if this model supports thinking process output.

        Args:
            model: Model name

        Returns:
            True if model can expose thinking content
        """
        return False
