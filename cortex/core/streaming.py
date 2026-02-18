"""Streaming response handling"""

import re
from typing import Iterator, Dict, Any, Optional
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from .providers import ModelProvider

console = Console()


def _extract_kimi_native_tool_calls_from_streaming(content: str) -> Optional[list]:
    """
    Extract tool calls from Kimi's native token format in accumulated streaming content.

    This is a lightweight version for post-processing accumulated streaming content.
    The full parsing is done in the OpenRouter provider.
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
                    continue

            tool_calls.append({
                "id": tool_id,
                "type": "function",
                "function": {
                    "name": func_name,
                    "arguments": args_str.strip(),
                },
            })

    return tool_calls if tool_calls else None


def _clean_kimi_tool_content(content: str) -> str:
    """Remove Kimi native tool call syntax from content."""
    if not content:
        return ""

    cleaned = re.sub(
        r"<\|tool_calls_section_begin\|>.*?<\|tool_calls_section_end\|>",
        "",
        content,
        flags=re.DOTALL,
    )

    return cleaned.strip()


def stream_model_response(
    provider: ModelProvider, model: str, messages: list, tools: list
) -> Iterator[Dict[str, Any]]:
    """
    Stream responses from model provider.

    Args:
        provider: Model provider instance
        model: Model name
        messages: Conversation history
        tools: Tool definitions

    Yields:
        Response chunks from the model
    """
    try:
        if not provider.supports_streaming():
            raise ValueError(f"Provider {type(provider).__name__} does not support streaming")

        stream = provider.stream_chat(model=model, messages=messages, tools=tools)

        for chunk in stream:
            yield chunk
    except Exception as e:
        console.print(f"[red]Streaming error:[/red] {e}")
        raise


def display_streaming_response(
    stream: Iterator[Dict[str, Any]], title: str = "[bold green]🤖 Cortex[/bold green]"
) -> Dict[str, Any]:
    """
    Display streaming response to user and collect full response.

    Args:
        stream: Iterator of response chunks
        title: Panel title

    Returns:
        Complete response message
    """
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls: list[Dict[str, Any]] = []
    full_message: Dict[str, Any] = {"role": "assistant"}

    # Collect all chunks
    for chunk in stream:
        msg = chunk.get("message", {})

        # Accumulate content
        if msg.get("content"):
            content_parts.append(msg["content"])

        # Accumulate reasoning_content (for DeepSeek thinking mode)
        if msg.get("reasoning_content"):
            reasoning_parts.append(msg["reasoning_content"])

        # Collect tool calls
        if msg.get("tool_calls"):
            if not tool_calls:
                tool_calls = msg["tool_calls"]
            else:
                # Merge tool calls
                for tc in msg["tool_calls"]:
                    # Update existing or add new
                    existing = next((t for t in tool_calls if t.get("id") == tc.get("id")), None)
                    if existing:
                        # Deep merge 'function' dictionary
                        if "function" in tc:
                            if "function" not in existing:
                                existing["function"] = {}
                            existing["function"].update(tc["function"])

                        # Update other top-level keys
                        for key, value in tc.items():
                            if key != "function":
                                existing[key] = value
                    else:
                        tool_calls.append(tc)

    # Build complete message
    full_content = "".join(content_parts) if content_parts else ""
    full_reasoning = "".join(reasoning_parts) if reasoning_parts else ""

    if full_content:
        full_message["content"] = full_content

    if full_reasoning:
        full_message["reasoning_content"] = full_reasoning

    if tool_calls:
        full_message["tool_calls"] = tool_calls
    elif full_content:
        # Post-process: Check for Kimi native tool calls in accumulated content
        # This handles cases where OpenRouter doesn't transpile Kimi's format
        kimi_tools = _extract_kimi_native_tool_calls_from_streaming(full_content)
        if kimi_tools:
            from cortex.utils.tool_call_validation import validate_tool_call_data

            full_message["tool_calls"] = [
                validate_tool_call_data(tc, index=i)
                for i, tc in enumerate(kimi_tools)
            ]
            # Clean content
            full_message["content"] = _clean_kimi_tool_content(full_content)

    # Handle case where we only have reasoning but no content
    # This prevents "empty assistant message" warnings downstream
    if not full_content and full_reasoning and not tool_calls:
        # Check if reasoning contains tool syntax - if so, try to extract tool calls
        tool_syntax_patterns = ["<tool_call>", "</tool_call>", "function_call", "tool_use", "<function_call>"]
        has_tool_syntax = any(pattern in full_reasoning.lower() for pattern in tool_syntax_patterns)
        
        if has_tool_syntax:
            # Try to extract tools from reasoning content as fallback
            kimi_tools = _extract_kimi_native_tool_calls_from_streaming(full_reasoning)
            if kimi_tools:
                from cortex.utils.tool_call_validation import validate_tool_call_data
                full_message["tool_calls"] = [
                    validate_tool_call_data(tc, index=i)
                    for i, tc in enumerate(kimi_tools)
                ]
                # Don't expose the raw tool syntax in reasoning
                full_message["reasoning_content"] = "[Tool call extracted from reasoning]"
            else:
                # Couldn't parse tools, just use reasoning as content
                full_message["content"] = full_reasoning
        else:
            # Normal reasoning-only response - use reasoning as content
            full_message["content"] = full_reasoning

    # Ensure we always have at least empty content to prevent API errors
    if "content" not in full_message:
        full_message["content"] = ""

    # Display final content if any (simple markdown, no Panel)
    if full_message.get("content"):
        console.print(Markdown(full_message["content"]))

    return full_message
