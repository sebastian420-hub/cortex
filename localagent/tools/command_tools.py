"""Command execution tools"""

import subprocess
from typing import Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from .base import Tool
from ..core.security import is_dangerous_command
from ..models import PermissionMode
from ..utils.errors import create_error_response, create_success_response, create_permission_denial, ErrorType


class ExecuteCommandTool(Tool):
    """Tool for executing shell commands"""
    
    def execute(self, command: str, reason: str = "") -> Dict[str, Any]:
        """Execute shell command"""
        
        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]⏸  PLAN MODE:[/yellow] Would execute: {command}")
            return create_permission_denial(
                "Plan mode - no commands allowed",
                "execute_command",
                {"command": command, "permission_mode": "plan"}
            )
        
        if self.console:
            self.console.print(f"[blue]🔧 Command:[/blue] {command}")
            if reason:
                self.console.print(f"[dim]Reason: {reason}[/dim]")
        
        # Safety check
        if is_dangerous_command(command):
            if self.console:
                self.console.print("[red]🛑 BLOCKED:[/red] Dangerous command detected")
            return create_error_response(
                "Dangerous command blocked for safety",
                ErrorType.SECURITY,
                {"command": command}
            )
        
        # Ask for approval
        if self.permission_mode == PermissionMode.NORMAL and self.console:
            if not Confirm.ask(f"[bold]Execute: {command}?[/bold]"):
                if self.console:
                    self.console.print("[red]✗[/red] Cancelled by user")
                return create_permission_denial(
                    "Cancelled by user",
                    "execute_command",
                    {"command": command}
                )
        
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
            
            if result.returncode == 0:
                return create_success_response({
                    "output": output,
                    "exit_code": result.returncode
                })
            else:
                return create_error_response(
                    f"Command failed with exit code {result.returncode}",
                    ErrorType.EXECUTION,
                    {"command": command, "exit_code": result.returncode, "output": output},
                    retryable=True
                )
            
        except subprocess.TimeoutExpired:
            return create_error_response(
                "Command timed out after 30 seconds",
                ErrorType.TIMEOUT,
                {"command": command},
                retryable=True
            )
        except Exception as e:
            return create_error_response(
                str(e),
                ErrorType.EXECUTION,
                {"command": command},
                retryable=True
            )

