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


class ReadFileTool(Tool):
    """Tool for reading files"""
    
    def execute(self, path: str) -> Dict[str, Any]:
        """Read file contents"""
        if self.console:
            self.console.print(f"[cyan]📖 Reading:[/cyan] {path}")
        
        try:
            full_path = validate_path(self.project_dir, path)
            
            if not full_path.exists():
                return {"error": f"File not found: {path}"}
            
            if not full_path.is_file():
                return {"error": f"Path is not a file: {path}"}
            
            content = full_path.read_text()
            
            # Show preview
            if self.console:
                ext = full_path.suffix.lstrip('.') or "txt"
                preview_lines = content.split('\n')[:15]
                preview = '\n'.join(preview_lines)
                if len(content.split('\n')) > 15:
                    preview += f"\n... ({len(content.split('\n')) - 15} more lines)"
                
                syntax = Syntax(preview, ext, theme="monokai", line_numbers=True)
                self.console.print(Panel(syntax, title=f"📄 {path}", border_style="cyan"))
            
            return {
                "success": True,
                "content": content,
                "lines": len(content.split('\n')),
                "size": len(content)
            }
            
        except SecurityError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}


class WriteFileTool(Tool):
    """Tool for writing files"""
    
    def execute(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to file"""
        
        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]⏸  PLAN MODE:[/yellow] Would write to {path}")
            return {"success": False, "message": "Plan mode - no writes allowed"}
        
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
                preview_lines = content.split('\n')[:20]
                preview = '\n'.join(preview_lines)
                if len(content.split('\n')) > 20:
                    preview += f"\n... ({len(content.split('\n')) - 20} more lines)"
                
                syntax = Syntax(preview, ext, theme="monokai", line_numbers=True)
                self.console.print(Panel(syntax, title=f"New content: {path}", border_style="yellow"))
            
            # Ask for approval
            if self.permission_mode == PermissionMode.NORMAL and self.console:
                if not Confirm.ask(f"[bold]Write to {path}?[/bold]"):
                    if self.console:
                        self.console.print("[red]✗[/red] Cancelled by user")
                    return {"success": False, "message": "Cancelled by user"}
            
            # Write file
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            
            if self.console:
                self.console.print(f"[green]✓[/green] Wrote {len(content)} bytes to {path}")
            
            return {"success": True, "bytes_written": len(content)}
            
        except SecurityError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

