"""Cortex - A unified agent for coding, cybersecurity, and personal assistance"""



def _resolve_version() -> str:
    """The version lives in pyproject.toml only; read it from installed metadata."""
    try:
        from importlib.metadata import version

        return version("cortex")
    except Exception:
        pass
    # Source checkout that is not installed: read pyproject.toml next to the package.
    try:
        import re
        from pathlib import Path

        text = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "0.0.0+unknown"


__version__ = _resolve_version()

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
