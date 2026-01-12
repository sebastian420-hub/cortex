"""Output formatters for different output modes"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TextIO
from enum import Enum
from datetime import datetime
import json
import sys


class OutputFormat(Enum):
    """Supported output formats"""

    TEXT = "text"  # Human-readable text (default)
    JSON = "json"  # Structured JSON output
    STREAM_JSON = "stream-json"  # Real-time newline-delimited JSON


class OutputFormatter(ABC):
    """
    Base class for output formatters.

    Formatters handle the presentation of agent responses, tool results,
    and errors in different formats suitable for various use cases.
    """

    @abstractmethod
    def format_response(self, response: Dict[str, Any]) -> str:
        """
        Format an assistant response.

        Args:
            response: Response dictionary with 'content', 'tool_calls', etc.

        Returns:
            Formatted string
        """
        pass

    @abstractmethod
    def format_tool_result(self, tool_name: str, result: Dict[str, Any]) -> str:
        """
        Format a tool execution result.

        Args:
            tool_name: Name of the tool that was executed
            result: Tool result dictionary

        Returns:
            Formatted string
        """
        pass

    @abstractmethod
    def format_error(
        self, error: str, error_type: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format an error message.

        Args:
            error: Error message
            error_type: Type of error (e.g., "permission", "execution")
            context: Optional additional context

        Returns:
            Formatted string
        """
        pass

    @abstractmethod
    def format_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Format a tool call (before execution).

        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments

        Returns:
            Formatted string
        """
        pass

    @abstractmethod
    def write(self, content: str) -> None:
        """
        Write formatted content to output.

        Args:
            content: Content to write
        """
        pass


class TextFormatter(OutputFormatter):
    """
    Human-readable text output formatter.

    Uses Rich console for colorized, styled output.
    This is the default formatter for interactive use.
    """

    def __init__(self, console=None):
        """
        Initialize text formatter.

        Args:
            console: Rich Console instance (optional, uses default if None)
        """
        self.console = console
        if self.console is None:
            from rich.console import Console

            self.console = Console()

    def format_response(self, response: Dict[str, Any]) -> str:
        """Format response as human-readable text."""
        content = response.get("content", "")
        return content

    def format_tool_result(self, tool_name: str, result: Dict[str, Any]) -> str:
        """Format tool result with success/error indication."""
        if result.get("success"):
            return f"[green]Tool {tool_name}: Success[/green]"
        else:
            error = result.get("error", "Unknown error")
            return f"[red]Tool {tool_name}: Error - {error}[/red]"

    def format_error(
        self, error: str, error_type: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format error with color coding."""
        return f"[red][{error_type.upper()}][/red] {error}"

    def format_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Format tool call announcement."""
        args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        return f"[cyan]Calling {tool_name}({args_str})[/cyan]"

    def write(self, content: str) -> None:
        """Write to Rich console."""
        if self.console:
            self.console.print(content)


class JSONFormatter(OutputFormatter):
    """
    Structured JSON output formatter.

    Outputs all data as JSON objects, suitable for programmatic consumption.
    Each output is a complete JSON object on its own line.
    """

    def __init__(self, stream: Optional[TextIO] = None, pretty: bool = False):
        """
        Initialize JSON formatter.

        Args:
            stream: Output stream (default: sys.stdout)
            pretty: Whether to pretty-print JSON (default: False)
        """
        self.stream = stream or sys.stdout
        self.pretty = pretty

    def _timestamp(self) -> str:
        """Get current ISO timestamp."""
        return datetime.now().isoformat()

    def _to_json(self, data: Dict[str, Any]) -> str:
        """Convert dict to JSON string."""
        if self.pretty:
            return json.dumps(data, indent=2, default=str)
        return json.dumps(data, default=str)

    def format_response(self, response: Dict[str, Any]) -> str:
        """Format response as JSON object."""
        return self._to_json(
            {
                "type": "response",
                "content": response.get("content", ""),
                "tool_calls": response.get("tool_calls"),
                "timestamp": self._timestamp(),
            }
        )

    def format_tool_result(self, tool_name: str, result: Dict[str, Any]) -> str:
        """Format tool result as JSON object."""
        return self._to_json(
            {
                "type": "tool_result",
                "tool_name": tool_name,
                "success": result.get("success", False),
                "result": result,
                "timestamp": self._timestamp(),
            }
        )

    def format_error(
        self, error: str, error_type: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format error as JSON object."""
        return self._to_json(
            {
                "type": "error",
                "error": error,
                "error_type": error_type,
                "context": context,
                "timestamp": self._timestamp(),
            }
        )

    def format_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Format tool call as JSON object."""
        return self._to_json(
            {
                "type": "tool_call",
                "tool_name": tool_name,
                "arguments": arguments,
                "timestamp": self._timestamp(),
            }
        )

    def write(self, content: str) -> None:
        """Write to output stream."""
        self.stream.write(content + "\n")
        self.stream.flush()


class StreamJSONFormatter(JSONFormatter):
    """
    Real-time streaming JSON output formatter.

    Extends JSONFormatter with streaming capabilities for real-time output.
    Outputs newline-delimited JSON (NDJSON) for easy parsing.
    """

    def __init__(self, stream: Optional[TextIO] = None):
        """
        Initialize stream JSON formatter.

        Args:
            stream: Output stream (default: sys.stdout)
        """
        super().__init__(stream=stream, pretty=False)

    def stream_start(self, event_type: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Signal start of a streaming event.

        Args:
            event_type: Type of event starting (e.g., "response", "tool_execution")
            metadata: Optional metadata about the event
        """
        output = self._to_json(
            {
                "type": "stream_start",
                "event": event_type,
                "metadata": metadata,
                "timestamp": self._timestamp(),
            }
        )
        self.stream.write(output + "\n")
        self.stream.flush()

    def stream_chunk(self, chunk: Dict[str, Any], event_type: str = "response") -> None:
        """
        Stream a single chunk of data.

        Args:
            chunk: Chunk data to stream
            event_type: Type of event this chunk belongs to
        """
        output = self._to_json(
            {"type": "chunk", "event": event_type, "data": chunk, "timestamp": self._timestamp()}
        )
        self.stream.write(output + "\n")
        self.stream.flush()

    def stream_end(self, event_type: str, summary: Optional[Dict[str, Any]] = None) -> None:
        """
        Signal end of a streaming event.

        Args:
            event_type: Type of event ending
            summary: Optional summary of the completed event
        """
        output = self._to_json(
            {
                "type": "stream_end",
                "event": event_type,
                "summary": summary,
                "timestamp": self._timestamp(),
            }
        )
        self.stream.write(output + "\n")
        self.stream.flush()

    def stream_error(self, error: str, error_type: str, event_type: str = "response") -> None:
        """
        Stream an error during a streaming event.

        Args:
            error: Error message
            error_type: Type of error
            event_type: Type of event where error occurred
        """
        output = self._to_json(
            {
                "type": "stream_error",
                "event": event_type,
                "error": error,
                "error_type": error_type,
                "timestamp": self._timestamp(),
            }
        )
        self.stream.write(output + "\n")
        self.stream.flush()


def create_formatter(
    output_format: OutputFormat, console=None, stream: Optional[TextIO] = None, pretty: bool = False
) -> OutputFormatter:
    """
    Factory function to create appropriate formatter.

    Args:
        output_format: Desired output format
        console: Rich Console instance (for TextFormatter)
        stream: Output stream (for JSON formatters)
        pretty: Pretty-print JSON (for JSONFormatter)

    Returns:
        OutputFormatter instance

    Raises:
        ValueError: If output_format is not recognized
    """
    if output_format == OutputFormat.TEXT:
        return TextFormatter(console=console)
    elif output_format == OutputFormat.JSON:
        return JSONFormatter(stream=stream, pretty=pretty)
    elif output_format == OutputFormat.STREAM_JSON:
        return StreamJSONFormatter(stream=stream)
    else:
        raise ValueError(f"Unknown output format: {output_format}")
