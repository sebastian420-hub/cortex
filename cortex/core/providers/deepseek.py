"""DeepSeek cloud API provider (OpenAI-compatible)."""

import os
from typing import Dict, Any, List, Iterator, Optional

from .base import ModelProvider, ProviderError


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

            # For deepseek-reasoner, ensure all assistant messages have reasoning_content
            if model == "deepseek-reasoner":
                sanitized_messages = self._ensure_reasoning_content(sanitized_messages)

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

    def _ensure_reasoning_content(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ensure all assistant messages have reasoning_content field.

        DeepSeek reasoner model requires reasoning_content in all assistant messages.
        This adds an empty string for messages that don't have it (e.g., from other models).
        """
        result = []
        for msg in messages:
            if msg.get("role") == "assistant":
                # Copy the message and add reasoning_content if missing
                new_msg = msg.copy()
                if "reasoning_content" not in new_msg:
                    new_msg["reasoning_content"] = ""
                result.append(new_msg)
            else:
                result.append(msg)
        return result

    def normalize_model_name(self, model: str) -> str:
        """Normalize DeepSeek model names"""
        # DeepSeek models: deepseek-chat, deepseek-coder, deepseek-reasoner
        if model.startswith("deepseek-"):
            return model
        # If just "deepseek", default to "deepseek-chat"
        if model.lower() == "deepseek":
            return "deepseek-chat"
        return model

    def extract_thinking_content(self, response: Any) -> Optional[str]:
        """
        Extract thinking/reasoning content from DeepSeek response.

        DeepSeek returns reasoning_content field in message object.
        """
        # For non-streaming responses
        if hasattr(response, "choices") and response.choices:
            message = response.choices[0].message
            if hasattr(message, "reasoning_content") and message.reasoning_content:
                return message.reasoning_content
        # For streaming chunks (delta)
        elif (
            hasattr(response, "choices")
            and response.choices
            and hasattr(response.choices[0], "delta")
        ):
            delta = response.choices[0].delta
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                return delta.reasoning_content
        return None

    def supports_thinking(self, model: str) -> bool:
        """
        Check if DeepSeek model supports thinking process output.

        DeepSeek reasoner models expose reasoning_content.
        Some other DeepSeek models may also support it.
        """
        model_lower = model.lower()
        return "reasoner" in model_lower or "deepseek" in model_lower

    def validate_api_key(self) -> bool:
        """Validate DeepSeek API key is set"""
        return os.getenv("DEEPSEEK_API_KEY") is not None
