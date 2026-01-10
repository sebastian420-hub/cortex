"""Git integration tools"""

import subprocess
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from .base import Tool
from ..models import PermissionMode
from ..utils.errors import create_error_response, create_success_response, create_permission_denial, ErrorType


class GitStatusTool(Tool):
    """Tool for showing git status"""

    default_timeout: int = 10
    timeout_category: str = "git"

    def execute(self) -> Dict[str, Any]:
        """Show git status"""
        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout
            )
            
            if result.returncode != 0:
                return create_error_response(
                    "Not a git repository or git command failed",
                    ErrorType.EXECUTION,
                    {"stderr": result.stderr},
                    retryable=True
                )
            
            output = result.stdout
            
            if self.console:
                self.console.print(Panel(
                    output or "[dim]No changes[/dim]",
                    title="📊 Git Status",
                    border_style="cyan"
                ))
            
            return create_success_response({
                "output": output,
                "has_changes": bool(output.strip())
            })
        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git status timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"timeout": timeout},
                retryable=True
            )
        except Exception as e:
            return create_error_response(
                str(e),
                ErrorType.EXECUTION,
                retryable=True
            )


class GitDiffTool(Tool):
    """Tool for showing git diff"""

    default_timeout: int = 10
    timeout_category: str = "git"

    def execute(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Show git diff for a file or all changes"""
        try:
            timeout = self.get_timeout()
            cmd = ["git", "diff"]
            if path:
                cmd.append(path)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout
            )
            
            if result.returncode != 0:
                return create_error_response(
                    "Git diff failed",
                    ErrorType.EXECUTION,
                    {"path": path, "stderr": result.stderr},
                    retryable=True
                )
            
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
            
            return create_success_response({
                "output": output,
                "has_changes": bool(output.strip())
            })
        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git diff timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"path": path, "timeout": timeout},
                retryable=True
            )
        except Exception as e:
            return create_error_response(
                str(e),
                ErrorType.EXECUTION,
                {"path": path},
                retryable=True
            )


class GitCommitTool(Tool):
    """Tool for committing changes"""

    default_timeout: int = 10
    timeout_category: str = "git"

    def execute(self, message: str) -> Dict[str, Any]:
        """Commit changes with message"""

        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]⏸  PLAN MODE:[/yellow] Would commit: {message}")
            return create_permission_denial(
                "Plan mode - no commits allowed",
                "git_commit",
                {"message": message, "permission_mode": "plan"}
            )
        
        if self.console:
            self.console.print(f"[blue]🔧 Git Commit:[/blue] {message}")
        
        # Ask for approval
        if self.permission_mode == PermissionMode.NORMAL and self.console:
            if not Confirm.ask(f"[bold]Commit with message: '{message}'?[/bold]"):
                if self.console:
                    self.console.print("[red]✗[/red] Cancelled by user")
                return create_permission_denial(
                    "Cancelled by user",
                    "git_commit",
                    {"message": message}
                )
        
        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout
            )

            if result.returncode != 0:
                return create_error_response(
                    result.stderr or "Commit failed",
                    ErrorType.EXECUTION,
                    {"message": message, "stdout": result.stdout, "stderr": result.stderr},
                    retryable=True
                )

            if self.console:
                self.console.print(Panel(
                    result.stdout,
                    title="✓ Commit Successful",
                    border_style="green"
                ))

            return create_success_response({
                "output": result.stdout
            })
        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git commit timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"message": message, "timeout": timeout},
                retryable=True
            )
        except Exception as e:
            return create_error_response(
                str(e),
                ErrorType.EXECUTION,
                {"message": message},
                retryable=True
            )


class GitLogTool(Tool):
    """Tool for showing git log"""

    default_timeout: int = 10
    timeout_category: str = "git"

    def execute(self, limit: int = 10) -> Dict[str, Any]:
        """Show recent git commits"""
        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--oneline"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout
            )
            
            if result.returncode != 0:
                return create_error_response(
                    "Git log failed",
                    ErrorType.EXECUTION,
                    {"limit": limit, "stderr": result.stderr},
                    retryable=True
                )
            
            output = result.stdout
            
            if self.console:
                self.console.print(Panel(
                    output or "[dim]No commits[/dim]",
                    title=f"📜 Git Log (last {limit})",
                    border_style="cyan"
                ))
            
            return create_success_response({
                "output": output,
                "commits": output.strip().split('\n') if output.strip() else []
            })
        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git log timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"limit": limit, "timeout": timeout},
                retryable=True
            )
        except Exception as e:
            return create_error_response(
                str(e),
                ErrorType.EXECUTION,
                {"limit": limit},
                retryable=True
            )

