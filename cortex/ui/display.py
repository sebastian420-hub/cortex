"""Display helpers for better UI"""

import difflib
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from typing import Optional, Dict, Any

from .modes import should_show_panels, is_minimal_mode, is_debug_mode

console = Console()


def show_file_diff(old_content: str, new_content: str, path: str) -> None:
    """Show a visual diff between old and new file content"""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines, new_lines, fromfile=f"old/{path}", tofile=f"new/{path}", lineterm=""
    )

    diff_text = "".join(diff)

    if diff_text:
        if is_minimal_mode():
            # Minimal mode: show diff without panel
            console.print(f"[yellow][DIFF] {path}[/yellow]")
            diff_lines = diff_text.split("\n")
            # Only show first few diff lines in minimal mode
            for line in diff_lines[:10]:
                if line.startswith("+"):
                    console.print(f"  [green]{line}[/green]")
                elif line.startswith("-"):
                    console.print(f"  [red]{line}[/red]")
                elif line.startswith("@@"):
                    console.print(f"  [cyan]{line}[/cyan]")
                else:
                    console.print(f"  {line}")
            if len(diff_lines) > 10:
                console.print(f"[dim]  ... ({len(diff_lines) - 10} more diff lines)[/dim]")
        else:
            # Normal/debug mode: panel display
            console.print(Panel(diff_text, title=f"[DIFF] {path}", border_style="yellow"))
    else:
        console.print(f"[dim]No changes in {path}[/dim]")


def show_file_preview(content: str, path: str, max_lines: int = 20) -> None:
    """Show a syntax-highlighted preview of file content"""
    ext = path.split(".")[-1] if "." in path else "txt"
    content_lines = content.split("\n")
    line_count = len(content_lines)
    
    if is_minimal_mode():
        # Minimal mode: clean display without panel
        console.print(f"[cyan][FILE] {path} ({line_count} lines)[/cyan]")
        if content_lines:
            # Show first few lines
            preview_lines = content_lines[:min(3, len(content_lines))]
            for i, line in enumerate(preview_lines, 1):
                console.print(f"  {i:3d}: {line}")
            if line_count > 3:
                console.print(f"[dim]  ... ({line_count - 3} more lines)[/dim]")
    else:
        # Normal/debug mode: panel display with syntax highlighting
        preview_lines = content_lines[:max_lines]
        preview = "\n".join(preview_lines)
        if len(content_lines) > max_lines:
            more_lines = len(content_lines) - max_lines
            preview += f"\n... ({more_lines} more lines)"

        syntax = Syntax(preview, ext, theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title=f"[FILE] {path}", border_style="cyan"))


def warn_large_file(size: int, threshold: int = 100000) -> bool:
    """Warn if file is large. Returns True if file is large."""
    if size > threshold:
        console.print(
            f"[yellow]⚠️  Warning:[/yellow] Large file detected ({size:,} bytes). "
            f"Reading may take a moment..."
        )
        return True
    return False


def display_thinking(
    reasoning_content: str, expanded: bool = False, max_preview_length: int = 80
) -> None:
    """
    Display reasoning/thinking content from models like DeepSeek.

    Args:
        reasoning_content: The raw thinking content from the model
        expanded: If True, show full content. If False, show minimal one-liner.
        max_preview_length: Maximum characters for the preview
    """
    if not reasoning_content:
        return

    # Clean up the content
    content = reasoning_content.strip()
    if not content:
        return

    if is_minimal_mode():
        # In minimal mode, never show panels
        if expanded:
            # Show full thinking content without panel
            console.print(f"[dim][THINK] Thinking:[/dim]")
            lines = content.split("\n")
            for line in lines:
                console.print(f"[dim]  {line}[/dim]")
        else:
            # Minimal one-liner preview
            lines = content.split("\n")
            first_line = lines[0].strip() if lines else ""
            if len(first_line) > max_preview_length:
                preview = first_line[:max_preview_length] + "..."
            else:
                preview = first_line
            if preview:
                console.print(f"[dim][THINK] {preview}[/dim]")
    else:
        # Normal/debug mode
        if expanded:
            # Full display with panel
            console.print(
                Panel(
                    content,
                    title="[bold yellow][THINK] Thinking[/bold yellow]",
                    border_style="yellow",
                    padding=(0, 1),
                )
            )
        else:
            # Minimal one-liner preview (no panel, no box)
            lines = content.split("\n")
            first_line = lines[0].strip() if lines else ""
            if len(first_line) > max_preview_length:
                preview = first_line[:max_preview_length] + "..."
            else:
                preview = first_line
            if preview:
                console.print(f"[dim][THINK] {preview}[/dim]")


