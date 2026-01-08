"""Base class for tools"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path
from ..models import PermissionMode


class Tool(ABC):
    """Base class for all tools"""
    
    def __init__(
        self,
        project_dir: Path,
        permission_mode: str = PermissionMode.NORMAL,
        console=None
    ):
        self.project_dir = project_dir
        self.permission_mode = permission_mode
        self.console = console
    
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

