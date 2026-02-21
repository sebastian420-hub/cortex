"""Git integration tools"""

import subprocess
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from .base import Tool
from ..models import PermissionMode
from ..utils.errors import (
    create_error_response,
    create_success_response,
    create_permission_denial,
    ErrorType,
)


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
                timeout=timeout,
            )

            if result.returncode != 0:
                return create_error_response(
                    "Not a git repository or git command failed",
                    ErrorType.EXECUTION,
                    {"stderr": result.stderr},
                    retryable=True,
                )

            output = result.stdout

            if self.console:
                self.console.print(
                    Panel(
                        output or "[dim]No changes[/dim]",
                        title="?? Git Status",
                        border_style="cyan",
                    )
                )

            return create_success_response({"output": output, "has_changes": bool(output.strip())})
        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git status timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"timeout": timeout},
                retryable=True,
            )
        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION, retryable=True)


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
                cmd, capture_output=True, text=True, cwd=self.project_dir, timeout=timeout
            )

            if result.returncode != 0:
                return create_error_response(
                    "Git diff failed",
                    ErrorType.EXECUTION,
                    {"path": path, "stderr": result.stderr},
                    retryable=True,
                )

            output = result.stdout

            if self.console:
                if output:
                    self.console.print(
                        Panel(
                            output,
                            title=f"?? Git Diff{' - ' + path if path else ''}",
                            border_style="yellow",
                        )
                    )
                else:
                    self.console.print("[dim]No changes to show[/dim]")

            return create_success_response({"output": output, "has_changes": bool(output.strip())})
        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git diff timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"path": path, "timeout": timeout},
                retryable=True,
            )
        except Exception as e:
            return create_error_response(
                str(e), ErrorType.EXECUTION, {"path": path}, retryable=True
            )


class GitCommitTool(Tool):
    """Tool for committing changes"""

    default_timeout: int = 10
    timeout_category: str = "git"

    def execute(self, message: str) -> Dict[str, Any]:
        """Commit changes with message"""

        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]PLAN MODE:[/yellow] Would commit: {message}")
            return create_permission_denial(
                "Plan mode - no commits allowed",
                "git_commit",
                {"message": message, "permission_mode": "plan"},
            )

        if self.console:
            self.console.print(f"[blue]?? Git Commit:[/blue] {message}")

        # Ask for approval
        if (
            self.permission_mode == PermissionMode.NORMAL
            and self.console
            and self.permission_mode != PermissionMode.AUTO_APPROVE
        ):
            if not Confirm.ask(f"[bold]Commit with message: '{message}'?[/bold]"):
                if self.console:
                    self.console.print("[red]?[/red] Cancelled by user")
                return create_permission_denial(
                    "Cancelled by user", "git_commit", {"message": message}
                )

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )

            if result.returncode != 0:
                return create_error_response(
                    result.stderr or "Commit failed",
                    ErrorType.EXECUTION,
                    {"message": message, "stdout": result.stdout, "stderr": result.stderr},
                    retryable=True,
                )

            if self.console:
                self.console.print(
                    Panel(result.stdout, title="? Commit Successful", border_style="green")
                )

            return create_success_response({"output": result.stdout})
        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git commit timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"message": message, "timeout": timeout},
                retryable=True,
            )
        except Exception as e:
            return create_error_response(
                str(e), ErrorType.EXECUTION, {"message": message}, retryable=True
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
                timeout=timeout,
            )

            if result.returncode != 0:
                return create_error_response(
                    "Git log failed",
                    ErrorType.EXECUTION,
                    {"limit": limit, "stderr": result.stderr},
                    retryable=True,
                )

            output = result.stdout

            if self.console:
                self.console.print(
                    Panel(
                        output or "[dim]No commits[/dim]",
                        title=f"?? Git Log (last {limit})",
                        border_style="cyan",
                    )
                )

            return create_success_response(
                {"output": output, "commits": output.strip().split("\n") if output.strip() else []}
            )
        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git log timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"limit": limit, "timeout": timeout},
                retryable=True,
            )
        except Exception as e:
            return create_error_response(
                str(e), ErrorType.EXECUTION, {"limit": limit}, retryable=True
            )


