"""Provider for any server that speaks the OpenAI chat API.

That covers OpenAI itself and, more usefully for local work, vLLM, llama.cpp's ``llama-server``,
LM Studio and SGLang: the usual ways to serve a model that is too big for Ollama's defaults or
that runs on another machine. The connection uses the OpenAI SDK's own settings,
``OPENAI_BASE_URL`` and ``OPENAI_API_KEY``. A local server ignores the key, so a base URL alone is
enough.

The server's context window is not discoverable through this API, so it is configured
(``openai.context_window`` or ``CORTEX_OPENAI_CONTEXT_WINDOW``). When it is set the agent sizes the
conversation to fit it; when it is not, the agent assumes the server's window is large enough.
"""

import os
from typing import Any, Dict, Iterator, List, Optional

from .base import ModelProvider, ProviderError, positive_int
from .usage import normalize_usage

BASE_URL_ENV = "OPENAI_BASE_URL"
API_KEY_ENV = "OPENAI_API_KEY"
CONTEXT_WINDOW_ENV = "CORTEX_OPENAI_CONTEXT_WINDOW"

# The SDK refuses an empty key, and a local server does not check it
PLACEHOLDER_KEY = "not-needed"


class OpenAICompatibleProvider(ModelProvider):
    """Provider for OpenAI and OpenAI-compatible servers (vLLM, llama.cpp, LM Studio, SGLang)"""

    config_section = "openai"

    def __init__(self):
        try:
            from openai import OpenAI

            self.client_class = OpenAI
        except ImportError:
            raise ProviderError("OpenAI package not installed. Install with: pip install openai")

        self._configured_base_url: Optional[str] = None
        self._context_window: Optional[int] = positive_int(os.getenv(CONTEXT_WINDOW_ENV))
        self._connect()

    # ---- connecting --------------------------------------------------------------------

    @property
    def base_url(self) -> Optional[str]:
        """The server to talk to: the environment first, then the configuration, else OpenAI."""
        return os.getenv(BASE_URL_ENV) or self._configured_base_url or None

    def _connect(self) -> None:
        base_url = self.base_url
        api_key = os.getenv(API_KEY_ENV)
        if not api_key and not base_url:
            raise ProviderError(
                f"No OpenAI server to talk to. Set {BASE_URL_ENV} (for a local server such as "
                f"vLLM or llama.cpp, e.g. http://localhost:8000/v1) or {API_KEY_ENV} (for OpenAI)."
            )

        kwargs: Dict[str, Any] = {"api_key": api_key or PLACEHOLDER_KEY}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = self.client_class(**kwargs)

    def configure(self, options: Optional[Dict[str, Any]] = None) -> None:
        options = options or {}
        self._configured_base_url = str(options.get("base_url") or "").strip() or None
        self._context_window = positive_int(os.getenv(CONTEXT_WINDOW_ENV)) or positive_int(
            options.get("context_window")
        )
        self._connect()

    @property
    def context_window(self) -> Optional[int]:
        return self._context_window

    def window_advice(self, needed: int) -> str:
        return (
            f"Start the server with a window of at least {needed} tokens (for vLLM, "
            f"--max-model-len; for llama.cpp, --ctx-size) and set {CONTEXT_WINDOW_ENV} (or "
            f"openai.context_window in the config) to match"
        )

    def _where(self) -> str:
        return self.base_url or "api.openai.com"

    # ---- chatting ----------------------------------------------------------------------

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Call the chat completions endpoint"""
        try:
            sanitized_messages, sanitized_tools = self._sanitize_request(messages, tools)
            kwargs: Dict[str, Any] = {"model": model, "messages": sanitized_messages}
            if sanitized_tools:
                kwargs["tools"] = sanitized_tools

            response = self.client.chat.completions.create(**kwargs)

            message = response.choices[0].message
            result: Dict[str, Any] = {
                "message": {
                    "role": getattr(message, "role", None) or "assistant",
                    "content": message.content or "",
                }
            }
            usage = normalize_usage(getattr(response, "usage", None))
            if usage:
                result["usage"] = usage

            tool_calls = getattr(message, "tool_calls", None)
            if tool_calls:
                # Local models often send calls with no id, or with arguments that are empty or
                # not valid JSON; the validator turns each into something the agent can run
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
                    for i, tc in enumerate(tool_calls)
                ]
            return result
        except Exception as e:
            raise ProviderError(f"OpenAI-compatible API error ({self._where()}): {e}") from e

    def stream_chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Stream the chat completions endpoint"""
        try:
            sanitized_messages, sanitized_tools = self._sanitize_request(messages, tools)
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": sanitized_messages,
                "stream": True,
            }
            if sanitized_tools:
                kwargs["tools"] = sanitized_tools

            for chunk in self.client.chat.completions.create(**kwargs):
                if not chunk.choices or not chunk.choices[0].delta:
                    continue
                delta = chunk.choices[0].delta
                result: Dict[str, Any] = {
                    "message": {
                        "role": getattr(delta, "role", None) or "assistant",
                        "content": delta.content or "",
                    }
                }
                # Pieces of a call arrive over several chunks, so they are passed on as they are
                # (with their index) for the caller to assemble, not validated one by one
                if getattr(delta, "tool_calls", None):
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
            raise ProviderError(f"OpenAI-compatible streaming error ({self._where()}): {e}") from e

    def supports_streaming(self) -> bool:
        return True

    def normalize_model_name(self, model: str) -> str:
        """The server decides what names exist, so the name is used exactly as given."""
        return model

    def validate_api_key(self) -> bool:
        """A server to talk to is configured (a base URL, or an OpenAI key)."""
        return bool(self.base_url or os.getenv(API_KEY_ENV))
