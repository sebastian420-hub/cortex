"""Display helpers for better UI"""

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.diff import Diff
from typing import Optional

console = Console()


def show_file_diff(old_content: str, new_content: str, path: str) -> None:
    """Show a visual diff between old and new file content"""
    diff = Diff(old_content, new_content)
    console.print(Panel(
        diff,
        title=f"📊 Diff: {path}",
        border_style="yellow"
    ))


def show_file_preview(content: str, path: str, max_lines: int = 20) -> None:
    """Show a syntax-highlighted preview of file content"""
    ext = path.split('.')[-1] if '.' in path else "txt"
    preview_lines = content.split('\n')[:max_lines]
    preview = '\n'.join(preview_lines)
    if len(content.split('\n')) > max_lines:
        preview += f"\n... ({len(content.split('\n')) - max_lines} more lines)"
    
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