class GitAddTool(Tool):
    """Tool for staging changes for commit"""

    default_timeout: int = 10
    timeout_category: str = "git"

    def execute(self, files: Optional[list[str]] = None, add_all: bool = False) -> Dict[str, Any]:
        """Stage changes for the next commit."""
        if not files and not add_all:
            return create_error_response(
                "Either 'files' must be provided or 'add_all' must be True.",
                ErrorType.VALIDATION,
            )

        if self.permission_mode == PermissionMode.PLAN:
            if add_all:
                action_desc = "all changes"
            else:
                action_desc = ", ".join(files)
            if self.console:
                self.console.print(f"[yellow]PLAN MODE:[/yellow] Would stage {action_desc}")
            return create_permission_denial(
                "Plan mode - no staging allowed", "git_add", {"files": files, "add_all": add_all}
            )

        # Build command
        cmd = ["git", "add"]
        if add_all:
            cmd.append("--all")
            action_desc = "all changes"
        else:
            cmd.extend(files)
            action_desc = ", ".join(files)

        # Ask for approval
        if (
            self.permission_mode == PermissionMode.NORMAL
            and self.console
            and self.permission_mode != PermissionMode.AUTO_APPROVE
        ):
            if not Confirm.ask(f"[bold]Stage {action_desc} for commit?[/bold]"):
                if self.console:
                    self.console.print("[red]?[/red] Cancelled by user")
                return create_permission_denial(
                    "Cancelled by user", "git_add", {"files": files, "add_all": add_all}
                )

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )

            if result.returncode != 0:
                return create_error_response(
                    result.stderr or f"Git add failed for {action_desc}",
                    ErrorType.EXECUTION,
                    {"command": cmd, "stderr": result.stderr},
                    retryable=True,
                )

            if self.console:
                self.console.print(
                    Panel(
                        f"Staged {action_desc}",
                        title="? Git Add Successful",
                        border_style="green",
                    )
                )

            return create_success_response({"staged": "all" if add_all else files})
        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git add timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"command": cmd, "timeout": timeout},
                retryable=True,
            )
        except Exception as e:
            return create_error_response(
                str(e), ErrorType.EXECUTION, {"command": cmd}, retryable=True
            )