def display_reasoning_details(
    reasoning_details: list, expanded: bool = False, max_preview_length: int = 80
) -> None:
    """
    Display reasoning_details from OpenRouter reasoning models (MiMo, Claude, etc.).
    
    Args:
        reasoning_details: List of reasoning detail objects from API response
        expanded: If True, show full content. If False, show minimal preview.
        max_preview_length: Maximum characters for the preview
    """
    if not reasoning_details or not isinstance(reasoning_details, list):
        return
    
    if is_minimal_mode():
        # In minimal mode, never show panels
        if expanded:
            # Show all reasoning details without panels
            for detail in reasoning_details:
                detail_type = detail.get("type", "")
                if detail_type == "reasoning.text":
                    content = detail.get("text", "")
                    if content:
                        console.print(f"[dim][THINK] Thinking:[/dim]")
                        lines = content.split("\n")
                        for line in lines:
                            console.print(f"[dim]  {line}[/dim]")
                elif detail_type == "reasoning.summary":
                    summary = detail.get("summary", "")
                    if summary:
                        console.print(f"[dim][SUM] Summary: {summary}[/dim]")
                elif detail_type == "reasoning.encrypted":
                    console.print(f"[dim][LOCK] Encrypted reasoning data[/dim]")
        else:
            # Minimal preview - show first text or summary
            for detail in reasoning_details:
                detail_type = detail.get("type", "")
                if detail_type == "reasoning.text":
                    content = detail.get("text", "")
                    if content:
                        lines = content.split("\n")
                        first_line = lines[0].strip() if lines else ""
                        if len(first_line) > max_preview_length:
                            preview = first_line[:max_preview_length] + "..."
                        else:
                            preview = first_line
                        if preview:
                            console.print(f"[dim][THINK] {preview}[/dim]")
                        break
                elif detail_type == "reasoning.summary":
                    summary = detail.get("summary", "")
                    if summary:
                        if len(summary) > max_preview_length:
                            preview = summary[:max_preview_length] + "..."
                        else:
                            preview = summary
                        if preview:
                            console.print(f"[dim][SUM] {preview}[/dim]")
                        break
    else:
        # Normal/debug mode
        if expanded:
            # Full display with panel
            for detail in reasoning_details:
                detail_type = detail.get("type", "")
                if detail_type == "reasoning.text":
                    content = detail.get("text", "")
                    if content:
                        console.print(
                            Panel(
                                content,
                                title=f"[bold yellow][THINK] {detail_type}[/bold yellow]",
                                border_style="yellow",
                                padding=(0, 1),
                            )
                        )
                elif detail_type == "reasoning.summary":
                    summary = detail.get("summary", "")
                    if summary:
                        console.print(
                            Panel(
                                summary,
                                title=f"[bold yellow][SUM] Summary[/bold yellow]",
                                border_style="yellow",
                                padding=(0, 1),
                            )
                        )
                elif detail_type == "reasoning.encrypted":
                    console.print(
                        Panel(
                            "[dim]Encrypted reasoning data[/dim]",
                            title=f"[bold yellow][LOCK] Encrypted[/bold yellow]",
                            border_style="yellow",
                            padding=(0, 1),
                        )
                    )
        else:
            # Minimal preview - show first text or summary
            for detail in reasoning_details:
                detail_type = detail.get("type", "")
                if detail_type == "reasoning.text":
                    content = detail.get("text", "")
                    if content:
                        lines = content.split("\n")
                        first_line = lines[0].strip() if lines else ""
                        if len(first_line) > max_preview_length:
                            preview = first_line[:max_preview_length] + "..."
                        else:
                            preview = first_line
                        if preview:
                            console.print(f"[dim][THINK] {preview}[/dim]")
                        break
                elif detail_type == "reasoning.summary":
                    summary = detail.get("summary", "")
                    if summary:
                        if len(summary) > max_preview_length:
                            preview = summary[:max_preview_length] + "..."
                        else:
                            preview = summary
                        if preview:
                            console.print(f"[dim][SUM] {preview}[/dim]")
                        break


