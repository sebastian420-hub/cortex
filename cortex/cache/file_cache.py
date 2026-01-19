"""File content cache with mtime validation and LRU eviction."""

import os
import threading
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from collections import OrderedDict
from datetime import datetime
import subprocess

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

    def pre_cache(
        self,
        patterns: Optional[List[str]] = None,
        source: str = "git_history",
        max_files: int = 50,
        directory: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Pre-cache files based on patterns or git history.

        Args:
            patterns: List of glob patterns to match files (e.g., ["*.py", "*.md"])
            source: Source for file selection:
                - "git_history": Use git history (most recent commits)
                - "git_tracked": All git-tracked files matching patterns
                - "directory": All files in directory matching patterns
            max_files: Maximum number of files to pre-cache
            directory: Directory to search (defaults to current directory)

        Returns:
            Dictionary with cache statistics:
            - "cached": number of files successfully cached
            - "skipped": number of files skipped
            - "errors": number of errors encountered
            - "files": list of files that were cached
        """
        if not self.enabled:
            return {"cached": 0, "skipped": 0, "errors": 1, "files": []}

        if directory is None:
            directory = Path.cwd()

        stats = {"cached": 0, "skipped": 0, "errors": 0, "files": []}

        try:
            if source == "git_history":
                files = self._get_files_from_git_history(directory, max_files, patterns)
            elif source == "git_tracked":
                files = self._get_git_tracked_files(directory, max_files, patterns)
            elif source == "directory":
                files = self._get_files_from_directory(directory, max_files, patterns)
            else:
                logger.warning(f"Unknown source: {source}")
                return {"cached": 0, "skipped": 0, "errors": 1, "files": []}

            logger.info(f"Pre-caching {len(files)} files from {source}")

            for filepath in files:
                try:
                    # Check if file exists and is readable
                    if not filepath.exists():
                        stats["skipped"] += 1
                        continue

                    # Check file size (don't cache huge files)
                    file_size = filepath.stat().st_size
                    if file_size > self.max_size_bytes:
                        logger.debug(f"Skipping large file: {filepath} ({file_size} bytes)")
                        stats["skipped"] += 1
                        continue

                    # Read and cache
                    content = filepath.read_text(encoding="utf-8")
                    if self.set(filepath, content):
                        stats["cached"] += 1
                        stats["files"].append(str(filepath))
                        logger.debug(f"Pre-cached: {filepath}")
                    else:
                        stats["skipped"] += 1

                except (OSError, UnicodeDecodeError) as e:
                    logger.debug(f"Error reading {filepath}: {e}")
                    stats["errors"] += 1

        except Exception as e:
            logger.error(f"Error during pre-caching: {e}")
            stats["errors"] += 1

        logger.info(
            f"Pre-caching complete: {stats['cached']} cached, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )

        return stats

    def _get_files_from_git_history(
        self, directory: Path, max_files: int, patterns: Optional[List[str]]
    ) -> List[Path]:
        """Get recently modified files from git history."""
        try:
            # Get recently modified files from git
            cmd = [
                "git",
                "log",
                "--name-only",
                "--pretty=format:",
                "--since=1.month",
                directory,
            ]
            result = subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10,
            )

            files = []
            seen = set()

            for line in result.stdout.splitlines():
                line = line.strip()
                if line and line not in seen:
                    filepath = directory / line
                    if filepath.exists() and patterns_match(filepath, patterns):
                        files.append(filepath)
                        seen.add(line)

                    if len(files) >= max_files:
                        break

            return files

        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            logger.debug(f"Git history failed: {e}")
            return []

    def _get_git_tracked_files(
        self, directory: Path, max_files: int, patterns: Optional[List[str]]
    ) -> List[Path]:
        """Get all git-tracked files."""
        try:
            cmd = ["git", "ls-files"]
            result = subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10,
            )

            files = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    filepath = directory / line
                    if filepath.exists() and patterns_match(filepath, patterns):
                        files.append(filepath)

                    if len(files) >= max_files:
                        break

            return files

        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            logger.debug(f"Git ls-files failed: {e}")
            return []

    def _get_files_from_directory(
        self, directory: Path, max_files: int, patterns: Optional[List[str]]
    ) -> List[Path]:
        """Get files from directory matching patterns."""
        files = []

        if patterns:
            for pattern in patterns:
                for filepath in directory.rglob(pattern):
                    if filepath.exists() and filepath.is_file():
                        files.append(filepath)
                        if len(files) >= max_files:
                            return files
        else:
            # Get all files (non-recursive)
            for filepath in directory.iterdir():
                if filepath.is_file():
                    files.append(filepath)
                    if len(files) >= max_files:
                        return files

        return files


def patterns_match(filepath: Path, patterns: Optional[List[str]]) -> bool:
    """
    Check if filepath matches any of the patterns.

    Args:
        filepath: Path to check
        patterns: List of glob patterns (e.g., ["*.py", "*.md"])

    Returns:
        True if matches any pattern or no patterns specified
    """
    if patterns is None or len(patterns) == 0:
        return True

    filename = filepath.name
    for pattern in patterns:
        # Simple glob matching
        if filepath.match(pattern) or filename.endswith(pattern.lstrip("*")):
            return True

        # Check if pattern matches with wildcard
        if "*" in pattern:
            import fnmatch
            if fnmatch.fnmatch(filename, pattern):
                return True

    return False


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
            - use_redis: bool (default False) - Use Redis backend
            - redis_host: str (default "localhost") - Redis host
            - redis_port: int (default 6379) - Redis port
            - redis_db: int (default 0) - Redis database
            - redis_password: str (optional) - Redis password
            - redis_ttl: int (default 3600) - Redis TTL in seconds
            - redis_fallback: bool (default True) - Fall back to local on Redis failure

    Returns:
        FileCache or RedisFileCache instance
    """
    global _file_cache

    with _cache_lock:
        if _file_cache is None:
            config = config or {}

            # Check if Redis backend is requested
            if config.get("use_redis", False):
                try:
                    from .redis_backend import RedisFileCache

                    _file_cache = RedisFileCache(
                        host=config.get("redis_host", "localhost"),
                        port=config.get("redis_port", 6379),
                        db=config.get("redis_db", 0),
                        password=config.get("redis_password"),
                        ttl=config.get("redis_ttl", 3600),
                        max_entries=config.get("max_entries", 100),
                        max_size_mb=config.get("max_size_mb", 50.0),
                        enabled=config.get("enabled", True),
                        fallback_to_local=config.get("redis_fallback", True),
                    )
                    logger.info("Using Redis cache backend")

                except Exception as e:
                    logger.warning(f"Failed to create Redis cache: {e}")
                    logger.warning("Falling back to local file cache")

                    # Fall back to local cache
                    _file_cache = FileCache(
                        max_entries=config.get("max_entries", 100),
                        max_size_mb=config.get("max_size_mb", 50.0),
                        enabled=config.get("enabled", True),
                    )
            else:
                # Use local file cache
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