class GitBranchTool(Tool):
    """Tool for branch management"""

    default_timeout: int = 10
    timeout_category: str = "git"

    def execute(
        self, action: str = "list", branch_name: Optional[str] = None, force: bool = False
    ) -> Dict[str, Any]:
        """List, create, or delete branches."""
        if action == "list":
            return self._list_branches()
        elif action == "create":
            if not branch_name:
                return create_error_response(
                    "branch_name is required for 'create' action.", ErrorType.VALIDATION
                )
            return self._create_branch(branch_name)
        elif action == "delete":
            if not branch_name:
                return create_error_response(
                    "branch_name is required for 'delete' action.", ErrorType.VALIDATION
                )
            return self._delete_branch(branch_name, force)
        else:
            return create_error_response(
                f"Invalid action '{action}'. Must be one of 'list', 'create', 'delete'.",
                ErrorType.VALIDATION,
            )

    def _list_branches(self) -> Dict[str, Any]:
        """List all local and remote branches."""
        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                ["git", "branch", "--all"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )
            if result.returncode != 0:
                return create_error_response(
                    "Failed to list branches.", ErrorType.EXECUTION, {"stderr": result.stderr}
                )

            output = result.stdout
            if self.console:
                self.console.print(Panel(output, title="?? Git Branches", border_style="cyan"))

            branches = [line.strip() for line in output.split("\n") if line.strip()]
            return create_success_response({"branches": branches})

        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION)

    def _create_branch(self, branch_name: str) -> Dict[str, Any]:
        """Create a new branch."""
        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(
                    f"[yellow]PLAN MODE:[/yellow] Would create branch '{branch_name}'"
                )
            return create_permission_denial("Plan mode - no branch creation", "git_branch_create")

        if (
            self.permission_mode == PermissionMode.NORMAL
            and self.console
            and self.permission_mode != PermissionMode.AUTO_APPROVE
        ):
            if not Confirm.ask(f"[bold]Create new branch '{branch_name}'?[/bold]"):
                return create_permission_denial(
                    "User cancelled branch creation.", "git_branch_create"
                )

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                ["git", "branch", branch_name],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )
            if result.returncode != 0:
                return create_error_response(
                    f"Failed to create branch '{branch_name}'.",
                    ErrorType.EXECUTION,
                    {"stderr": result.stderr},
                )

            if self.console:
                self.console.print(
                    Panel(
                        f"Branch '{branch_name}' created.",
                        title="? Branch Created",
                        border_style="green",
                    )
                )
            return create_success_response({"branch_name": branch_name, "action": "create"})

        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION)

    def _delete_branch(self, branch_name: str, force: bool) -> Dict[str, Any]:
        """Delete a branch."""
        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(
                    f"[yellow]PLAN MODE:[/yellow] Would delete branch '{branch_name}'"
                )
            return create_permission_denial("Plan mode - no branch deletion", "git_branch_delete")

        delete_flag = "-D" if force else "-d"
        confirm_msg = (
            f"[bold red]Permanently delete branch '{branch_name}'? This cannot be undone.[/bold red]"  # noqa: E501
            if force
            else f"[bold]Delete branch '{branch_name}'?[/bold]"
        )

        if (
            self.permission_mode == PermissionMode.NORMAL
            and self.console
            and self.permission_mode != PermissionMode.AUTO_APPROVE
        ):
            if not Confirm.ask(confirm_msg):
                return create_permission_denial(
                    "User cancelled branch deletion.", "git_branch_delete"
                )

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                ["git", "branch", delete_flag, branch_name],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )
            if result.returncode != 0:
                return create_error_response(
                    f"Failed to delete branch '{branch_name}'.",
                    ErrorType.EXECUTION,
                    {"stderr": result.stderr},
                )

            if self.console:
                self.console.print(
                    Panel(result.stdout, title="? Branch Deleted", border_style="green")
                )
            return create_success_response({"branch_name": branch_name, "action": "delete"})
        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION)


class GitPushTool(Tool):
    """Tool for pushing changes to a remote repository"""

    default_timeout: int = 60  # Pushing can take longer
    timeout_category: str = "git"

    def execute(self, remote: str = "origin", branch: Optional[str] = None) -> Dict[str, Any]:
        """Push commits to a remote repository."""

        action_desc = f"push to remote '{remote}'"
        if branch:
            action_desc += f" branch '{branch}'"

        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]PLAN MODE:[/yellow] Would {action_desc}")
            return create_permission_denial("Plan mode - no push allowed", "git_push")

        if self.console:
            warning_panel = Panel(
                f"[bold]You are about to push changes to the remote repository '{remote}'.[/bold]\n"
                "This action can affect other collaborators and cannot be easily undone.",
                title="?? [bold red]High-Risk Action[/bold red] ??",
                border_style="red",
                expand=False,
            )
            self.console.print(warning_panel)
            if self.permission_mode == PermissionMode.NORMAL and not Confirm.ask(
                f"[bold]Are you sure you want to {action_desc}?[/bold]"
            ):
                return create_permission_denial("User cancelled push.", "git_push")
        elif self.permission_mode == PermissionMode.NORMAL and self.console:
            if not Confirm.ask(f"[bold]Are you sure you want to {action_desc}?[/bold]"):
                return create_permission_denial("User cancelled push.", "git_push")

        cmd = ["git", "push", remote]
        if branch:
            cmd.append(branch)

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )

            if result.returncode != 0:
                error_message = result.stderr or "Git push failed."
                if "authentication" in error_message.lower():
                    error_message += (
                        "\nHint: Authentication may have failed. Check your credentials."
                    )
                return create_error_response(
                    error_message,
                    ErrorType.EXECUTION,
                    {"command": cmd, "stderr": result.stderr},
                )

            if self.console:
                self.console.print(
                    Panel(
                        result.stderr or result.stdout,
                        title="? Push Successful",
                        border_style="green",
                    )
                )
            return create_success_response({"output": result.stderr or result.stdout})

        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git push timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"command": cmd, "timeout": timeout},
            )
        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION, {"command": cmd})


