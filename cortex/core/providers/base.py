"""Base provider classes and errors for model provider abstraction layer."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Iterator, Optional

from ...utils.encoding import sanitize_string, sanitize_object


class ProviderError(Exception):
    """Error related to model provider operations"""

    pass


class ModelProvider(ABC):
    """Abstract base class for model providers"""

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
