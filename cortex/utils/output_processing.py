"""Utilities for processing and cleaning model output for display."""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def process_model_output(content: Any) -> str:
    """
    Process model output to handle common formatting issues.

    1. Unescapes literal \\n strings.
    2. Unwraps JSON-wrapped responses if they match the expected schema
       (e.g. {"answer": "..."} or {"content": "..."}).
    3. Handles JSON inside Markdown code blocks.
    4. Converts non-string content to string.

    Args:
        content: The raw content from the model.

    Returns:
        Processed string ready for display/Markdown parsing.
    """
    if content is None:
        return ""

    if not isinstance(content, str):
        # If it's already a dict, try to extract common answer keys
        if isinstance(content, dict):
            for key in ["answer", "content", "response", "text", "message", "summary"]:
                if key in content and content[key]:
                    return process_model_output(content[key])
        return str(content)

    # Unescape literal \\n strings (common with some model APIs)
    processed = content.replace("\\n", "\n")

    stripped = processed.strip()
    if not stripped:
        return ""

    # Check for Markdown code blocks containing JSON (a common model pattern)
    if "```json" in stripped:
        # Pattern to extract content inside ```json ... ```
        # We look for the FIRST JSON object found in a code block
        pattern = r"```json\s*(\{.*?\})\s*```"
        match = re.search(pattern, stripped, re.DOTALL)
        if match:
            potential_json = match.group(1).strip()
            # If the code block is the ONLY thing in the response (or nearly so),
            # we consider it a candidate for unwrapping.
            # If there's lots of other text, we keep it as Markdown.
            if len(stripped) < len(potential_json) + 20:
                stripped = potential_json

    # Check if content is a JSON-wrapped response and unwrap it
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                # Look for common fields models use when they "over-JSON"
                for key in ["answer", "content", "response", "text", "message", "summary"]:
                    if key in data and data[key]:
                        # Recursively process in case the value also needs unescaping or has its own JSON  # noqa: E501
                        return process_model_output(data[key])
        except (json.JSONDecodeError, TypeError, ValueError):
            # Not valid JSON or other error, return as is (but with \\n fixed)
            pass

    return processed
