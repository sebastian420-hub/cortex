"""Token usage, in one shape, whatever the provider calls it.

Providers report usage under different names: OpenAI-style APIs (OpenRouter, DeepSeek) say
``prompt_tokens``/``completion_tokens``, Anthropic says ``input_tokens``/``output_tokens``, Ollama
says ``prompt_eval_count``/``eval_count``. Everything downstream (the benchmark's token and cost
columns) reads ``{"input_tokens": int, "output_tokens": int}``.

When a provider reports nothing, there is no usage: callers get None, never a made-up zero.
"""

from typing import Any, Dict, Optional

_INPUT_KEYS = ("input_tokens", "prompt_tokens", "prompt_eval_count")
_OUTPUT_KEYS = ("output_tokens", "completion_tokens", "eval_count")


def _read(source: Any, key: str) -> Optional[int]:
    value = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def normalize_usage(raw: Any) -> Optional[Dict[str, int]]:
    """``{"input_tokens", "output_tokens"}`` from an SDK usage object or dict, or None."""
    if raw is None:
        return None
    input_tokens = next((v for v in (_read(raw, k) for k in _INPUT_KEYS) if v is not None), None)
    output_tokens = next((v for v in (_read(raw, k) for k in _OUTPUT_KEYS) if v is not None), None)
    if input_tokens is None and output_tokens is None:
        return None
    return {"input_tokens": input_tokens or 0, "output_tokens": output_tokens or 0}


def usage_of_response(response: Any) -> Optional[Dict[str, int]]:
    """The usage in a provider's chat() result: normalized under "usage", or Ollama-style counts
    sitting on the response itself."""
    if response is None:
        return None
    nested = (
        response.get("usage") if isinstance(response, dict) else getattr(response, "usage", None)
    )
    return normalize_usage(nested) or normalize_usage(response)