class GitRemoteTool(Tool):
    """Tool for listing remotes"""

    default_timeout: int = 10
    timeout_category: str = "git"

    def execute(self, verbose: bool = False) -> Dict[str, Any]:
        """List git remotes."""
        cmd = ["git", "remote"]
        if verbose:
            cmd.append("-v")

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )

            if result.returncode != 0:
                return create_error_response(
                    "Failed to list remotes.", ErrorType.EXECUTION, {"stderr": result.stderr}
                )

            output = result.stdout
            if self.console:
                self.console.print(
                    Panel(
                        output or "[dim]No remotes configured.[/dim]",
                        title="?? Git Remotes",
                        border_style="cyan",
                    )
                )
            return create_success_response(
                {"output": output, "remotes": output.strip().split("\n") if output.strip() else []}
            )

        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION)


class GitShowTool(Tool):
    """Tool for showing git object details"""

    default_timeout: int = 10
    timeout_category: str = "git"

    def execute(self, ref: str = "HEAD") -> Dict[str, Any]:
        """Show details of a commit, tag, or other git object."""
        cmd = ["git", "show", ref]

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )

            if result.returncode != 0:
                return create_error_response(
                    f"Failed to show details for '{ref}'.",
                    ErrorType.EXECUTION,
                    {"stderr": result.stderr},
                )

            output = result.stdout
            if self.console:
                self.console.print(Panel(output, title=f"?? Git Show: {ref}", border_style="cyan"))
            return create_success_response({"output": output})

        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION)


class GitCheckoutTool(Tool):
    """Tool for switching branches"""

    default_timeout: int = 10
    timeout_category: str = "git"

    def execute(self, branch: str, new_branch: bool = False) -> Dict[str, Any]:
        """Switch branches or create a new one."""

        action_desc = f"checkout branch '{branch}'"
        cmd = ["git", "checkout", branch]
        if new_branch:
            action_desc = f"create and checkout new branch '{branch}'"
            cmd.insert(2, "-b")

        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]PLAN MODE:[/yellow] Would {action_desc}")
            return create_permission_denial("Plan mode - no checkout allowed", "git_checkout")

        if (
            self.permission_mode == PermissionMode.NORMAL
            and self.console
            and self.permission_mode != PermissionMode.AUTO_APPROVE
        ):
            if not Confirm.ask(f"[bold]Do you want to {action_desc}?[/bold]"):
                return create_permission_denial("User cancelled checkout.", "git_checkout")

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )

            if result.returncode != 0:
                return create_error_response(
                    result.stderr or f"Git checkout failed for branch '{branch}'.",
                    ErrorType.EXECUTION,
                    {"command": cmd, "stderr": result.stderr},
                )

            output = result.stderr or result.stdout
            if self.console:
                self.console.print(
                    Panel(output, title=f"? Git Checkout Successful", border_style="green")
                )

            return create_success_response(
                {"output": output, "branch": branch, "new_branch": new_branch}
            )

        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION, {"command": cmd})


