"""Tests for file caching functionality."""

import pytest
import tempfile
import time
from pathlib import Path

from cortex.cache import (
    FileCache,
    CacheEntry,
    get_file_cache,
    invalidate_file,
    clear_cache,
    reset_cache,
)


@pytest.fixture(autouse=True)
def reset_global_cache():
    """Reset global cache before each test."""
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello, World!")
        f.flush()
        yield Path(f.name)
    # Cleanup
    try:
        Path(f.name).unlink()
    except OSError:
        pass


@pytest.fixture
def cache():
    """Create a test cache instance."""
    return FileCache(max_entries=10, max_size_mb=1.0, enabled=True)


class TestFileCache:
    """Tests for FileCache class."""

    def test_cache_set_and_get(self, cache, temp_file):
        """Test basic cache set and get operations."""
        content = "Test content"
        temp_file.write_text(content)

        # Set cache
        assert cache.set(temp_file, content) is True

        # Get from cache
        cached = cache.get(temp_file)
        assert cached == content

    def test_cache_miss_for_uncached_file(self, cache, temp_file):
        """Test cache miss for file not in cache."""
        result = cache.get(temp_file)
        assert result is None

    def test_cache_invalidation_on_file_change(self, cache, temp_file):
        """Test that cache invalidates when file mtime changes."""
        content = "Original content"
        temp_file.write_text(content)
        cache.set(temp_file, content)

        # Verify cached
        assert cache.get(temp_file) == content

        # Modify file (need small delay to ensure mtime changes)
        time.sleep(0.1)
        new_content = "Modified content"
        temp_file.write_text(new_content)

        # Cache should return None (mtime mismatch)
        assert cache.get(temp_file) is None

    def test_cache_explicit_invalidation(self, cache, temp_file):
        """Test explicit cache invalidation."""
        content = "Test content"
        temp_file.write_text(content)
        cache.set(temp_file, content)

        # Verify cached
        assert cache.get(temp_file) == content

        # Invalidate
        assert cache.invalidate(temp_file) is True

        # Should be gone
        assert cache.get(temp_file) is None

    def test_cache_invalidation_nonexistent(self, cache, temp_file):
        """Test invalidation of file not in cache."""
        result = cache.invalidate(temp_file)
        assert result is False

    def test_cache_clear(self, cache, temp_file):
        """Test cache clear operation."""
        content = "Test content"
        temp_file.write_text(content)
        cache.set(temp_file, content)

        assert len(cache) == 1

        cache.clear()

        assert len(cache) == 0
        assert cache.get(temp_file) is None

    def test_lru_eviction(self):
        """Test LRU eviction when max entries reached."""
        cache = FileCache(max_entries=3, max_size_mb=10.0)

        files = []
        for i in range(5):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                content = f"Content {i}"
                f.write(content)
                files.append((Path(f.name), content))

        try:
            # Add 5 files to cache with max_entries=3
            for path, content in files:
                cache.set(path, content)

            # Only last 3 should be in cache
            assert len(cache) == 3

            # First 2 should be evicted
            assert cache.get(files[0][0]) is None
            assert cache.get(files[1][0]) is None

            # Last 3 should be present
            assert cache.get(files[2][0]) == files[2][1]
            assert cache.get(files[3][0]) == files[3][1]
            assert cache.get(files[4][0]) == files[4][1]
        finally:
            for path, _ in files:
                try:
                    path.unlink()
                except OSError:
                    pass

    def test_size_limit_eviction(self):
        """Test eviction when size limit reached."""
        # Cache with 1KB limit
        cache = FileCache(max_entries=100, max_size_mb=0.001)  # ~1KB

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            # Content larger than cache limit
            large_content = "x" * 2000  # 2KB
            f.write(large_content)
            path = Path(f.name)

        try:
            # Should fail to cache (too large for single entry)
            result = cache.set(path, large_content)
            assert result is False
            assert len(cache) == 0
        finally:
            path.unlink()

    def test_cache_disabled(self, temp_file):
        """Test cache when disabled."""
        cache = FileCache(enabled=False)
        content = "Test content"
        temp_file.write_text(content)

        # Set should return False when disabled
        assert cache.set(temp_file, content) is False

        # Get should return None when disabled
        assert cache.get(temp_file) is None

    def test_cache_stats(self, cache, temp_file):
        """Test cache statistics."""
        content = "Test content"
        temp_file.write_text(content)

        # Initial stats
        stats = cache.get_stats()
        assert stats["entries"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

        # Miss
        cache.get(temp_file)
        stats = cache.get_stats()
        assert stats["misses"] == 1

        # Set
        cache.set(temp_file, content)
        stats = cache.get_stats()
        assert stats["entries"] == 1

        # Hit
        cache.get(temp_file)
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["hit_rate"] == 0.5  # 1 hit, 1 miss

    def test_cache_contains(self, cache, temp_file):
        """Test __contains__ method."""
        content = "Test content"
        temp_file.write_text(content)

        assert temp_file not in cache

        cache.set(temp_file, content)

        assert temp_file in cache

    def test_cache_len(self, cache, temp_file):
        """Test __len__ method."""
        assert len(cache) == 0

        content = "Test content"
        temp_file.write_text(content)
        cache.set(temp_file, content)

        assert len(cache) == 1


class TestGlobalCache:
    """Tests for global cache functions."""

    def test_get_file_cache_singleton(self):
        """Test that get_file_cache returns singleton."""
        cache1 = get_file_cache()
        cache2 = get_file_cache()
        assert cache1 is cache2

    def test_get_file_cache_with_config(self):
        """Test get_file_cache with custom config."""
        config = {"enabled": True, "max_entries": 50, "max_size_mb": 25.0}
        cache = get_file_cache(config)
        stats = cache.get_stats()
        assert stats["max_entries"] == 50
        assert stats["max_size_mb"] == 25.0

    def test_invalidate_file_global(self, temp_file):
        """Test global invalidate_file function."""
        content = "Test content"
        temp_file.write_text(content)

        cache = get_file_cache()
        cache.set(temp_file, content)

        assert cache.get(temp_file) == content

        # Use global function
        result = invalidate_file(temp_file)
        assert result is True
        assert cache.get(temp_file) is None

    def test_clear_cache_global(self, temp_file):
        """Test global clear_cache function."""
        content = "Test content"
        temp_file.write_text(content)

        cache = get_file_cache()
        cache.set(temp_file, content)

        assert len(cache) == 1

        # Use global function
        clear_cache()
        assert len(cache) == 0


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        """Test CacheEntry creation."""
        from datetime import datetime

        entry = CacheEntry(
            content="test", mtime=1234567890.0, size=4, accessed_at=datetime.now(), hit_count=0
        )
        assert entry.content == "test"
        assert entry.mtime == 1234567890.0
        assert entry.size == 4
        assert entry.hit_count == 0


class TestCacheThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_access(self, temp_file):
        """Test concurrent cache access."""
        import threading
        import random

        cache = FileCache(max_entries=100, max_size_mb=10.0)
        content = "Test content"
        temp_file.write_text(content)

        errors = []

        def worker():
            try:
                for _ in range(100):
                    op = random.choice(["get", "set", "invalidate"])
                    if op == "get":
                        cache.get(temp_file)
                    elif op == "set":
                        cache.set(temp_file, content)
                    else:
                        cache.invalidate(temp_file)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
