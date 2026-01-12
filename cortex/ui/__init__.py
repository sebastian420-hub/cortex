"""UI components for Cortex"""

from .console import console
from .display import (
    show_file_diff,
    show_file_preview,
    warn_large_file,
    display_thinking,
    display_progress_summary,
    display_operation_complete,
)
from .repl import REPL
from .progress import (
    OperationTracker,
    ProgressUpdater,
    SpinnerUpdater,
    track_files,
    track_search,
    show_operation_summary,
    get_tracker,
)

__all__ = [
    "console",
    # Display helpers
    "show_file_diff",
    "show_file_preview",
    "warn_large_file",
    "display_thinking",
    "display_progress_summary",
    "display_operation_complete",
    # REPL
    "REPL",
    # Progress tracking
    "OperationTracker",
    "ProgressUpdater",
    "SpinnerUpdater",
    "track_files",
    "track_search",
    "show_operation_summary",
    "get_tracker",
]
