"""Display helpers for better UI"""

import difflib
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from typing import Optional

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
        console.print(Panel(diff_text, title=f"📊 Diff: {path}", border_style="yellow"))
    else:
        console.print(f"[dim]No changes in {path}[/dim]")


def show_file_preview(content: str, path: str, max_lines: int = 20) -> None:
    """Show a syntax-highlighted preview of file content"""
    ext = path.split(".")[-1] if "." in path else "txt"
    content_lines = content.split("\n")
    preview_lines = content_lines[:max_lines]
    preview = "\n".join(preview_lines)
    if len(content_lines) > max_lines:
        more_lines = len(content_lines) - max_lines
        preview += f"\n... ({more_lines} more lines)"

    syntax = Syntax(preview, ext, theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=f"📄 {path}", border_style="cyan"))


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

    if expanded:
        # Full display with panel
        console.print(
            Panel(
                content,
                title="[bold yellow]💭 Thinking[/bold yellow]",
                border_style="yellow",
                padding=(0, 1),
            )
        )
    else:
        # Minimal one-liner preview (no panel, no box)
        lines = content.split("\n")
        first_line = lines[0].strip() if lines else ""

        # Truncate if too long
        if len(first_line) > max_preview_length:
            preview = first_line[:max_preview_length] + "..."
        else:
            preview = first_line

        # Simple dim one-liner
        if preview:
            console.print(f"[dim]💭 {preview}[/dim]")


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
    icon = "✓" if success else "✗"
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
