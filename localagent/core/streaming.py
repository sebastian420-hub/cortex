"""Streaming response handling"""

from typing import Iterator, Dict, Any, Optional
import ollama
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


def stream_ollama_response(
    model: str,
    messages: list,
    tools: list
) -> Iterator[Dict[str, Any]]:
    """
    Stream responses from Ollama.
    
    Args:
        model: Model name
        messages: Conversation history
        tools: Tool definitions
        
    Yields:
        Response chunks from Ollama
    """
    try:
        stream = ollama.chat(
            model=model,
            messages=messages,
            tools=tools,
            stream=True
        )
        
        for chunk in stream:
            yield chunk
    except Exception as e:
        console.print(f"[red]Streaming error:[/red] {e}")
        raise


def display_streaming_response(
    stream: Iterator[Dict[str, Any]],
    title: str = "[bold green]🤖 LocalAgent[/bold green]"
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
    tool_calls: list[Dict[str, Any]] = []
    full_message: Dict[str, Any] = {"role": "assistant"}
    
    # Collect all chunks
    for chunk in stream:
        msg = chunk.get("message", {})
        
        # Accumulate content
        if msg.get("content"):
            content_parts.append(msg["content"])
        
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
    
    if tool_calls:
        full_message["tool_calls"] = tool_calls
    
    # Display final content if any
    if full_message.get("content"):
        console.print(Panel(
            Markdown(full_message["content"]),
            title=title,
            border_style="green"
        ))
    
    return full_message

