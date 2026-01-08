"""UI components for LocalAgent"""

from .console import console
from .display import show_file_diff, show_file_preview, warn_large_file
from .repl import REPL

__all__ = [
    "console",
    "show_file_diff",
    "show_file_preview",
    "warn_large_file",
    "REPL"
]

