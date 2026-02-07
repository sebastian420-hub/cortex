"""Tool call validation and normalization utilities.

This module provides functions to validate and normalize tool call data
from various model providers. Some models (e.g., Kimi K2.5 via OpenRouter)
return non-standard tool call formats such as:
- Integer IDs instead of strings
- None or empty string IDs
- Empty string arguments instead of "{}"
- Invalid JSON in arguments

These utilities ensure consistent, type-safe tool call data throughout the system.
"""

import json
import uuid
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def normalize_tool_call_id(raw_id: Any, fallback_prefix: str = "call") -> str:
    """
    Normalize a tool call ID to a valid string format.

    Handles:
    - Integer IDs (converted to string)
    - None/null IDs (generated UUID-based ID)
    - Empty string IDs (generated UUID-based ID)
    - Already valid string IDs (returned as-is)

    Args:
        raw_id: The raw ID from the API response (may be int, None, str, etc.)
        fallback_prefix: Prefix for generated IDs when raw_id is invalid

    Returns:
        A valid string ID
    """
    if raw_id is None or raw_id == "":
        generated_id = f"{fallback_prefix}_{uuid.uuid4().hex[:12]}"
        logger.debug(f"Generated tool call ID: {generated_id} (raw was: {raw_id!r})")
        return generated_id

    if isinstance(raw_id, int):
        str_id = str(raw_id)
        logger.debug(f"Converted integer tool call ID: {raw_id} -> {str_id}")
        return str_id

    if isinstance(raw_id, str):
        return raw_id

    # Fallback for any other unexpected type
    logger.warning(f"Unexpected tool call ID type: {type(raw_id).__name__}, value: {raw_id!r}")
    return f"{fallback_prefix}_{uuid.uuid4().hex[:12]}"


def normalize_tool_call_arguments(raw_arguments: Any) -> str:
    """
    Normalize tool call arguments to a valid JSON string.

    Handles:
    - Empty string "" -> "{}"
    - None/null -> "{}"
    - Whitespace-only strings -> "{}"
    - Already valid JSON strings -> returned as-is
    - Dict objects -> serialized to JSON
    - Invalid JSON strings -> "{}" with warning

    Args:
        raw_arguments: The raw arguments from the API response

    Returns:
        A valid JSON string (at minimum "{}")
    """
    if raw_arguments is None or raw_arguments == "":
        return "{}"

    if isinstance(raw_arguments, dict):
        # If it's already a dict, serialize it
        try:
            return json.dumps(raw_arguments, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize arguments dict: {e}")
            return "{}"

    if isinstance(raw_arguments, str):
        # Check for whitespace-only strings
        if raw_arguments.strip() == "":
            return "{}"
        # Validate it's valid JSON
        try:
            json.loads(raw_arguments)
            return raw_arguments
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in tool arguments, using empty: {raw_arguments[:100]}")
            return "{}"

    # Fallback for any other unexpected type
    logger.warning(f"Unexpected arguments type: {type(raw_arguments).__name__}")
    return "{}"


def validate_tool_call_data(tool_call_data: Dict[str, Any], index: int = 0) -> Dict[str, Any]:
    """
    Validate and normalize a single tool call data structure.

    This is the main entry point for normalizing tool call data from providers.
    It ensures all fields are present and correctly typed.

    Args:
        tool_call_data: Raw tool call dict from provider response
        index: Index of this tool call in the batch (for fallback ID generation)

    Returns:
        Normalized tool call dict with guaranteed string ID and valid arguments
    """
    # Handle None or missing function data
    function_data = tool_call_data.get("function")
    if function_data is None:
        function_data = {}

    normalized = {
        "id": normalize_tool_call_id(tool_call_data.get("id"), f"call_{index}"),
        "type": tool_call_data.get("type", "function"),
        "function": {
            "name": function_data.get("name") or "",
            "arguments": normalize_tool_call_arguments(function_data.get("arguments"))
        }
    }

    # Preserve index if present (for streaming tool calls)
    if "index" in tool_call_data:
        normalized["index"] = tool_call_data["index"]

    return normalized
