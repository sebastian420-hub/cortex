"""Base class for tools"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path
from ..models import PermissionMode

if TYPE_CHECKING:
    from ..utils.timeouts import TimeoutConfig
    from ..core.transaction import TransactionManager


class Tool(ABC):
    """Base class for all tools"""

    # Default timeout for this tool (can be overridden by subclasses)
    default_timeout: int = 30
    # Tool category for timeout lookup (e.g., "git", "test", "search")
    timeout_category: str = "default"

    def __init__(
        self,
        project_dir: Path,
        permission_mode: str = PermissionMode.NORMAL,
        console=None,
        timeout_config: Optional["TimeoutConfig"] = None,
        transaction_manager: Optional["TransactionManager"] = None,
    ):
        self.project_dir = project_dir
        self.permission_mode = permission_mode
        self.console = console
        self._timeout_config = timeout_config
        self._transaction_manager = transaction_manager

    def get_timeout(self, operation: Optional[str] = None) -> int:
        """
        Get timeout for this tool's operations.

        Priority:
        1. TimeoutConfig if available (uses tool name lookup)
        2. Class default_timeout attribute

        Args:
            operation: Optional operation name for fine-grained control

        Returns:
            Timeout value in seconds
        """
        if self._timeout_config is not None:
            # Convert class name to tool_name format (e.g., ExecuteCommandTool -> execute_command)
            class_name = self.__class__.__name__
            tool_name = class_name.replace("Tool", "")
            # Convert CamelCase to snake_case
            import re

            tool_name = re.sub(r"(?<!^)(?=[A-Z])", "_", tool_name).lower()
            return self._timeout_config.get_timeout(tool_name, operation)
        return self.default_timeout

    @abstractmethod
    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute the tool with given arguments"""
        pass

    def check_permission(self, action: str) -> bool:
        """
        Check if action is allowed based on permission mode.

        Args:
            action: Description of the action

        Returns:
            True if action is allowed
        """
        if self.permission_mode == PermissionMode.PLAN:
            return False
        if self.permission_mode == PermissionMode.AUTO_APPROVE:
            return True
        # NORMAL mode - ask user (handled by caller)
        return True

    def backup_file(self, path: Path, operation: str) -> bool:
        """
        Backup a file before modification.

        Args:
            path: Path to the file to backup
            operation: Type of operation ('write', 'edit', 'delete')

        Returns:
            True if backup was successful or not available

        Note:
            If transaction manager is not available, logs a warning and returns True
            to allow operations to proceed. In production, transaction manager should
            always be initialized to ensure recoverability.
        """
        if self._transaction_manager is None:
            # Transaction manager not available - log warning but don't block
            # This can happen in tests or if initialization is incomplete
            import logging

            logging.warning(
                f"Transaction manager not available for {operation} on {path}. "
                f"File modifications will not be backed up for recovery."
            )
            return False

        try:
            self._transaction_manager.backup_file(path, operation)
            return True
        except Exception as e:
            # Log the backup failure but don't block the operation
            import logging

            logging.warning(f"Backup failed for {path}: {e}")
            return False
