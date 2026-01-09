"""Streaming response handling"""

from typing import Iterator, Dict, Any, Optional
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from .providers import ModelProvider

console = Console()


def stream_model_response(
    provider: ModelProvider,
    model: str,
    messages: list,
    tools: list
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
        
        stream = provider.stream_chat(
            model=model,
            messages=messages,
            tools=tools
        )
        
        for chunk in stream:
            yield chunk
    except Exception as e:
        console.print(f"[red]Streaming error:[/red] {e}")
        raise


def display_streaming_response(
    stream: Iterator[Dict[str, Any]],
    title: str = "[bold green]🤖 Cortex[/bold green]"
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
                    existing = next(
                        (t for t in tool_calls if t.get("id") == tc.get("id")),
                        None
                    )
                    if existing:
                        existing.update(tc)
                    else:
                        tool_calls.append(tc)
    
    # Build complete message
    if content_parts:
        full_message["content"] = "".join(content_parts)
    
    if reasoning_parts:
        full_message["reasoning_content"] = "".join(reasoning_parts)
    
    if tool_calls:
        full_message["tool_calls"] = tool_calls
    
    # Display final content if any (simple markdown, no Panel)
    if full_message.get("content"):
        console.print(Markdown(full_message["content"]))
    
    return full_message

