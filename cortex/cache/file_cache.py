"""File content cache with mtime validation and LRU eviction."""

import os
import threading
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from collections import OrderedDict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cached file entry."""

    content: str
    mtime: float
    size: int
    accessed_at: datetime
    hit_count: int = 0


class FileCache:
    """
    LRU file cache with mtime validation.

    Features:
    - Automatic invalidation on file change (mtime check)
    - LRU eviction policy
    - Configurable max entries and total size
    - Thread-safe operations

    Usage:
        cache = FileCache(max_entries=100, max_size_mb=50.0)

        # Get from cache (returns None if not cached or invalid)
        content = cache.get(Path("file.py"))

        # Set cache entry
        cache.set(Path("file.py"), content)

        # Invalidate after modification
        cache.invalidate(Path("file.py"))
    """

    def __init__(self, max_entries: int = 100, max_size_mb: float = 50.0, enabled: bool = True):
        self.max_entries = max_entries
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.enabled = enabled

        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._current_size = 0
        self._lock = threading.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0

    def get(self, path: Path) -> Optional[str]:
        """
        Get file content from cache if valid.

        Validates mtime before returning cached content.
        Returns None if not cached or invalid.

        Args:
            path: Path to the file

        Returns:
            Cached content or None
        """
        if not self.enabled:
            return None

        key = str(path.resolve())

        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Validate mtime
            try:
                current_mtime = path.stat().st_mtime
                if current_mtime != entry.mtime:
                    # File changed, invalidate
                    self._remove_entry(key)
                    self._misses += 1
                    logger.debug(f"Cache invalidated (mtime changed): {path}")
                    return None
            except OSError:
                # File may have been deleted
                self._remove_entry(key)
                self._misses += 1
                return None

            # Update access info (LRU)
            entry.accessed_at = datetime.now()
            entry.hit_count += 1
            self._cache.move_to_end(key)

            self._hits += 1
            logger.debug(f"Cache hit: {path}")
            return entry.content

    def set(self, path: Path, content: str) -> bool:
        """
        Cache file content.

        Args:
            path: Path to the file
            content: File content to cache

        Returns:
            True if cached successfully
        """
        if not self.enabled:
            return False

        key = str(path.resolve())
        content_size = len(content.encode("utf-8"))

        # Don't cache if single file exceeds limit
        if content_size > self.max_size_bytes:
            logger.debug(f"File too large to cache: {path} ({content_size} bytes)")
            return False

        with self._lock:
            # Remove existing entry if present
            if key in self._cache:
                self._remove_entry(key)

            # Evict if needed
            while (
                len(self._cache) >= self.max_entries
                or self._current_size + content_size > self.max_size_bytes
            ):
                if not self._cache:
                    break
                self._evict_lru()

            # Get mtime
            try:
                mtime = path.stat().st_mtime
            except OSError:
                return False

            # Add entry
            entry = CacheEntry(
                content=content, mtime=mtime, size=content_size, accessed_at=datetime.now()
            )

            self._cache[key] = entry
            self._current_size += content_size

            logger.debug(f"Cached: {path} ({content_size} bytes)")
            return True

    def invalidate(self, path: Path) -> bool:
        """
        Invalidate cache entry for a path.

        Call this after modifying a file.

        Args:
            path: Path to invalidate

        Returns:
            True if entry was found and removed
        """
        key = str(path.resolve())

        with self._lock:
            if key in self._cache:
                self._remove_entry(key)
                logger.debug(f"Cache invalidated: {path}")
                return True
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._current_size = 0
            logger.debug("Cache cleared")

    def _remove_entry(self, key: str) -> None:
        """Remove entry (must hold lock)."""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._current_size -= entry.size

    def _evict_lru(self) -> None:
        """Evict least recently used entry (must hold lock)."""
        if self._cache:
            key, entry = self._cache.popitem(last=False)
            self._current_size -= entry.size
            logger.debug(f"Evicted from cache: {key}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

            return {
                "enabled": self.enabled,
                "entries": len(self._cache),
                "max_entries": self.max_entries,
                "size_bytes": self._current_size,
                "size_mb": self._current_size / (1024 * 1024),
                "max_size_mb": self.max_size_bytes / (1024 * 1024),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
            }

    def __len__(self) -> int:
        """Return number of cached entries."""
        with self._lock:
            return len(self._cache)

    def __contains__(self, path: Path) -> bool:
        """Check if path is in cache (without validating mtime)."""
        key = str(path.resolve())
        with self._lock:
            return key in self._cache


# Global cache instance
_file_cache: Optional[FileCache] = None
_cache_lock = threading.Lock()


def get_file_cache(config: Optional[Dict[str, Any]] = None) -> FileCache:
    """
    Get or create global file cache.

    Args:
        config: Optional configuration dict with keys:
            - enabled: bool (default True)
            - max_entries: int (default 100)
            - max_size_mb: float (default 50.0)

    Returns:
        FileCache instance
    """
    global _file_cache

    with _cache_lock:
        if _file_cache is None:
            config = config or {}
            _file_cache = FileCache(
                max_entries=config.get("max_entries", 100),
                max_size_mb=config.get("max_size_mb", 50.0),
                enabled=config.get("enabled", True),
            )
        return _file_cache


def invalidate_file(path: Path) -> bool:
    """
    Invalidate file in global cache.

    Convenience function for use after file modifications.

    Args:
        path: Path to invalidate

    Returns:
        True if entry was found and removed
    """
    global _file_cache
    if _file_cache is not None:
        return _file_cache.invalidate(path)
    return False


def clear_cache() -> None:
    """Clear global file cache."""
    global _file_cache
    if _file_cache is not None:
        _file_cache.clear()


def reset_cache() -> None:
    """Reset the global cache instance (for testing)."""
    global _file_cache
    with _cache_lock:
        _file_cache = None
