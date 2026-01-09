"""File I/O tools"""

from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm

from .base import Tool
from ..core.security import validate_path, SecurityError
from ..models import PermissionMode
from ..utils.errors import create_error_response, create_success_response, create_permission_denial, ErrorType


class ReadFileTool(Tool):
    """Tool for reading files"""
    
    def execute(self, path: str) -> Dict[str, Any]:
        """Read file contents"""
        if self.console:
            self.console.print(f"[cyan]📖 Reading:[/cyan] {path}")
        
        try:
            full_path = validate_path(self.project_dir, path)
            
            if not full_path.exists():
                return create_error_response(
                    f"File not found: {path}",
                    ErrorType.NOT_FOUND,
                    {"path": path}
                )
            
            if not full_path.is_file():
                return create_error_response(
                    f"Path is not a file: {path}",
                    ErrorType.VALIDATION,
                    {"path": path},
                    retryable=True
                )
            
            content = full_path.read_text()
            
            # Show preview
            if self.console:
                ext = full_path.suffix.lstrip('.') or "txt"
                content_lines = content.split('\n')
                preview_lines = content_lines[:15]
                preview = '\n'.join(preview_lines)
                if len(content_lines) > 15:
                    more_lines = len(content_lines) - 15
                    preview += f"\n... ({more_lines} more lines)"
                
                syntax = Syntax(preview, ext, theme="monokai", line_numbers=True)
                self.console.print(Panel(syntax, title=f"📄 {path}", border_style="cyan"))
            
            return create_success_response({
                "content": content,
                "lines": len(content.split('\n')),
                "size": len(content)
            })
            
        except SecurityError as e:
            return create_error_response(
                str(e),
                ErrorType.SECURITY,
                {"path": path}
            )
        except Exception as e:
            return create_error_response(
                str(e),
                ErrorType.EXECUTION,
                {"path": path},
                retryable=True
            )


class WriteFileTool(Tool):
    """Tool for writing files"""
    
    def execute(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to file"""
        
        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]⏸  PLAN MODE:[/yellow] Would write to {path}")
            return create_permission_denial(
                "Plan mode - no writes allowed",
                "write_file",
                {"path": path, "permission_mode": "plan"}
            )
        
        if self.console:
            self.console.print(f"[yellow]📝 Writing:[/yellow] {path}")
        
        try:
            full_path = validate_path(self.project_dir, path)
            
            # Show diff if file exists
            if full_path.exists():
                old_content = full_path.read_text()
                if self.console:
                    self.console.print(Panel(
                        f"[red]- Old ({len(old_content)} bytes)[/red]\n"
                        f"[green]+ New ({len(content)} bytes)[/green]",
                        title="📊 Changes"
                    ))
            
            # Show preview of new content
            if self.console:
                ext = full_path.suffix.lstrip('.') or "txt"
                content_lines = content.split('\n')
                preview_lines = content_lines[:20]
                preview = '\n'.join(preview_lines)
                if len(content_lines) > 20:
                    more_lines = len(content_lines) - 20
                    preview += f"\n... ({more_lines} more lines)"
                
                syntax = Syntax(preview, ext, theme="monokai", line_numbers=True)
                self.console.print(Panel(syntax, title=f"New content: {path}", border_style="yellow"))
            
            # Ask for approval
            if self.permission_mode == PermissionMode.NORMAL and self.console:
                if not Confirm.ask(f"[bold]Write to {path}?[/bold]"):
                    if self.console:
                        self.console.print("[red]✗[/red] Cancelled by user")
                    return create_permission_denial(
                        "Cancelled by user",
                        "write_file",
                        {"path": path}
                    )
            
            # Write file
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            
            if self.console:
                self.console.print(f"[green]✓[/green] Wrote {len(content)} bytes to {path}")
            
            return create_success_response({"bytes_written": len(content)})
            
        except SecurityError as e:
            return create_error_response(
                str(e),
                ErrorType.SECURITY,
                {"path": path}
            )
        except Exception as e:
            return create_error_response(
                str(e),
                ErrorType.EXECUTION,
                {"path": path},
                retryable=True
            )

