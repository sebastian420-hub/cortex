"""LocalAgent - A Claude Code-like terminal agent using local models"""

__version__ = "1.0.0"

from .agent import LocalAgent
from .models import PermissionMode
from .config import AgentConfig

__all__ = [
    "LocalAgent",
    "PermissionMode",
    "AgentConfig",
    "__version__"
]

