"""File caching module for Cortex.

Provides LRU caching with mtime validation for file reads.
"""

from .file_cache import (
    FileCache,
    CacheEntry,
    get_file_cache,
    invalidate_file,
    clear_cache,
    reset_cache,
)

__all__ = [
    "FileCache",
    "CacheEntry",
    "get_file_cache",
    "invalidate_file",
    "clear_cache",
    "reset_cache",
]