def display_progress_summary(
    operation: str, completed: int, total: int = None, details: str = ""
) -> None:
    """
    Display a progress summary for operations.

    Args:
        operation: Name of the operation
        completed: Number completed
        total: Total count (if known)
        details: Additional details
    """
    if total:
        percent = (completed / total) * 100
        progress_text = f"[cyan]{operation}:[/cyan] {completed}/{total} ({percent:.0f}%)"
    else:
        progress_text = f"[cyan]{operation}:[/cyan] {completed} processed"

    if details:
        progress_text += f" - {details}"

    console.print(progress_text)


def display_operation_complete(
    operation: str, success: bool = True, summary: str = "", duration_ms: float = None
) -> None:
    """
    Display operation completion status.

    Args:
        operation: Name of the operation
        success: Whether it succeeded
        summary: Brief summary of results
        duration_ms: Duration in milliseconds
    """
    icon = "[OK]" if success else "[X]"
    color = "green" if success else "red"

    parts = [f"[{color}]{icon}[/{color}] {operation}"]

    if summary:
        parts.append(f"- {summary}")

    if duration_ms is not None:
        if duration_ms < 1000:
            parts.append(f"[dim]({duration_ms:.0f}ms)[/dim]")
        else:
            parts.append(f"[dim]({duration_ms/1000:.1f}s)[/dim]")

    console.print(" ".join(parts))


def display_tool_execution(
    tool_name: str,
    arguments: Dict[str, Any],
    result: Dict[str, Any],
    duration_ms: float,
    show_arguments: bool = False,
) -> None:
    """
    Display tool execution with mode awareness.
    
    Args:
        tool_name: Name of the tool executed
        arguments: Tool arguments
        result: Tool result dictionary
        duration_ms: Execution duration in milliseconds
        show_arguments: Force showing arguments (for debug mode)
    """
    success = result.get("success", False)
    
    if is_minimal_mode():
        # Minimal mode: simple icon and duration
        icon = "⚙️"
        color = "dim"
        if duration_ms > 0:
            if duration_ms < 1000:
                console.print(f"[{color}]{icon} {tool_name} ({duration_ms:.0f}ms)[/{color}]")
            else:
                console.print(f"[{color}]{icon} {tool_name} ({duration_ms/1000:.1f}s)[/{color}]")
        else:
            console.print(f"[{color}]{icon} {tool_name}[/{color}]")
    
    elif is_debug_mode():
        # Debug mode: detailed information
        icon = "✓" if success else "✗"
        color = "green" if success else "red"
        
        console.print(f"[{color}][TOOL] {tool_name} {icon}[/{color}]")
        console.print(f"  [dim]Duration: {duration_ms:.2f}ms[/dim]")
        
        if show_arguments or is_debug_mode():
            # Show arguments in debug mode
            try:
                import json
                args_preview = json.dumps(arguments, indent=2)
                # Limit preview length
                if len(args_preview) > 500:
                    args_preview = args_preview[:500] + "..."
                console.print(f"  [dim]Arguments: {args_preview}[/dim]")
            except:
                console.print(f"  [dim]Arguments: {str(arguments)[:200]}[/dim]")
        
        # Show error if any
        if "error" in result:
            console.print(f"  [red]Error: {result.get('error')}[/red]")
        
        # Show metadata if available
        if "metadata" in result:
            console.print(f"  [dim]Metadata: {result.get('metadata')}[/dim]")
    
    else:
        # Normal mode: current behavior (tools display their own output)
        # We could optionally show a simple execution message here
        icon = "⚙️"
        color = "dim"
        if duration_ms > 0:
            if duration_ms < 1000:
                console.print(f"[{color}]{icon} {tool_name} ({duration_ms:.0f}ms)[/{color}]")
            else:
                console.print(f"[{color}]{icon} {tool_name} ({duration_ms/1000:.1f}s)[/{color}]")
