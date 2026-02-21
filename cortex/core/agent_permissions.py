"""Permission management module - handles permission checks and user approvals"""

import logging
from typing import Dict, Any, Set, TYPE_CHECKING
from rich.prompt import Confirm
from rich.panel import Panel
import json
import hashlib

from ..models import PermissionMode
from ..ui.console import console

if TYPE_CHECKING:
    from ..agent import Cortex

logger = logging.getLogger(__name__)


class PermissionManager:
    """
    Manages permission checks and user approvals.

    Responsibilities:
    - Check if operations are permitted based on permission mode
    - Handle user approval dialogs for dangerous operations
    - Detect and block destructive operations in PLAN mode
    - Cache user approvals to avoid repeated prompts
    """

    # Dangerous operations that require extra caution
    DANGEROUS_COMMANDS = [
        "rm -rf",
        "sudo rm",
        "format",
        "del /f /q",
        "DROP TABLE",
        "DROP DATABASE",
        "git reset --hard",
        "git push --force",
        "npm publish",
    ]

    # Destructive tools blocked in PLAN mode
    DESTRUCTIVE_TOOLS = {
        "write_file",
        "edit_file",
        "execute_command",
        "git_commit",
        "git_push",
    }

    def __init__(self, agent: "Cortex"):
        """
        Initialize with reference to parent agent.

        Args:
            agent: Parent Cortex agent instance
        """
        self.agent = agent
        self.approved_operations: Set[str] = set()  # Cache of approved operations

    def check(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """
        Check if tool execution is permitted.

        Args:
            tool_name: Name of tool to execute
            args: Tool arguments

        Returns:
            True if permitted, False otherwise
        """
        # AUTO_APPROVE mode - always allow
        if self.agent.permission_mode == PermissionMode.AUTO_APPROVE:
            return True

        # PLAN mode - block destructive operations
        if self.agent.permission_mode == PermissionMode.PLAN:
            if tool_name in self.DESTRUCTIVE_TOOLS:
                console.print(
                    Panel(
                        f"[yellow]⚠️  Operation blocked in PLAN mode[/yellow]\n\n"
                        f"Tool: [cyan]{tool_name}[/cyan]\n"
                        f"PLAN mode is read-only. Use /mode normal to execute changes.",
                        title="Permission Denied",
                        border_style="yellow",
                    )
                )
                return False
            return True

        # NORMAL mode - ask user for dangerous operations
        if self._is_dangerous(tool_name, args):
            return self._ask_user_approval(tool_name, args)

        return True

    def _is_dangerous(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """
        Detect if operation is dangerous and needs approval.

        Args:
            tool_name: Tool name
            args: Tool arguments

        Returns:
            True if dangerous, False otherwise
        """
        # Tool-specific danger checks
        if tool_name == "execute_command":
            return self._is_dangerous_command(args)
        elif tool_name == "write_file":
            return self._is_dangerous_write(args)
        elif tool_name in ["git_push", "git_force_push"]:
            return True  # Git push always requires approval

        return False

    def _is_dangerous_command(self, args: Dict[str, Any]) -> bool:
        """Check if command is dangerous"""
        command = args.get("command", "")
        return any(pattern in command for pattern in self.DANGEROUS_COMMANDS)

    def _is_dangerous_write(self, args: Dict[str, Any]) -> bool:
        """Check if file write is dangerous"""
        path = args.get("path", "")

        # System files
        dangerous_paths = [
            "/etc/",
            "/bin/",
            "/usr/bin/",
            "C:\\Windows\\",
            "C:\\System32\\",
        ]

        return any(dangerous in path for dangerous in dangerous_paths)

    def _ask_user_approval(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """
        Prompt user for approval of dangerous operation.

        Args:
            tool_name: Tool name
            args: Tool arguments

        Returns:
            True if approved, False otherwise
        """
        # Check cache to avoid repeated prompts for same operation
        operation_hash = self._hash_operation(tool_name, args)
        if operation_hash in self.approved_operations:
            return True

        # Show details to user
        console.print(
            Panel(
                f"[yellow]⚠️  Dangerous operation detected[/yellow]\n\n"
                f"Tool: [cyan]{tool_name}[/cyan]\n"
                f"Arguments:\n[dim]{json.dumps(args, indent=2)}[/dim]",
                title="Permission Required",
                border_style="yellow",
            )
        )

        # Ask for approval
        approved = Confirm.ask("[cyan]Allow this operation?[/cyan]", default=False)

        # Cache approval if granted
        if approved:
            self.approved_operations.add(operation_hash)
            logger.info(f"User approved: {tool_name} with args {args}")
        else:
            logger.info(f"User denied: {tool_name} with args {args}")

        return approved

    def _hash_operation(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        Create hash of operation for caching approvals.

        Args:
            tool_name: Tool name
            args: Tool arguments

        Returns:
            Hash string
        """
        # Create stable string representation
        arg_str = json.dumps(args, sort_keys=True)
        operation_str = f"{tool_name}:{arg_str}"

        # Hash it
        return hashlib.sha256(operation_str.encode()).hexdigest()

    def clear_approvals(self):
        """Clear all cached approvals"""
        self.approved_operations.clear()
        logger.info("Cleared all cached permissions")

    def get_approval_count(self) -> int:
        """Get number of cached approvals"""
        return len(self.approved_operations)
