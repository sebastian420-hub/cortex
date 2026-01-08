"""Git integration tools"""

import subprocess
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from .base import Tool
from ..models import PermissionMode


class GitStatusTool(Tool):
    """Tool for showing git status"""
    
    def execute(self) -> Dict[str, Any]:
        """Show git status"""
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=10
            )
            
            if result.returncode != 0:
                return {"error": "Not a git repository or git command failed"}
            
            output = result.stdout
            
            if self.console:
                self.console.print(Panel(
                    output or "[dim]No changes[/dim]",
                    title="📊 Git Status",
                    border_style="cyan"
                ))
            
            return {
                "success": True,
                "output": output,
                "has_changes": bool(output.strip())
            }
        except Exception as e:
            return {"error": str(e)}


class GitDiffTool(Tool):
    """Tool for showing git diff"""
    
    def execute(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Show git diff for a file or all changes"""
        try:
            cmd = ["git", "diff"]
            if path:
                cmd.append(path)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=10
            )
            
            if result.returncode != 0:
                return {"error": "Git diff failed"}
            
            output = result.stdout
            
            if self.console:
                if output:
                    self.console.print(Panel(
                        output,
                        title=f"📊 Git Diff{' - ' + path if path else ''}",
                        border_style="yellow"
                    ))
                else:
                    self.console.print("[dim]No changes to show[/dim]")
            
            return {
                "success": True,
                "output": output,
                "has_changes": bool(output.strip())
            }
        except Exception as e:
            return {"error": str(e)}


class GitCommitTool(Tool):
    """Tool for committing changes"""
    
    def execute(self, message: str) -> Dict[str, Any]:
        """Commit changes with message"""
        
        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]⏸  PLAN MODE:[/yellow] Would commit: {message}")
            return {"success": False, "message": "Plan mode - no commits allowed"}
        
        if self.console:
            self.console.print(f"[blue]🔧 Git Commit:[/blue] {message}")
        
        # Ask for approval
        if self.permission_mode == PermissionMode.NORMAL and self.console:
            if not Confirm.ask(f"[bold]Commit with message: '{message}'?[/bold]"):
                if self.console:
                    self.console.print("[red]✗[/red] Cancelled by user")
                return {"success": False, "message": "Cancelled by user"}
        
        try:
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=10
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr or "Commit failed",
                    "output": result.stdout
                }
            
            if self.console:
                self.console.print(Panel(
                    result.stdout,
                    title="✓ Commit Successful",
                    border_style="green"
                ))
            
            return {
                "success": True,
                "output": result.stdout
            }
        except Exception as e:
            return {"error": str(e)}


class GitLogTool(Tool):
    """Tool for showing git log"""
    
    def execute(self, limit: int = 10) -> Dict[str, Any]:
        """Show recent git commits"""
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--oneline"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=10
            )
            
            if result.returncode != 0:
                return {"error": "Git log failed"}
            
            output = result.stdout
            
            if self.console:
                self.console.print(Panel(
                    output or "[dim]No commits[/dim]",
                    title=f"📜 Git Log (last {limit})",
                    border_style="cyan"
                ))
            
            return {
                "success": True,
                "output": output,
                "commits": output.strip().split('\n') if output.strip() else []
            }
        except Exception as e:
            return {"error": str(e)}