class GitResetTool(Tool):
    """Tool for unstaging files"""

    default_timeout: int = 10
    timeout_category: str = "git"

    def execute(self, files: list[str]) -> Dict[str, Any]:
        """Unstage files from the index."""

        if not files:
            return create_error_response(
                "At least one file must be provided.", ErrorType.VALIDATION
            )

        action_desc = f"unstage {', '.join(files)}"

        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]PLAN MODE:[/yellow] Would {action_desc}")
            return create_permission_denial("Plan mode - no reset allowed", "git_reset")

        if self.permission_mode == PermissionMode.NORMAL and self.console:
            if self.permission_mode != PermissionMode.AUTO_APPROVE and not Confirm.ask(
                f"[bold]Do you want to {action_desc}?[/bold]"
            ):
                return create_permission_denial("User cancelled reset.", "git_reset")

        cmd = ["git", "reset", "--"] + files

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )

            if result.returncode != 0:
                return create_error_response(
                    result.stderr or f"Git reset failed for files: {', '.join(files)}",
                    ErrorType.EXECUTION,
                    {"command": cmd, "stderr": result.stderr},
                )

            output = result.stderr or result.stdout
            if self.console:
                self.console.print(
                    Panel(
                        f"Unstaged {', '.join(files)}",
                        title=f"? Git Reset Successful",
                        border_style="green",
                    )
                )

            return create_success_response({"output": output, "files": files})

        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION, {"command": cmd})


class GitFetchTool(Tool):
    """Tool for fetching from a remote repository"""

    default_timeout: int = 60
    timeout_category: str = "git"

    def execute(self, remote: str = "origin") -> Dict[str, Any]:
        """Fetch changes from a remote repository."""

        action_desc = f"fetch from remote '{remote}'"

        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]PLAN MODE:[/yellow] Would {action_desc}")
            return create_permission_denial("Plan mode - no fetch allowed", "git_fetch")

        if (
            self.permission_mode == PermissionMode.NORMAL
            and self.console
            and self.permission_mode != PermissionMode.AUTO_APPROVE
        ):
            if not Confirm.ask(f"[bold]Do you want to {action_desc}?[/bold]"):
                return create_permission_denial("User cancelled fetch.", "git_fetch")

        cmd = ["git", "fetch", remote]

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )

            if result.returncode != 0:
                error_message = result.stderr or "Git fetch failed."
                return create_error_response(
                    error_message,
                    ErrorType.EXECUTION,
                    {"command": cmd, "stderr": result.stderr},
                )

            output = result.stderr or result.stdout
            if self.console:
                self.console.print(
                    Panel(output, title="? Git Fetch Successful", border_style="green")
                )

            return create_success_response({"output": output})

        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git fetch timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"command": cmd, "timeout": timeout},
            )
        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION, {"command": cmd})


class GitPullTool(Tool):
    """Tool for pulling changes from a remote repository"""

    default_timeout: int = 60
    timeout_category: str = "git"

    def execute(self, remote: str = "origin", branch: Optional[str] = None) -> Dict[str, Any]:
        """Fetch from and integrate with another repository or a local branch."""

        action_desc = f"pull from remote '{remote}'"
        if branch:
            action_desc += f" branch '{branch}'"

        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]PLAN MODE:[/yellow] Would {action_desc}")
            return create_permission_denial("Plan mode - no pull allowed", "git_pull")

        if self.console and self.permission_mode != PermissionMode.AUTO_APPROVE:
            if not Confirm.ask(f"[bold]Are you sure you want to {action_desc}?[/bold]"):
                return create_permission_denial("User cancelled pull.", "git_pull")

        cmd = ["git", "pull", remote]
        if branch:
            cmd.append(branch)

        try:
            timeout = self.get_timeout()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=timeout,
            )

            if result.returncode != 0:
                error_message = result.stderr or "Git pull failed."
                if "authentication" in error_message.lower():
                    error_message += (
                        "\nHint: Authentication may have failed. Check your credentials."
                    )
                return create_error_response(
                    error_message,
                    ErrorType.EXECUTION,
                    {"command": cmd, "stderr": result.stderr},
                )

            output = result.stderr or result.stdout
            if self.console:
                self.console.print(
                    Panel(output, title="? Git Pull Successful", border_style="green")
                )

            return create_success_response({"output": output})

        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Git pull timed out after {timeout} seconds",
                ErrorType.TIMEOUT,
                {"command": cmd, "timeout": timeout},
            )
        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION, {"command": cmd})
