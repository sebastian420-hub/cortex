"""
AST Cache - LRU cache for parsed ASTs with file change detection.

Provides efficient caching of parsed ASTs to avoid re-parsing
unchanged files.
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional, Any, Dict, Tuple, List
from collections import OrderedDict

logger = logging.getLogger(__name__)


class ASTCache:
    """
    LRU cache for ASTs with file change detection.

    Features:
    - LRU eviction policy
    - File content hash validation
    - Cache statistics
    - Thread-safe operations
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize AST cache.

        Args:
            max_size: Maximum number of ASTs to cache
        """
        self.max_size = max_size
        self.cache: OrderedDict[Tuple[Path, str], Dict[str, Any]] = OrderedDict()
        self.hits = 0
        self.misses = 0

        logger.info(f"AST Cache initialized with max_size={max_size}")

    def _get_key(self, file_path: Path, language: str) -> Tuple[Path, str]:
        """Create cache key from file path and language."""
        return (file_path.resolve(), language)

    def _get_file_hash(self, file_path: Path) -> str:
        """
        Get hash of file contents.

        Args:
            file_path: Path to the file

        Returns:
            MD5 hash of file contents or empty string if file doesn't exist
        """
        try:
            if not file_path.exists():
                return ""

            content = file_path.read_bytes()
            return hashlib.md5(content).hexdigest()

        except Exception as e:
            logger.warning(f"Failed to hash file {file_path}: {e}")
            return ""

    def get(self, file_path: Path, language: str) -> Optional[Any]:
        """
        Get AST from cache if available and file hasn't changed.

        Args:
            file_path: Path to the file
            language: Programming language

        Returns:
            Cached AST or None if not in cache or file changed
        """
        key = self._get_key(file_path, language)

        if key not in self.cache:
            self.misses += 1
            return None

        # Get cached entry
        entry = self.cache[key]

        # Check if file has changed
        current_hash = self._get_file_hash(file_path)
        if current_hash != entry["hash"]:
            # File changed, remove from cache
            del self.cache[key]
            self.misses += 1
            logger.debug(f"File changed, removed from cache: {file_path}")
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self.hits += 1

        logger.debug(f"Cache hit for {file_path}")
        return entry["ast"]

    def put(self, file_path: Path, language: str, ast: Any) -> None:
        """
        Put AST in cache.

        Args:
            file_path: Path to the file
            language: Programming language
            ast: Parsed AST
        """
        key = self._get_key(file_path, language)

        # Get current file hash
        file_hash = self._get_file_hash(file_path)
        if not file_hash:
            logger.warning(f"Cannot cache {file_path}: cannot read file")
            return

        # Create cache entry
        entry = {
            "ast": ast,
            "hash": file_hash,
            "language": language,
            "timestamp": Path(file_path).stat().st_mtime if file_path.exists() else 0,
        }

        # Add to cache
        self.cache[key] = entry
        self.cache.move_to_end(key)

        # Evict if cache is full
        if len(self.cache) > self.max_size:
            self._evict()

        logger.debug(f"Cached AST for {file_path}")

    def _evict(self) -> None:
        """Evict least recently used entry from cache."""
        if self.cache:
            key, entry = self.cache.popitem(last=False)
            logger.debug(f"Evicted from cache: {key[0]}")

    def remove(self, file_path: Path, language: Optional[str] = None) -> None:
        """
        Remove entry from cache.

        Args:
            file_path: Path to the file
            language: Programming language (remove all if None)
        """
        if language is None:
            # Remove all entries for this file
            keys_to_remove = [k for k in self.cache.keys() if k[0] == file_path.resolve()]
            for key in keys_to_remove:
                del self.cache[key]
                logger.debug(f"Removed from cache: {file_path}")
        else:
            # Remove specific entry
            key = self._get_key(file_path, language)
            if key in self.cache:
                del self.cache[key]
                logger.debug(f"Removed from cache: {file_path} ({language})")

    def clear(self) -> None:
        """Clear all entries from cache."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        logger.info("AST cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "total": total,
            "hit_rate": hit_rate,
            "full": len(self.cache) >= self.max_size,
        }

    def contains(self, file_path: Path, language: str) -> bool:
        """
        Check if cache contains entry for file.

        Args:
            file_path: Path to the file
            language: Programming language

        Returns:
            True if entry exists and file hasn't changed
        """
        key = self._get_key(file_path, language)

        if key not in self.cache:
            return False

        # Check if file has changed
        entry = self.cache[key]
        current_hash = self._get_file_hash(file_path)

        return current_hash == entry["hash"]

    def get_cached_files(self) -> List[Tuple[Path, str]]:
        """
        Get list of cached files.

        Returns:
            List of (file_path, language) tuples
        """
        return list(self.cache.keys())

    def __len__(self) -> int:
        """Get number of cached entries."""
        return len(self.cache)

    def __contains__(self, key: Tuple[Path, str]) -> bool:
        """Check if key is in cache."""
        return key in self.cache
