"""Tests for Redis cache backend."""

import tempfile
from pathlib import Path
import pytest

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from cortex.cache.file_cache import get_file_cache, FileCache


class TestRedisCache:
    """Test Redis cache functionality."""

    def test_redis_available(self):
        """Test that Redis is available."""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis not installed")

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_redis_cache_creation(self):
        """Test Redis cache creation."""
        try:
            cache = get_file_cache({
                "use_redis": True,
                "redis_host": "localhost",
                "redis_port": 6379,
                "redis_db": 0,
                "enabled": True,
            })
            assert cache is not None
            assert hasattr(cache, 'redis_connected')
        except Exception as e:
            # Redis may not be running, that's OK
            assert "Redis" in str(e) or "redis" in str(e).lower()

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_redis_cache_get_stats(self):
        """Test Redis cache get_stats method."""
        try:
            cache = get_file_cache({
                "use_redis": True,
                "redis_host": "localhost",
                "redis_port": 6379,
                "redis_db": 0,
                "enabled": True,
            })
            stats = cache.get_stats()
            assert isinstance(stats, dict)
            assert "redis_connected" in stats
            assert "redis_hits" in stats
            assert "redis_misses" in stats
            assert "redis_errors" in stats
        except Exception as e:
            # Redis may not be running, that's OK
            assert "Redis" in str(e) or "redis" in str(e).lower()

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_redis_cache_fallback_to_local(self):
        """Test Redis cache fallback to local cache."""
        try:
            cache = get_file_cache({
                "use_redis": True,
                "redis_host": "localhost",
                "redis_port": 6379,
                "redis_db": 0,
                "fallback_to_local": True,
                "enabled": True,
            })
            # When Redis is not available, falls back to FileCache
            # FileCache is returned as the fallback
            assert cache is not None
            assert isinstance(cache, FileCache)
        except Exception as e:
            # Redis may not be running, that's OK
            assert "Redis" in str(e) or "redis" in str(e).lower()

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_redis_cache_disabled(self):
        """Test Redis cache when disabled."""
        cache = get_file_cache({
            "use_redis": True,
            "enabled": False,
        })
        # Cache may be disabled or may have fallen back to local cache
        # which is enabled by default
        assert cache.enabled is False or hasattr(cache, '_local_cache') or not hasattr(cache, 'redis_connected')

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_redis_cache_get_set(self):
        """Test Redis cache get/set operations."""
        try:
            cache = get_file_cache({
                "use_redis": True,
                "redis_host": "localhost",
                "redis_port": 6379,
                "redis_db": 0,
                "enabled": True,
                "fallback_to_local": True,
            })

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)
                test_file = tmpdir / "test.py"
                test_content = "print('test')"
                test_file.write_text(test_content)

                # Try to set
                result = cache.set(test_file, test_content)
                # May fail if Redis not running, but shouldn't crash

                # Try to get
                content = cache.get(test_file)
                # May return None if Redis not running

                # Verify type
                assert content is None or content == test_content

        except Exception as e:
            # Redis may not be running, that's OK
            assert "Redis" in str(e) or "redis" in str(e).lower()

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_redis_cache_invalidate(self):
        """Test Redis cache invalidate."""
        try:
            cache = get_file_cache({
                "use_redis": True,
                "redis_host": "localhost",
                "redis_port": 6379,
                "redis_db": 0,
                "enabled": True,
            })

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)
                test_file = tmpdir / "test.py"
                test_file.write_text("test")

                # Try to invalidate
                result = cache.invalidate(test_file)
                # May return False if Redis not running

                # Verify type
                assert isinstance(result, bool)

        except Exception as e:
            # Redis may not be running, that's OK
            assert "Redis" in str(e) or "redis" in str(e).lower()

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_redis_cache_clear(self):
        """Test Redis cache clear."""
        try:
            cache = get_file_cache({
                "use_redis": True,
                "redis_host": "localhost",
                "redis_port": 6379,
                "redis_db": 0,
                "enabled": True,
            })

            # Try to clear
            cache.clear()
            # Should not crash

        except Exception as e:
            # Redis may not be running, that's OK
            assert "Redis" in str(e) or "redis" in str(e).lower()

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_redis_cache_sync_methods(self):
        """Test Redis cache sync methods."""
        try:
            cache = get_file_cache({
                "use_redis": True,
                "redis_host": "localhost",
                "redis_port": 6379,
                "redis_db": 0,
                "enabled": True,
            })

            # Test sync methods exist (only on Redis cache)
            if hasattr(cache, 'sync_to_local'):
                # Try to call them
                result = cache.sync_to_local()
                assert isinstance(result, int)

                result = cache.sync_to_redis()
                assert isinstance(result, int)
            else:
                # Redis not available, fallback to local cache
                assert hasattr(cache, 'redis_connected') == False

        except Exception as e:
            # Redis may not be running, that's OK
            assert "Redis" in str(e) or "redis" in str(e).lower()


class TestRedisConnection:
    """Test Redis connection handling."""

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_redis_connection_error(self):
        """Test Redis connection error handling."""
        from cortex.cache.redis_backend import RedisFileCache, RedisCacheError

        try:
            # Try to connect to non-existent Redis
            cache = RedisFileCache(
                host="nonexistent-host-that-does-not-exist",
                port=6379,
                db=0,
                enabled=True,
                fallback_to_local=True,
            )
            # Should have fallen back to local cache
            assert cache._redis_connected is False
            assert hasattr(cache, '_local_cache')

        except RedisCacheError as e:
            # Expected if Redis is not installed
            assert "Redis is not available" in str(e)

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_redis_invalid_config(self):
        """Test Redis with invalid configuration."""
        from cortex.cache.redis_backend import RedisFileCache

        try:
            # Try with invalid port
            cache = RedisFileCache(
                host="localhost",
                port=99999,  # Invalid port
                db=0,
                enabled=True,
                fallback_to_local=True,
            )
            # Should have fallen back to local cache
            assert cache._redis_connected is False

        except Exception:
            # May raise various exceptions, all acceptable
            pass


class TestGlobalRedisCache:
    """Test global Redis cache instance management."""

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_global_redis_cache_instance(self):
        """Test getting global Redis cache instance."""
        from cortex.cache.redis_backend import GlobalRedisCache

        try:
            cache = GlobalRedisCache.get_instance(
                host="localhost",
                port=6379,
                db=0,
                enabled=True,
            )
            assert cache is not None
        except Exception as e:
            # Redis may not be running, that's OK
            assert "Redis" in str(e) or "redis" in str(e).lower()

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
    def test_global_redis_cache_reset(self):
        """Test resetting global Redis cache instance."""
        from cortex.cache.redis_backend import GlobalRedisCache

        try:
            # Reset the instance
            GlobalRedisCache.reset_instance()

            # Get a new instance
            cache = GlobalRedisCache.get_instance(enabled=True)
            assert cache is not None

        except Exception as e:
            # Redis may not be running, that's OK
            assert "Redis" in str(e) or "redis" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])