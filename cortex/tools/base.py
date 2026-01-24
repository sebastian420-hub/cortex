"""Base class for tools"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path
from ..models import PermissionMode
from ..ui.consolidated_display import create_consolidated_console

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
        **kwargs,
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

    def estimate_content_tokens(self, content: str, model: Optional[str] = None) -> int:
        """
        Estimate tokens in content using the agent's model.

        Args:
            content: The text content to estimate tokens for
            model: Optional model name (if None, uses default)

        Returns:
            Estimated token count
        """
        from ..core.context import estimate_tokens

        if model is None and hasattr(self, 'agent'):
            model = getattr(self.agent, 'model', 'gpt-4')
        return estimate_tokens(content, model or 'gpt-4')

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
    
    def _create_error(self, message: str, error_type: str, **context) -> Dict[str, Any]:
        """
        Create standardized error response.
        
        This helper method ensures consistent error formatting across all tools.
        
        Args:
            message: Human-readable error message
            error_type: Type of error (e.g., "validation", "security", "execution")
            **context: Additional context about the error
        
        Returns:
            Standardized error response dictionary
        """
        from ..utils.errors import create_error_response
        
        # Add tool-specific context
        tool_context = {
            "tool_name": self.__class__.__name__,
            "permission_mode": self.permission_mode,
            **context
        }
        
        return create_error_response(message, error_type, tool_context)
    
    def _create_permission_denial(self, reason: str, action: str, **context) -> Dict[str, Any]:
        """
        Create standardized permission denial response.
        
        Args:
            reason: Why permission was denied
            action: What action was attempted
            **context: Additional context
        
        Returns:
            Standardized permission denial response
        """
        from ..utils.errors import create_permission_denial
        
        denial_context = {
            "tool_name": self.__class__.__name__,
            "permission_mode": self.permission_mode,
            **context
        }
        
        return create_permission_denial(reason, action, denial_context)
    
    def _create_success(self, **data) -> Dict[str, Any]:
        """
        Create standardized success response.
        
        Args:
            **data: Additional data to include in success response
        
        Returns:
            Standardized success response dictionary
        """
        from ..utils.errors import create_success_response
        
        return create_success_response(data)
    
    def _validate_arguments(self, required_args: list, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Validate required arguments for tool execution.
        
        Args:
            required_args: List of required argument names
            **kwargs: Arguments to validate
        
        Returns:
            Error dict if validation fails, None if validation passes
        """
        missing = [arg for arg in required_args if arg not in kwargs]
        if missing:
            return self._create_error(
                f"Missing required arguments: {', '.join(missing)}",
                "validation",
                missing_arguments=missing,
                provided_arguments=list(kwargs.keys())
            )
        return None
