"""Anthropic Claude API provider."""

import os
import json
from typing import Dict, Any, List, Iterator, Optional

from .base import ModelProvider, ProviderError


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
        # Anthropic models: claude-4-6-sonnet, claude-3-5-sonnet-20241022, etc.
        if model.startswith("claude-"):
            return model
        # If just "claude", default to latest sonnet
        if model.lower() == "claude":
            return "claude-4-6-sonnet"
        return model

    def validate_api_key(self) -> bool:
        """Validate Anthropic API key is set"""
        return os.getenv("ANTHROPIC_API_KEY") is not None

    def extract_thinking_content(self, response: Any) -> Optional[str]:
        """
        Extract thinking/reasoning content from Anthropic response.

        Anthropic returns thinking as special content blocks when using
        thinking mode (available in Claude 3.5+).
        """
        try:
            # Anthropic returns content as a list of blocks
            if hasattr(response, "content") and response.content:
                thinking_parts = []

                for content_block in response.content:
                    # Check if this is a thinking block (Anthropic API)
                    if hasattr(content_block, "type") and content_block.type == "thinking":
                        if hasattr(content_block, "thinking") and content_block.thinking:
                            thinking_parts.append(content_block.thinking)
                    # Check for text blocks that might contain thinking
                    elif hasattr(content_block, "type") and content_block.type == "text":
                        # Check if it has thinking attribute (some Anthropic models)
                        if hasattr(content_block, "thinking") and content_block.thinking:
                            thinking_parts.append(content_block.thinking)

                return "\n".join(thinking_parts) if thinking_parts else None
        except Exception:
            # Be defensive - if structure is unexpected, just return None
            pass
        return None

    def supports_thinking(self, model: str) -> bool:
        """
        Check if Anthropic model supports thinking process output.

        Thinking mode is available in Claude 3.5+ (Claude 3.5 Sonnet, Claude 3.7 Sonnet).
        """
        model_lower = model.lower()
        return (
            "claude-3.5" in model_lower
            or "claude-3.7" in model_lower
            or "claude-3.6" in model_lower  # Future-proofing
        )
