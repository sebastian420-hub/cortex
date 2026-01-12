"""Interactive help system for Cortex."""

from .content import (
    HelpEntry,
    HelpCategory,
    HELP_ENTRIES,
    get_help_entries_by_category,
    get_beginner_entries,
    get_entry_by_command,
)
from .search import (
    SearchResult,
    search_entries,
    search_by_keyword,
    suggest_commands,
    get_related_entries,
)
from .system import HelpSystem

__all__ = [
    # Content
    "HelpEntry",
    "HelpCategory",
    "HELP_ENTRIES",
    "get_help_entries_by_category",
    "get_beginner_entries",
    "get_entry_by_command",
    # Search
    "SearchResult",
    "search_entries",
    "search_by_keyword",
    "suggest_commands",
    "get_related_entries",
    # System
    "HelpSystem",
]
