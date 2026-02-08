"""Ollama provider for local models."""

from typing import Dict, Any, List, Iterator, Optional

from .base import ModelProvider, ProviderError


class OllamaProvider(ModelProvider):
    """Provider for local Ollama models"""

    def __init__(self):
        try:
            import ollama

            self.ollama = ollama
        except ImportError:
            raise ProviderError("Ollama package not installed. Install with: pip install ollama")

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Call Ollama chat API"""
        try:
            # Sanitize messages and tools to remove invalid UTF-8 characters
            sanitized_messages, sanitized_tools = self._sanitize_request(messages, tools)
            kwargs = {"model": model, "messages": sanitized_messages}
            if sanitized_tools:
                kwargs["tools"] = sanitized_tools

            return self.ollama.chat(**kwargs)
        except Exception as e:
            raise ProviderError(f"Ollama API error: {e}") from e

    def stream_chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Stream responses from Ollama"""
        try:
            # Sanitize messages and tools to remove invalid UTF-8 characters
            sanitized_messages, sanitized_tools = self._sanitize_request(messages, tools)
            kwargs = {"model": model, "messages": sanitized_messages, "stream": True}
            if sanitized_tools:
                kwargs["tools"] = sanitized_tools

            stream = self.ollama.chat(**kwargs)
            for chunk in stream:
                yield chunk
        except Exception as e:
            raise ProviderError(f"Ollama streaming error: {e}") from e

    def supports_streaming(self) -> bool:
        return True

    def normalize_model_name(self, model: str) -> str:
        """Ollama model names are used as-is"""
        return model

    def validate_api_key(self) -> bool:
        """Ollama doesn't need API keys"""
        return True

    def extract_thinking_content(self, response: Any) -> Optional[str]:
        """
        Extract thinking/reasoning content from Ollama response.

        Ollama models might return thinking in custom message fields.
        This is model-dependent and may require specific model configurations.
        """
        # Check for thinking in message object
        if isinstance(response, dict):
            message = response.get('message', {})

            # Try common thinking field names
            thinking = message.get('thinking') or message.get('reasoning')
            if thinking:
                return thinking

            # Some models might have thinking in content field
            content = message.get('content', '')
            if content and isinstance(content, str):
                # Check if content starts with thinking tags or patterns
                stripped = content.strip()
                if stripped.startswith("<thinking>") or stripped.startswith("<tool_call>"):
                    # This might be thinking content
                    return None  # Don't extract from content to avoid duplication

        # For non-dict responses (like ollama chat response object)
        elif hasattr(response, 'get'):
            try:
                message = response.get('message', {})
                thinking = message.get('thinking') or message.get('reasoning')
                if thinking:
                    return thinking
            except Exception:
                pass

        return None

    def supports_thinking(self, model: str) -> bool:
        """
        Check if Ollama model supports thinking process output.

        Some Ollama models like deepseek-r1 and specialized reasoning models
        may expose thinking content. This method identifies these models.
        """
        model_lower = model.lower()
        thinking_indicators = [
            "deepseek-r1", "deepseek-reasoner", "reasoner",
            "thinking", "r1", "qwen2.5-32b-thought"
        ]
        return any(indicator in model_lower for indicator in thinking_indicators)
