"""Model provider abstraction layer for supporting multiple LLM APIs"""

import os
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Iterator, Optional
import logging

logger = logging.getLogger(__name__)

from ..utils.encoding import sanitize_string, sanitize_object

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


class DeepSeekProvider(ModelProvider):
    """Provider for DeepSeek cloud API (OpenAI-compatible)"""

    def __init__(self):
        try:
            from openai import OpenAI

            self.client_class = OpenAI
        except ImportError:
            raise ProviderError("OpenAI package not installed. Install with: pip install openai")

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ProviderError(
                "DEEPSEEK_API_KEY environment variable not set. "
                "Get your API key from https://platform.deepseek.com/"
            )

        self.client = self.client_class(api_key=api_key, base_url="https://api.deepseek.com")

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Call DeepSeek API"""
        try:
            # Sanitize messages and tools to remove invalid UTF-8 characters
            sanitized_messages, sanitized_tools = self._sanitize_request(messages, tools)
            kwargs = {"model": model, "messages": sanitized_messages}
            if sanitized_tools:
                kwargs["tools"] = sanitized_tools

            response = self.client.chat.completions.create(**kwargs)

            # Convert OpenAI format to Ollama-compatible format
            message = response.choices[0].message

            result = {"message": {"role": message.role, "content": message.content}}

            # Handle reasoning_content (required for DeepSeek thinking mode)
            if hasattr(message, "reasoning_content") and message.reasoning_content:
                result["message"]["reasoning_content"] = message.reasoning_content

            # Handle tool calls
            if hasattr(message, "tool_calls") and message.tool_calls:
                result["message"]["tool_calls"] = [
                    {
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        "id": tc.id,
                        "type": tc.type,
                    }
                    for tc in message.tool_calls
                ]

            return result
        except Exception as e:
            raise ProviderError(f"DeepSeek API error: {e}") from e

    def stream_chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Stream responses from DeepSeek API"""
        try:
            # Sanitize messages and tools to remove invalid UTF-8 characters
            sanitized_messages, sanitized_tools = self._sanitize_request(messages, tools)
            kwargs = {"model": model, "messages": sanitized_messages, "stream": True}
            if sanitized_tools:
                kwargs["tools"] = sanitized_tools

            stream = self.client.chat.completions.create(**kwargs)

            for chunk in stream:
                if chunk.choices:
                    choice = chunk.choices[0]
                    if choice.delta:
                        delta = choice.delta
                        result = {
                            "message": {
                                "role": delta.role or "assistant",
                                "content": delta.content or "",
                            }
                        }

                        # Handle reasoning_content in streaming (required for DeepSeek thinking mode)
                        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                            result["message"]["reasoning_content"] = delta.reasoning_content

                        # Handle tool calls in streaming
                        if hasattr(delta, "tool_calls") and delta.tool_calls:
                            result["message"]["tool_calls"] = [
                                {
                                    "function": {
                                        "name": tc.function.name if tc.function else None,
                                        "arguments": tc.function.arguments if tc.function else "",
                                    },
                                    "id": tc.id,
                                    "index": tc.index,
                                    "type": tc.type,
                                }
                                for tc in delta.tool_calls
                            ]

                        yield result
        except Exception as e:
            raise ProviderError(f"DeepSeek streaming error: {e}") from e

    def supports_streaming(self) -> bool:
        return True

    def normalize_model_name(self, model: str) -> str:
        """Normalize DeepSeek model names"""
        # DeepSeek models: deepseek-chat, deepseek-coder, deepseek-reasoner
        if model.startswith("deepseek-"):
            return model
        # If just "deepseek", default to "deepseek-chat"
        if model.lower() == "deepseek":
            return "deepseek-chat"
        return model

    def validate_api_key(self) -> bool:
        """Validate DeepSeek API key is set"""
        return os.getenv("DEEPSEEK_API_KEY") is not None


