"""Command execution tools"""

import subprocess
from typing import Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from .base import Tool
from ..core.security import is_dangerous_command
from ..models import PermissionMode


class ExecuteCommandTool(Tool):
    """Tool for executing shell commands"""
    
    def execute(self, command: str, reason: str = "") -> Dict[str, Any]:
        """Execute shell command"""
        
        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]⏸  PLAN MODE:[/yellow] Would execute: {command}")
            return {"success": False, "message": "Plan mode - no commands allowed"}
        
        if self.console:
            self.console.print(f"[blue]🔧 Command:[/blue] {command}")
            if reason:
                self.console.print(f"[dim]Reason: {reason}[/dim]")
        
        # Safety check
        if is_dangerous_command(command):
            if self.console:
                self.console.print("[red]🛑 BLOCKED:[/red] Dangerous command detected")
            return {"error": "Dangerous command blocked for safety"}
        
        # Ask for approval
        if self.permission_mode == PermissionMode.NORMAL and self.console:
            if not Confirm.ask(f"[bold]Execute: {command}?[/bold]"):
                if self.console:
                    self.console.print("[red]✗[/red] Cancelled by user")
                return {"success": False, "message": "Cancelled by user"}
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            
            if self.console:
                if result.returncode == 0:
                    self.console.print(Panel(
                        output or "[dim]Command completed successfully[/dim]",
                        title="✓ Output",
                        border_style="green"
                    ))
                else:
                    self.console.print(Panel(
                        output,
                        title=f"✗ Failed (exit code {result.returncode})",
                        border_style="red"
                    ))
            
            return {
                "success": result.returncode == 0,
                "output": output,
                "exit_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out after 30 seconds"}
        except Exception as e:
            return {"error": str(e)}

