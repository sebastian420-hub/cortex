"""Command execution tools"""

import subprocess
from typing import Dict, Any, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from .base import Tool
from ..core.security import is_dangerous_command
from ..models import PermissionMode
from ..ui.modes import should_show_panels, is_minimal_mode
from ..utils.errors import (
    create_error_response,
    create_success_response,
    create_permission_denial,
    ErrorType,
)


class ExecuteCommandTool(Tool):
    """Tool for executing shell commands"""

    default_timeout: int = 30
    timeout_category: str = "default"

    def _validate_python_command(self, command: str) -> Tuple[bool, str]:
        """
        Validate Python commands for safety.

        Args:
            command: The command string to validate

        Returns:
            Tuple of (is_safe, error_message)
        """
        if not command.strip().startswith("python"):
            return True, ""  # Not a Python command, use default validation

        # Dangerous patterns that could erase or modify files
        dangerous_patterns = [
            "truncate()",  # Empty file
            "write('')",  # Write empty string
            'write("")',  # Write empty string (double quotes)
            ".remove(",  # Delete file
            ".unlink(",  # Delete file (pathlib)
            "os.remove(",  # Delete file
            "os.unlink(",  # Delete file
            "shutil.rmtree(",  # Delete directory
            "os.rmdir(",  # Delete directory
            "pathlib.Path",  # Pathlib operations - combined with above patterns
        ]

        # Check for dangerous patterns
        for pattern in dangerous_patterns:
            if pattern in command:
                return False, f"Dangerous pattern '{pattern}' detected in Python command"

        return True, ""

    def execute(self, command: str, reason: str = "") -> Dict[str, Any]:
        """Execute shell command"""

        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]PLAN MODE:[/yellow] Would execute: {command}")
            return create_permission_denial(
                "Plan mode - no commands allowed",
                "execute_command",
                {"command": command, "permission_mode": "plan"},
            )

        if self.console:
            self.console.print(f"[blue]Command:[/blue] {command}")
            if reason:
                self.console.print(f"[dim]Reason: {reason}[/dim]")

        # Safety check - Python command validation
        is_safe, error_msg = self._validate_python_command(command)
        if not is_safe:
            if self.console:
                self.console.print(f"[red]BLOCKED:[/red] {error_msg}")
            return create_error_response(
                error_msg,
                ErrorType.SECURITY,
                {"command": command, "reason": "dangerous_python_pattern"},
            )

        # Safety check - general dangerous commands
        if is_dangerous_command(command):
            if self.console:
                self.console.print("[red]BLOCKED:[/red] Dangerous command detected")
            return create_error_response(
                "Dangerous command blocked for safety", ErrorType.SECURITY, {"command": command}
            )

        # Ask for approval
        if self.permission_mode == PermissionMode.NORMAL and self.console:
            if not Confirm.ask(f"[bold]Execute: {command}?[/bold]"):
                if self.console:
                    self.console.print("[red]?[/red] Cancelled by user")
                return create_permission_denial(
                    "Cancelled by user", "execute_command", {"command": command}
                )

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                command,
                shell=True,  # nosec
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )

            output = result.stdout + result.stderr

            if self.console:
                if result.returncode == 0:
                    if should_show_panels():
                        self.console.print(
                            Panel(
                                output or "[dim]Command completed successfully[/dim]",
                                title="? Output",
                                border_style="green",
                            )
                        )
                    else:
                        # Minimal mode - simple but clear output
                        if output:
                            self.console.print(f"[green]? Output:[/green]\n{output.strip()}")
                        else:
                            self.console.print("[green]? Command completed successfully[/green]")
                else:
                    if should_show_panels():
                        self.console.print(
                            Panel(
                                output,
                                title=f"? Failed (exit code {result.returncode})",
                                border_style="red",
                            )
                        )
                    else:
                        # Minimal mode - simple but clear output
                        self.console.print(
                            f"[red]? Failed (exit code {result.returncode}):[/red]\n{output.strip()}"  # noqa: E501
                        )

            if result.returncode == 0:
                return create_success_response({"output": output, "exit_code": result.returncode})
            else:
                return create_error_response(
                    f"Command failed with exit code {result.returncode}",
                    ErrorType.EXECUTION,
                    {"command": command, "exit_code": result.returncode, "output": output},
                    retryable=True,
                )

        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Command timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"command": command, "timeout": timeout},
                retryable=True,
            )
        except Exception as e:
            return create_error_response(
                str(e), ErrorType.EXECUTION, {"command": command}, retryable=True
            )
