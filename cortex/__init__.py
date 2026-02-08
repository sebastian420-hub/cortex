"""Cortex - A unified agent for coding, cybersecurity, and personal assistance"""

__version__ = "1.0.0"

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv

    load_dotenv()  # Load from .env in current directory
except ImportError:
    # python-dotenv not installed, continue without .env support
    pass

from .agent import Cortex
from .models import PermissionMode
from .config import AgentConfig

__all__ = ["Cortex", "PermissionMode", "AgentConfig", "__version__"]
