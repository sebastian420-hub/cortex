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
        old_lines,
        new_lines,
        fromfile=f"old/{path}",
        tofile=f"new/{path}",
        lineterm=""
    )
    
    diff_text = "".join(diff)
    
    if diff_text:
        console.print(Panel(
            diff_text,
            title=f"📊 Diff: {path}",
            border_style="yellow"
        ))
    else:
        console.print(f"[dim]No changes in {path}[/dim]")


def show_file_preview(content: str, path: str, max_lines: int = 20) -> None:
    """Show a syntax-highlighted preview of file content"""
    ext = path.split('.')[-1] if '.' in path else "txt"
    content_lines = content.split('\n')
    preview_lines = content_lines[:max_lines]
    preview = '\n'.join(preview_lines)
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

