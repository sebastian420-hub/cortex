"""Cortex - A unified agent for coding, cybersecurity, and personal assistance"""

__version__ = "1.0.0"

from .agent import Cortex
from .models import PermissionMode
from .config import AgentConfig

__all__ = [
    "Cortex",
    "PermissionMode",
    "AgentConfig",
    "__version__"
]