class AnthropicProvider(ModelProvider):
    """Provider for Anthropic Claude API"""

    def __init__(self):
        try:
            import anthropic

            self.anthropic = anthropic
        except ImportError:
            raise ProviderError(
                "Anthropic package not installed. Install with: pip install anthropic"
            )

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ProviderError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Get your API key from https://console.anthropic.com/"
            )

        self.client = self.anthropic.Anthropic(api_key=api_key)

    def _convert_tools_to_anthropic_format(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert Ollama tool format to Anthropic format"""
        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                anthropic_tools.append(
                    {
                        "name": func.get("name"),
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    }
                )
        return anthropic_tools

    def _convert_messages_to_anthropic_format(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert messages to Anthropic format"""
        anthropic_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            # Anthropic uses "user" and "assistant" roles
            if role == "system":
                # System messages are handled separately in Anthropic
                continue

            anthropic_msg = {
                "role": role if role in ["user", "assistant"] else "user",
                "content": content,
            }
            anthropic_messages.append(anthropic_msg)

        return anthropic_messages

    def _extract_system_prompt(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Extract system prompt from messages"""
        for msg in messages:
            if msg.get("role") == "system":
                return msg.get("content", "")
        return None

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Call Anthropic API"""
        try:
            # Sanitize messages and tools to remove invalid UTF-8 characters
            sanitized_messages, sanitized_tools = self._sanitize_request(messages, tools)
            # Extract system prompt
            system_prompt = self._extract_system_prompt(sanitized_messages)
            anthropic_messages = self._convert_messages_to_anthropic_format(sanitized_messages)

            kwargs = {"model": model, "messages": anthropic_messages, "max_tokens": 4096}

            if system_prompt:
                kwargs["system"] = system_prompt

            if sanitized_tools:
                anthropic_tools = self._convert_tools_to_anthropic_format(sanitized_tools)
                kwargs["tools"] = anthropic_tools

            response = self.client.messages.create(**kwargs)

            # Convert Anthropic format to Ollama-compatible format
            result = {"message": {"role": "assistant", "content": ""}}

            # Handle content (can be list of text blocks or tool use blocks)
            content_parts = []
            tool_calls = []

            for content_block in response.content:
                if content_block.type == "text":
                    content_parts.append(content_block.text)
                elif content_block.type == "tool_use":
                    tool_calls.append(
                        {
                            "function": {
                                "name": content_block.name,
                                "arguments": json.dumps(
                                    content_block.input
                                ),  # Anthropic uses dict, convert to JSON string
                            },
                            "id": content_block.id,
                            "type": "function",
                        }
                    )

            if content_parts:
                result["message"]["content"] = "".join(content_parts)

            if tool_calls:
                result["message"]["tool_calls"] = tool_calls

            return result
        except Exception as e:
            raise ProviderError(f"Anthropic API error: {e}") from e

    def stream_chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Stream responses from Anthropic API"""
        try:
            # Sanitize messages and tools to remove invalid UTF-8 characters
            sanitized_messages, sanitized_tools = self._sanitize_request(messages, tools)
            system_prompt = self._extract_system_prompt(sanitized_messages)
            anthropic_messages = self._convert_messages_to_anthropic_format(sanitized_messages)

            kwargs = {
                "model": model,
                "messages": anthropic_messages,
                "max_tokens": 4096,
                "stream": True,
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            if sanitized_tools:
                anthropic_tools = self._convert_tools_to_anthropic_format(sanitized_tools)
                kwargs["tools"] = anthropic_tools

            stream = self.client.messages.create(**kwargs)

            current_content = ""
            current_tool_calls = {}

            for event in stream:
                if event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        current_content += delta.text
                        yield {"message": {"role": "assistant", "content": current_content}}
                    elif delta.type == "tool_use_delta":
                        # Handle tool use deltas
                        tool_use = delta.tool_use
                        if tool_use.index not in current_tool_calls:
                            current_tool_calls[tool_use.index] = {
                                "function": {"name": "", "arguments": ""},
                                "id": "",
                                "type": "function",
                            }

                        if tool_use.name:
                            current_tool_calls[tool_use.index]["function"]["name"] = tool_use.name
                        if tool_use.id:
                            current_tool_calls[tool_use.index]["id"] = tool_use.id
                        if tool_use.partial_json:
                            current_tool_calls[tool_use.index]["function"][
                                "arguments"
                            ] = tool_use.partial_json

                elif event.type == "content_block_stop":
                    # Finalize tool calls
                    if current_tool_calls:
                        yield {
                            "message": {
                                "role": "assistant",
                                "tool_calls": list(current_tool_calls.values()),
                            }
                        }
        except Exception as e:
            raise ProviderError(f"Anthropic streaming error: {e}") from e

    def supports_streaming(self) -> bool:
        return True

    def normalize_model_name(self, model: str) -> str:
        """Normalize Anthropic model names"""
        # Anthropic models: claude-3-5-sonnet-20241022, claude-3-haiku-20240307, etc.
        if model.startswith("claude-"):
            return model
        # If just "claude", default to latest sonnet
        if model.lower() == "claude":
            return "claude-3-5-sonnet-20241022"
        return model

    def validate_api_key(self) -> bool:
        """Validate Anthropic API key is set"""
        return os.getenv("ANTHROPIC_API_KEY") is not None


class OpenRouterProvider(ModelProvider):
    """Provider for OpenRouter (OpenAI-compatible)"""

    def __init__(self):
        try:
            from openai import OpenAI

            self.client_class = OpenAI
        except ImportError:
            raise ProviderError("OpenAI package not installed. Install with: pip install openai")

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ProviderError(
                "OPENROUTER_API_KEY environment variable not set. "
                "Get your API key from https://openrouter.ai/ and set it."
            )

        self.client = self.client_class(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                # Optional: For rankings on openrouter.ai, if applicable
                "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost:8000"),
                "X-Title": os.getenv("OPENROUTER_X_TITLE", "Cortex CLI"),
            }
        )

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Call OpenRouter API"""
        try:
            # OpenRouter expects OpenAI-compatible messages and tool definitions
            sanitized_messages, sanitized_tools = self._sanitize_request(messages, tools)

            kwargs = {"model": model, "messages": sanitized_messages}
            if sanitized_tools:
                kwargs["tools"] = sanitized_tools

            response = self.client.chat.completions.create(**kwargs)

            # Convert OpenAI format to Cortex internal format
            message = response.choices[0].message
            result = {"message": {"role": message.role, "content": message.content or ""}}

            if hasattr(message, "tool_calls") and message.tool_calls:
                result["message"]["tool_calls"] = [
                    {
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        "id": tc.id,
                        "type": tc.type,
                    }
                    for tc in message.tool_calls
                ]
            return result
        except Exception as e:
            raise ProviderError(f"OpenRouter API error: {e}") from e

    def stream_chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Stream responses from OpenRouter API"""
        try:
            sanitized_messages, sanitized_tools = self._sanitize_request(messages, tools)

            kwargs = {"model": model, "messages": sanitized_messages, "stream": True}
            if sanitized_tools:
                kwargs["tools"] = sanitized_tools

            stream = self.client.chat.completions.create(**kwargs)

            for chunk in stream:
                if chunk.choices:
                    choice = chunk.choices[0]
                    if choice.delta:
                        delta = choice.delta
                        result = {
                            "message": {
                                "role": delta.role or "assistant",
                                "content": delta.content or "",
                            }
                        }
                        if hasattr(delta, "tool_calls") and delta.tool_calls:
                            result["message"]["tool_calls"] = [
                                {
                                    "function": {
                                        "name": tc.function.name if tc.function else None,
                                        "arguments": tc.function.arguments if tc.function else "",
                                    },
                                    "id": tc.id,
                                    "index": tc.index,
                                    "type": tc.type,
                                }
                                for tc in delta.tool_calls
                            ]
                        yield result
        except Exception as e:
            raise ProviderError(f"OpenRouter streaming error: {e}") from e

    def supports_streaming(self) -> bool:
        return True

    def normalize_model_name(self, model: str) -> str:
        """OpenRouter model names are used as-is"""
        return model

    def validate_api_key(self) -> bool:
        """Validate OpenRouter API key is set"""
        return os.getenv("OPENROUTER_API_KEY") is not None


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

        # Check for OpenRouter models first
        # Check for OpenRouter models first (including models with colons)
        openrouter_indicators = [
            "devstral", "openrouter/", "nvidia/", ":free", ":paid",
            "mistralai/", "google/", "anthropic/", "meta-llama/",
            "perplexity/", "cohere/", "jamba/", "qwen/", "llama3"
        ]
        
        # Special case: if model contains "llama3" but looks like Ollama format, it's Ollama
        if "llama3" in model_lower and ":" in model_name:
            # Check if it matches Ollama pattern like "llama3.2:70b" or "llama3:70b"
            import re
            if re.match(r'^llama3(\.\d+)?:\d+[bB]?$', model_name):
                # This is an Ollama model, skip to Ollama detection below
                # Don't return here, let it fall through
                pass
            else:
                # Check other OpenRouter indicators (excluding llama3)
                other_indicators = [indicator for indicator in openrouter_indicators if indicator != "llama3"]
                if any(indicator in model_lower for indicator in other_indicators):
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
        
        # Check for OpenRouter indicators first (including models with colons)
        openrouter_indicators = [
            "devstral", "openrouter/", "nvidia/", ":free", ":paid",
            "mistralai/", "google/", "anthropic/", "meta-llama/",
            "perplexity/", "cohere/", "jamba/", "qwen/", "llama3"
        ]
        if any(indicator in model_lower for indicator in openrouter_indicators):
            return True
        
        # Check for other cloud providers
        if model_lower.startswith("deepseek-"):
            return True
        if model_lower.startswith("claude-") or model_lower == "claude":
            return True
        
        # Ollama models (local) - contain colons but not cloud indicators
        if ":" in model_name:
            return False
        
        return False

    @staticmethod
    def get_provider_name(model_name: str) -> str:
        """Get provider name for a model"""
        model_lower = model_name.lower()

        # Check for OpenRouter models first (including models with colons)
        openrouter_indicators = [
            "devstral", "openrouter/", "nvidia/", ":free", ":paid",
            "mistralai/", "google/", "anthropic/", "meta-llama/",
            "perplexity/", "cohere/", "jamba/", "qwen/", "llama3"
        ]
        
        # Special case: if model contains "llama3" but looks like Ollama format, it's Ollama
        if "llama3" in model_lower and ":" in model_name:
            # Check if it matches Ollama pattern like "llama3.2:70b" or "llama3:70b"
            import re
            if re.match(r'^llama3(\.\d+)?:\d+[bB]?$', model_name):
                # This is an Ollama model, skip to Ollama detection below
                pass
            else:
                # Check other OpenRouter indicators (excluding llama3)
                other_indicators = [indicator for indicator in openrouter_indicators if indicator != "llama3"]
                if any(indicator in model_lower for indicator in other_indicators):
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
