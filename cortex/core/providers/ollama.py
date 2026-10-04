"""Ollama provider for local models."""

import os
from typing import Dict, Any, List, Iterator, Optional

from .base import ModelProvider, ProviderError

# Cortex sends about 7,000 tokens (tool definitions and system prompt) before the user's first
# word. When no window is requested Ollama applies its own small default and silently drops the
# oldest messages, system prompt included, so a window is always requested explicitly.
DEFAULT_NUM_CTX = 32768
NUM_CTX_ENV = "CORTEX_OLLAMA_NUM_CTX"


def _positive_int(value: Any) -> Optional[int]:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


class OllamaProvider(ModelProvider):
    """Provider for local Ollama models"""

    def __init__(self):
        try:
            import ollama

            self.ollama = ollama
        except ImportError:
            raise ProviderError("Ollama package not installed. Install with: pip install ollama")
        self.num_ctx = self._resolve_num_ctx(None)

    @staticmethod
    def _resolve_num_ctx(configured: Any) -> int:
        """Environment variable, then the config value, then the default; unusable values skipped."""
        return (
            _positive_int(os.environ.get(NUM_CTX_ENV))
            or _positive_int(configured)
            or DEFAULT_NUM_CTX
        )

    def configure(self, options: Optional[Dict[str, Any]] = None) -> None:
        self.num_ctx = self._resolve_num_ctx((options or {}).get("num_ctx"))

    @property
    def context_window(self) -> Optional[int]:
        return self.num_ctx

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
            kwargs = {
                "model": model,
                "messages": sanitized_messages,
                "options": {"num_ctx": self.num_ctx},
            }
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
            kwargs = {
                "model": model,
                "messages": sanitized_messages,
                "stream": True,
                "options": {"num_ctx": self.num_ctx},
            }
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
            message = response.get("message", {})

            # Try common thinking field names
            thinking = message.get("thinking") or message.get("reasoning")
            if thinking:
                return thinking

            # Some models might have thinking in content field
            content = message.get("content", "")
            if content and isinstance(content, str):
                # Check if content starts with thinking tags or patterns
                stripped = content.strip()
                if stripped.startswith("<thinking>") or stripped.startswith("<tool_call>"):
                    # This might be thinking content
                    return None  # Don't extract from content to avoid duplication

        # For non-dict responses (like ollama chat response object)
        elif hasattr(response, "get"):
            try:
                message = response.get("message", {})
                thinking = message.get("thinking") or message.get("reasoning")
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
            "deepseek-r1",
            "deepseek-reasoner",
            "reasoner",
            "thinking",
            "r1",
            "qwen2.5-32b-thought",
        ]
        return any(indicator in model_lower for indicator in thinking_indicators)
