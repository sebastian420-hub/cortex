"""Redis backend for distributed file caching.

This module provides a Redis-based backend for the file cache,
enabling cache sharing across multiple Cortex instances.

Features:
- Redis-backed storage for distributed cache
- Configurable Redis connection parameters
- Cache synchronization across instances
- Automatic fallback to local cache on connection failure
- TTL support for automatic cache expiration

Usage:
    cache = RedisFileCache(
        host='localhost',
        port=6379,
        db=0,
        ttl=3600  # 1 hour
    )
"""

import json
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from .file_cache import CacheEntry, FileCache

logger = logging.getLogger(__name__)


class RedisCacheError(Exception):
    """Exception raised for Redis cache errors."""
    pass


class RedisFileCache(FileCache):
    """
    Redis-backed file cache for distributed caching.

    This cache uses Redis as the backend storage, allowing multiple
    Cortex instances to share the same cache.

    Features:
    - Distributed cache across multiple instances
    - Automatic fallback to local cache on Redis failure
    - Configurable TTL for cache entries
    - Thread-safe operations
    - Cache synchronization

    Args:
        host: Redis host (default: localhost)
        port: Redis port (default: 6379)
        db: Redis database number (default: 0)
        password: Redis password (optional)
        ttl: Time-to-live in seconds for cache entries (default: 3600)
        max_entries: Maximum number of entries in local cache (default: 100)
        max_size_mb: Maximum cache size in MB (default: 50)
        enabled: Whether to enable the cache (default: True)
        fallback_to_local: Whether to fall back to local cache on Redis failure (default: True)
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ttl: int = 3600,
        max_entries: int = 100,
        max_size_mb: float = 50.0,
        enabled: bool = True,
        fallback_to_local: bool = True,
    ):
        if not REDIS_AVAILABLE:
            raise RedisCacheError(
                "Redis is not available. Please install it with: pip install redis"
            )

        super().__init__(max_entries=max_entries, max_size_mb=max_size_mb, enabled=enabled)

        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.ttl = ttl
        self.fallback_to_local = fallback_to_local

        self._redis_client: Optional[redis.Redis] = None
        self._redis_connected = False
        self._redis_lock = threading.Lock()
        self._local_cache = FileCache(max_entries=max_entries, max_size_mb=max_size_mb, enabled=enabled)

        # Statistics
        self._redis_hits = 0
        self._redis_misses = 0
        self._redis_errors = 0
        self._local_fallback_hits = 0
        self._local_fallback_misses = 0

        # Initialize Redis connection
        self._connect()

    def _connect(self) -> bool:
        """
        Establish connection to Redis server.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            self._redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=False,  # We'll handle decoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5,
                retry=False,  # Don't retry on timeout (deprecated)
            )

            # Test connection
            self._redis_client.ping()
            self._redis_connected = True
            logger.info(f"Connected to Redis at {self.host}:{self.port}/{self.db}")
            return True

        except redis.ConnectionError as e:
            logger.warning(f"Redis connection failed: {e}")
            self._redis_connected = False
            self._redis_errors += 1
            return False

        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            self._redis_connected = False
            self._redis_errors += 1
            return False

    def _ensure_connection(self) -> bool:
        """Ensure Redis connection is active, reconnect if needed."""
        if not self.enabled:
            return False

        if not self._redis_connected:
            return self._connect()

        # Test connection if it's been a while since last check
        try:
            self._redis_client.ping()
            return True
        except redis.ConnectionError:
            logger.warning("Redis connection lost, attempting to reconnect...")
            return self._connect()

    def get(self, path: Path) -> Optional[str]:
        """
        Get file content from cache (Redis first, then local fallback).

        Args:
            path: Path to the file

        Returns:
            Cached content or None
        """
        if not self.enabled:
            return None

        # Try Redis first
        if self._ensure_connection():
            try:
                key = str(path.resolve())
                data = self._redis_client.get(f"file_cache:{key}")

                if data is not None:
                    # Decode and validate
                    entry_dict = json.loads(data.decode('utf-8'))

                    # Validate mtime
                    current_mtime = path.stat().st_mtime if path.exists() else None
                    if current_mtime and current_mtime != entry_dict['mtime']:
                        # File changed, invalidate
                        self.invalidate(path)
                        self._redis_misses += 1
                        return None

                    # Update access info
                    self._redis_client.hset(
                        f"file_cache:{key}:meta",
                        mapping={
                            "accessed_at": datetime.now().isoformat(),
                            "hit_count": str(int(entry_dict.get('hit_count', 0)) + 1),
                        }
                    )
                    self._redis_client.expire(f"file_cache:{key}", self.ttl)
                    self._redis_client.expire(f"file_cache:{key}:meta", self.ttl)

                    self._redis_hits += 1
                    return entry_dict['content']

            except (redis.RedisError, json.JSONDecodeError, KeyError) as e:
                logger.debug(f"Redis get error: {e}")
                self._redis_errors += 1

        # Fallback to local cache
        if self.fallback_to_local:
            local_result = self._local_cache.get(path)
            if local_result is not None:
                self._local_fallback_hits += 1
                return local_result
            self._local_fallback_misses += 1

        self._redis_misses += 1
        return None

    def set(self, path: Path, content: str) -> bool:
        """
        Cache file content in Redis (and local cache).

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

        # Get mtime
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return False

        # Prepare cache entry
        entry = {
            "content": content,
            "mtime": mtime,
            "size": content_size,
            "accessed_at": datetime.now().isoformat(),
            "hit_count": 0,
        }

        success = False

        # Try Redis first
        if self._ensure_connection():
            try:
                # Store in Redis with TTL
                self._redis_client.setex(
                    f"file_cache:{key}",
                    self.ttl,
                    json.dumps(entry).encode('utf-8')
                )

                # Store metadata
                self._redis_client.hset(
                    f"file_cache:{key}:meta",
                    mapping={
                        "size": str(content_size),
                        "cached_at": datetime.now().isoformat(),
                    }
                )
                self._redis_client.expire(f"file_cache:{key}:meta", self.ttl)

                success = True

            except redis.RedisError as e:
                logger.debug(f"Redis set error: {e}")
                self._redis_errors += 1
                success = False

        # Also store in local cache for quick access
        if self.fallback_to_local:
            self._local_cache.set(path, content)

        if success:
            logger.debug(f"Redis cached: {path} ({content_size} bytes)")
        else:
            logger.debug(f"Redis cache failed: {path}")

        return success

    def invalidate(self, path: Path) -> bool:
        """
        Invalidate cache entry for a path.

        Args:
            path: Path to invalidate

        Returns:
            True if entry was found and removed
        """
        key = str(path.resolve())
        removed = False

        # Invalidate from Redis
        if self._ensure_connection():
            try:
                count = self._redis_client.delete(
                    f"file_cache:{key}",
                    f"file_cache:{key}:meta"
                )
                if count > 0:
                    removed = True
            except redis.RedisError as e:
                logger.debug(f"Redis invalidate error: {e}")
                self._redis_errors += 1

        # Also invalidate from local cache
        self._local_cache.invalidate(path)

        if removed:
            logger.debug(f"Redis cache invalidated: {path}")

        return removed

    def clear(self) -> None:
        """Clear all cached entries from Redis and local cache."""
        # Clear local cache
        self._local_cache.clear()

        # Clear Redis cache
        if self._ensure_connection():
            try:
                # Use SCAN to find all file_cache keys and delete them
                cursor = 0
                deleted = 0
                while True:
                    cursor, keys = self._redis_client.scan(
                        cursor, match="file_cache:*", count=100
                    )
                    if keys:
                        self._redis_client.delete(*keys)
                        deleted += len(keys)
                    if cursor == 0:
                        break
                logger.debug(f"Redis cache cleared: {deleted} entries deleted")
            except redis.RedisError as e:
                logger.debug(f"Redis clear error: {e}")
                self._redis_errors += 1

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        stats = super().get_stats()

        # Add Redis-specific stats
        redis_stats = {
            "redis_connected": self._redis_connected,
            "redis_hits": self._redis_hits,
            "redis_misses": self._redis_misses,
            "redis_errors": self._redis_errors,
            "local_fallback_hits": self._local_fallback_hits,
            "local_fallback_misses": self._local_fallback_misses,
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "ttl": self.ttl,
        }

        # Get Redis info if connected
        if self._ensure_connection():
            try:
                info = self._redis_client.info()
                redis_stats.update({
                    "redis_memory_used": info.get('used_memory_human', 'N/A'),
                    "redis_connected_clients": info.get('connected_clients', 0),
                    "redis_uptime_days": info.get('uptime_in_days', 0),
                })
            except redis.RedisError:
                pass

        stats.update(redis_stats)
        return stats

    def sync_to_local(self) -> int:
        """
        Sync Redis cache to local cache.

        Useful for when Redis is temporarily unavailable.

        Returns:
            Number of entries synced
        """
        if not self._ensure_connection():
            logger.warning("Cannot sync to local: Redis not connected")
            return 0

        synced = 0
        try:
            # Get all file_cache keys
            cursor = 0
            while True:
                cursor, keys = self._redis_client.scan(
                    cursor, match="file_cache:*:meta", count=50
                )

                for meta_key in keys:
                    try:
                        # Get metadata
                        meta_data = self._redis_client.hgetall(meta_key)
                        if not meta_data:
                            continue

                        # Get actual cache entry
                        cache_key = meta_key.replace(":meta", "")
                        data = self._redis_client.get(cache_key)
                        if data is None:
                            continue

                        # Parse and add to local cache
                        entry_dict = json.loads(data.decode('utf-8'))
                        filepath = Path(cache_key.replace("file_cache:", ""))

                        if filepath.exists():
                            self._local_cache.set(filepath, entry_dict['content'])
                            synced += 1

                    except (redis.RedisError, json.JSONDecodeError, KeyError) as e:
                        logger.debug(f"Error syncing entry {meta_key}: {e}")

                if cursor == 0:
                    break

        except redis.RedisError as e:
            logger.error(f"Redis sync error: {e}")

        logger.info(f"Synced {synced} entries from Redis to local cache")
        return synced

    def sync_to_redis(self) -> int:
        """
        Sync local cache to Redis.

        Useful for when Redis connection is restored.

        Returns:
            Number of entries synced
        """
        if not self._ensure_connection():
            logger.warning("Cannot sync to Redis: Redis not connected")
            return 0

        synced = 0
        with self._local_cache._lock:
            for key, entry in self._local_cache._cache.items():
                try:
                    # Get filepath from key
                    filepath = Path(key)

                    # Prepare entry data
                    entry_data = {
                        "content": entry.content,
                        "mtime": entry.mtime,
                        "size": entry.size,
                        "accessed_at": entry.accessed_at.isoformat(),
                        "hit_count": entry.hit_count,
                    }

                    # Store in Redis
                    self._redis_client.setex(
                        f"file_cache:{key}",
                        self.ttl,
                        json.dumps(entry_data).encode('utf-8')
                    )

                    synced += 1

                except (redis.RedisError, Exception) as e:
                    logger.debug(f"Error syncing entry {key}: {e}")

        logger.info(f"Synced {synced} entries from local cache to Redis")
        return synced


class GlobalRedisCache:
    """Global Redis cache instance management."""

    _instance: Optional[RedisFileCache] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(
        cls,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ttl: int = 3600,
        max_entries: int = 100,
        max_size_mb: float = 50.0,
        enabled: bool = True,
        fallback_to_local: bool = True,
    ) -> RedisFileCache:
        """
        Get or create global Redis cache instance.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password
            ttl: Time-to-live in seconds
            max_entries: Maximum entries in local cache
            max_size_mb: Maximum cache size in MB
            enabled: Whether to enable the cache
            fallback_to_local: Whether to fall back to local cache

        Returns:
            RedisFileCache instance
        """
        with cls._lock:
            if cls._instance is None:
                try:
                    cls._instance = RedisFileCache(
                        host=host,
                        port=port,
                        db=db,
                        password=password,
                        ttl=ttl,
                        max_entries=max_entries,
                        max_size_mb=max_size_mb,
                        enabled=enabled,
                        fallback_to_local=fallback_to_local,
                    )
                    logger.info("Global Redis cache instance created")
                except RedisCacheError as e:
                    logger.warning(f"Failed to create Redis cache: {e}")
                    # Fall back to local cache
                    from .file_cache import get_file_cache
                    cls._instance = get_file_cache()  # type: ignore
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the global Redis cache instance (for testing)."""
        with cls._lock:
            cls._instance = None
            logger.debug("Global Redis cache instance reset")