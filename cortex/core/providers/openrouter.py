"""OpenRouter provider (OpenAI-compatible)."""

import os
from typing import Dict, Any, List, Iterator, Optional

from .base import ModelProvider, ProviderError


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
        ]
        return any(indicator in model_lower for indicator in thinking_indicators)

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
