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
        if hasattr(response, 'choices') and response.choices:
            message = response.choices[0].message
            if hasattr(message, 'reasoning_content') and message.reasoning_content:
                return message.reasoning_content
        # For streaming chunks (delta)
        elif hasattr(response, 'choices') and response.choices and hasattr(response.choices[0], 'delta'):
            delta = response.choices[0].delta
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
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

    def extract_thinking_content(self, response: Any) -> Optional[str]:
        """
        Extract thinking/reasoning content from Anthropic response.
        
        Anthropic returns thinking as special content blocks when using
        thinking mode (available in Claude 3.5+).
        """
        try:
            # Anthropic returns content as a list of blocks
            if hasattr(response, 'content') and response.content:
                thinking_parts = []
                
                for content_block in response.content:
                    # Check if this is a thinking block (Anthropic API)
                    if hasattr(content_block, 'type') and content_block.type == "thinking":
                        if hasattr(content_block, 'thinking') and content_block.thinking:
                            thinking_parts.append(content_block.thinking)
                    # Check for text blocks that might contain thinking
                    elif hasattr(content_block, 'type') and content_block.type == "text":
                        # Check if it has thinking attribute (some Anthropic models)
                        if hasattr(content_block, 'thinking') and content_block.thinking:
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
            "claude-3.5" in model_lower or 
            "claude-3.7" in model_lower or
            "claude-3.6" in model_lower  # Future-proofing
        )


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

            # Add reasoning support for MiMo and other reasoning models
            if self._should_enable_reasoning(model):
                kwargs["extra_body"] = self._get_reasoning_config(model, tools)
            
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
        if hasattr(response, 'choices') and response.choices:
            message = response.choices[0].message
            # Try OpenAI reasoning field (for o1, o3, o1-mini)
            if hasattr(message, 'reasoning') and message.reasoning:
                return message.reasoning
            # Try reasoning_content (for DeepSeek via OpenRouter)
            if hasattr(message, 'reasoning_content') and message.reasoning_content:
                return message.reasoning_content
        # For streaming chunks (delta)
        elif hasattr(response, 'choices') and response.choices and hasattr(response.choices[0], 'delta'):
            delta = response.choices[0].delta
            if hasattr(delta, 'reasoning') and delta.reasoning:
                return delta.reasoning
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
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
            "o1", "o3", "o1-mini", "reasoner", "thinking",
            "deepseek", "claude-3.5", "claude-3.7", "mimo"
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
    
    def _get_reasoning_config(self, model: str, tools: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Get reasoning configuration based on task complexity.
        
        Args:
            model: Model name
            tools: List of tools being used (indicates task complexity)
        
        Returns:
            Reasoning configuration dict for extra_body
        """
        from .model_capabilities import get_model_profile
        
        config = {}
        
        # Get model profile to access reasoning budget
        profile = get_model_profile(model)
        
        # Determine thinking budget based on task complexity
        if tools and len(tools) > 0:
            # Complex tasks with tools (coding, editing, etc.)
            # Use complex budget from profile or default 8000
            budget = profile.reasoning_budget.get("complex", 8000) if profile.reasoning_budget else 8000
        else:
            # Simple tasks without tools
            # Use simple budget from profile or default 2000
            budget = profile.reasoning_budget.get("simple", 2000) if profile.reasoning_budget else 2000
        
        config["reasoning"] = {"max_tokens": budget}
        
        return config


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

        # Exclude models with ollama/ prefix - these are local
        if model_lower.startswith("ollama/"):
            return OllamaProvider()

        # Generic slash detection for OpenRouter models (user requested: models with slashes are OpenRouter)
        if '/' in model_name:
            return OpenRouterProvider()

        # Check for OpenRouter models first (including models with colons)
        openrouter_indicators = [
            "devstral", "openrouter/", "nvidia/", ":free", ":paid",
            "mistralai/", "google/", "anthropic/", "meta-llama/",
            "perplexity/", "cohere/", "jamba/", "qwen/",
            "x-ai/", "xiaomi/", "cognitivecomputations/", "openai/",
            "nousresearch/", "z-ai/"
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
                # Check other OpenRouter indicators
                if any(indicator in model_lower for indicator in openrouter_indicators):
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

        # Exclude models with ollama/ prefix - these are local
        if model_lower.startswith("ollama/"):
            return False

        # Generic slash detection for OpenRouter models (user requested: models with slashes are OpenRouter)
        if '/' in model_name:
            return True

        # Check for OpenRouter indicators first (including models with colons)
        openrouter_indicators = [
            "devstral", "openrouter/", "nvidia/", ":free", ":paid",
            "mistralai/", "google/", "anthropic/", "meta-llama/",
            "perplexity/", "cohere/", "jamba/", "qwen/",
            "x-ai/", "xiaomi/", "cognitivecomputations/", "openai/",
            "nousresearch/", "z-ai/"
        ]
        
        # Special case: if model contains "llama3" but looks like Ollama format, it's Ollama
        if "llama3" in model_lower and ":" in model_name:
            import re
            # Check if it matches Ollama pattern like "llama3.2:70b" or "llama3:70b"
            if re.match(r'^llama3(\.\d+)?:\d+[bB]?$', model_name):
                # This is an Ollama model (local)
                return False
            else:
                # Check other OpenRouter indicators
                if any(indicator in model_lower for indicator in openrouter_indicators):
                    return True
        elif any(indicator in model_lower for indicator in openrouter_indicators):
            return True

        # Check for Ollama model patterns (contains colon but not OpenRouter patterns)
        if ":" in model_name:
            return False
        
        # Check for other cloud providers
        if model_lower.startswith("deepseek-"):
            return True
        if model_lower.startswith("claude-") or model_lower == "claude":
            return True
        
        # Default to local (Ollama)
        return False

    @staticmethod
    def get_provider_name(model_name: str) -> str:
        """Get provider name for a model"""
        model_lower = model_name.lower()

        # Exclude models with ollama/ prefix - these are local
        if model_lower.startswith("ollama/"):
            return "ollama"

        # Generic slash detection for OpenRouter models (user requested: models with slashes are OpenRouter)
        if '/' in model_name:
            return "openrouter"

        # Check for OpenRouter models first (including models with colons)
        openrouter_indicators = [
            "devstral", "openrouter/", "nvidia/", ":free", ":paid",
            "mistralai/", "google/", "anthropic/", "meta-llama/",
            "perplexity/", "cohere/", "jamba/", "qwen/",
            "x-ai/", "xiaomi/", "cognitivecomputations/", "openai/",
            "nousresearch/", "z-ai/"
        ]
        
        # Special case: if model contains "llama3" but looks like Ollama format, it's Ollama
        if "llama3" in model_lower and ":" in model_name:
            # Check if it matches Ollama pattern like "llama3.2:70b" or "llama3:70b"
            import re
            if re.match(r'^llama3(\.\d+)?:\d+[bB]?$', model_name):
                # This is an Ollama model, skip to Ollama detection below
                pass
            else:
                # Check other OpenRouter indicators
                if any(indicator in model_lower for indicator in openrouter_indicators):
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
