"""Command history management"""

from pathlib import Path
from prompt_toolkit.history import FileHistory


def get_history_file(base_dir: Path) -> Path:
    """Get the history file path"""
    history_dir = base_dir / ".cortex"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir / "history.txt"

