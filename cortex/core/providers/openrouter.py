"""OpenRouter provider (OpenAI-compatible)."""

import os
import re
import logging
from typing import Dict, Any, List, Iterator, Optional

from .base import ModelProvider, ProviderError

logger = logging.getLogger(__name__)


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
            },
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

            # Add reasoning support for MiMo and other reasoning models
            if self._should_enable_reasoning(model):
                kwargs["extra_body"] = self._get_reasoning_config(model, tools)

            response = self.client.chat.completions.create(**kwargs)

            # Convert OpenAI format to Cortex internal format
            message = response.choices[0].message
            result = {"message": {"role": message.role, "content": message.content or ""}}

            if hasattr(message, "tool_calls") and message.tool_calls:
                from cortex.utils.tool_call_validation import validate_tool_call_data

                result["message"]["tool_calls"] = [
                    validate_tool_call_data(
                        {
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                            "id": tc.id,
                            "type": tc.type,
                        },
                        index=i,
                    )
                    for i, tc in enumerate(message.tool_calls)
                ]
            else:
                # Fallback: Check for Kimi native tool call format
                # OpenRouter may not always transpile Kimi's native format to OpenAI format
                kimi_tools = self._extract_kimi_native_tool_calls(message.content or "")
                if kimi_tools:
                    from cortex.utils.tool_call_validation import validate_tool_call_data

                    logger.info(
                        f"Parsed {len(kimi_tools)} tool calls from Kimi native format "
                        f"for model {model}"
                    )
                    result["message"]["tool_calls"] = [
                        validate_tool_call_data(tc, index=i)
                        for i, tc in enumerate(kimi_tools)
                    ]
                    # Remove tool syntax from content
                    result["message"]["content"] = self._clean_kimi_tool_content(
                        message.content or ""
                    )

            # Extract reasoning_details if available
            if hasattr(message, "reasoning_details") and message.reasoning_details:
                result["message"]["reasoning_details"] = message.reasoning_details

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

            # Add reasoning support for MiMo and other reasoning models
            if self._should_enable_reasoning(model):
                kwargs["extra_body"] = self._get_reasoning_config(model, tools)

            stream = self.client.chat.completions.create(**kwargs)

            # Buffer for Kimi native tool call detection in streaming mode
            content_buffer = ""
            kimi_section_started = False

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

                        # Buffer content for Kimi native tool call detection
                        if delta.content:
                            content_buffer += delta.content
                            # Check if we're entering a tool calls section
                            if "<|tool_calls_section_begin|>" in content_buffer:
                                kimi_section_started = True

                        if hasattr(delta, "tool_calls") and delta.tool_calls:
                            from cortex.utils.tool_call_validation import validate_tool_call_data

                            result["message"]["tool_calls"] = [
                                validate_tool_call_data(
                                    {
                                        "function": {
                                            "name": tc.function.name if tc.function else None,
                                            "arguments": (
                                                tc.function.arguments if tc.function else ""
                                            ),
                                        },
                                        "id": tc.id,
                                        "index": tc.index,
                                        "type": tc.type,
                                    },
                                    index=tc.index if tc.index is not None else i,
                                )
                                for i, tc in enumerate(delta.tool_calls)
                            ]
                        # Extract reasoning_details if available
                        if hasattr(delta, "reasoning_details") and delta.reasoning_details:
                            result["message"]["reasoning_details"] = delta.reasoning_details

                        # Check if Kimi native tool call section is complete
                        if kimi_section_started and "<|tool_calls_section_end|>" in content_buffer:
                            # Extract tool calls from buffered content
                            kimi_tools = self._extract_kimi_native_tool_calls(content_buffer)
                            if kimi_tools:
                                from cortex.utils.tool_call_validation import validate_tool_call_data

                                logger.info(
                                    f"Parsed {len(kimi_tools)} tool calls from Kimi native format "
                                    f"in streaming mode for model {model}"
                                )
                                result["message"]["tool_calls"] = [
                                    validate_tool_call_data(tc, index=i)
                                    for i, tc in enumerate(kimi_tools)
                                ]
                                # Clear content since it was tool syntax
                                result["message"]["content"] = ""
                            # Reset buffer
                            content_buffer = ""
                            kimi_section_started = False

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

    def extract_thinking_content(self, response: Any) -> Optional[str]:
        """
        Extract thinking/reasoning content from OpenRouter response.

        OpenRouter supports OpenAI-compatible reasoning models (o1, o3, etc.).
        It may also route requests to DeepSeek reasoning models.
        """
        # For non-streaming responses
        if hasattr(response, "choices") and response.choices:
            message = response.choices[0].message
            # Try OpenAI reasoning field (for o1, o3, o1-mini)
            if hasattr(message, "reasoning") and message.reasoning:
                return message.reasoning
            # Try reasoning_content (for DeepSeek via OpenRouter)
            if hasattr(message, "reasoning_content") and message.reasoning_content:
                return message.reasoning_content
        # For streaming chunks (delta)
        elif (
            hasattr(response, "choices")
            and response.choices
            and hasattr(response.choices[0], "delta")
        ):
            delta = response.choices[0].delta
            if hasattr(delta, "reasoning") and delta.reasoning:
                return delta.reasoning
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                return delta.reasoning_content
        return None

    def supports_thinking(self, model: str) -> bool:
        """
        Check if OpenRouter model supports thinking process output.

        OpenRouter provides access to various reasoning models including:
        - OpenAI o1, o3, o1-mini (reasoning field)
        - DeepSeek reasoning models (reasoning_content field)
        - Anthropic Claude with thinking (content blocks)
        - MiMo-V2-Flash (reasoning_details field)
        """
        model_lower = model.lower()
        thinking_indicators = [
            "o1",
            "o3",
            "o1-mini",
            "reasoner",
            "thinking",
            "deepseek",
            "claude-3.5",
            "claude-3.7",
            "mimo",
            "kimi",
        ]
        return any(indicator in model_lower for indicator in thinking_indicators)

    def _extract_kimi_native_tool_calls(self, content: str) -> Optional[List[Dict[str, Any]]]:
        """
        Extract tool calls from Kimi's native token format.

        Kimi K2/K2.5 models use a special token-based format for tool calls that
        OpenRouter may not always properly transpile to OpenAI's tool_calls format.

        Native Kimi format:
        <|tool_calls_section_begin|>
        <|tool_call_begin|>functions.func_name:0<|tool_call_argument_begin|>{"arg": "value"}
        <|tool_call_end|>
        <|tool_calls_section_end|>

        Args:
            content: The raw content from the model response

        Returns:
            List of tool call dicts in OpenAI-compatible format, or None if no native format found
        """
        if not content or "<|tool_calls_section_begin|>" not in content:
            return None

        tool_calls = []

        # Pattern to match the entire tool calls section
        section_pattern = r"<\|tool_calls_section_begin\|>(.*?)<\|tool_calls_section_end\|>"
        sections = re.findall(section_pattern, content, re.DOTALL)

        if not sections:
            return None

        # Pattern to match individual tool calls within the section
        # Format: <|tool_call_begin|>functions.name:idx<|tool_call_argument_begin|>{args}<|tool_call_end|>
        call_pattern = (
            r"<\|tool_call_begin\|>\s*"
            r"(?P<tool_id>[\w\.]+:\d+)\s*"
            r"<\|tool_call_argument_begin\|>\s*"
            r"(?P<args>\{.*?\})\s*"
            r"<\|tool_call_end\|>"
        )

        for section in sections:
            for match in re.finditer(call_pattern, section, re.DOTALL):
                tool_id = match.group("tool_id")
                args_str = match.group("args")

                # Parse function name from ID (functions.func_name:0)
                func_name = ""
                if "." in tool_id and ":" in tool_id:
                    try:
                        func_name = tool_id.split(".")[1].split(":")[0]
                    except IndexError:
                        logger.warning(f"Could not parse function name from tool_id: {tool_id}")
                        continue

                tool_calls.append({
                    "id": tool_id,
                    "type": "function",
                    "function": {
                        "name": func_name,
                        "arguments": args_str.strip(),
                    },
                })

        if tool_calls:
            logger.debug(f"Extracted {len(tool_calls)} tool calls from Kimi native format")

        return tool_calls if tool_calls else None

    def _clean_kimi_tool_content(self, content: str) -> str:
        """
        Remove Kimi native tool call syntax from content.

        Args:
            content: Raw content containing tool call syntax

        Returns:
            Cleaned content with tool syntax removed
        """
        if not content:
            return ""

        # Remove the entire tool calls section
        cleaned = re.sub(
            r"<\|tool_calls_section_begin\|>.*?<\|tool_calls_section_end\|>",
            "",
            content,
            flags=re.DOTALL,
        )

        return cleaned.strip()

    def _should_enable_reasoning(self, model: str) -> bool:
        """
        Determine if reasoning should be enabled for this model.

        MiMo and other reasoning models benefit from thinking tokens for complex tasks.
        """
        # Enable for MiMo models
        if "mimo" in model.lower():
            return True

        # Enable for other reasoning models
        return self.supports_thinking(model)

    def _get_reasoning_config(
        self, model: str, tools: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Get reasoning configuration based on task complexity.

        Args:
            model: Model name
            tools: List of tools being used (indicates task complexity)

        Returns:
            Reasoning configuration dict for extra_body
        """
        from ..model_capabilities import get_model_profile

        config = {}

        # Get model profile to access reasoning budget
        profile = get_model_profile(model)

        # Determine thinking budget based on task complexity
        # Note: Some models may ignore max_tokens but it's good to provide
        if tools and len(tools) > 0:
            # Complex tasks with tools (coding, editing, etc.)
            # Use complex budget from profile or default 8000
            budget = (
                profile.reasoning_budget.get("complex", 8000) if profile.reasoning_budget else 8000
            )
        else:
            # Simple tasks without tools
            # Use simple budget from profile or default 2000
            budget = (
                profile.reasoning_budget.get("simple", 2000) if profile.reasoning_budget else 2000
            )

        # OpenRouter reasoning format for MiMo and similar models
        # Uses "reasoning": {"max_tokens": budget} format
        config["reasoning"] = {"max_tokens": budget}

        return config
