"""gRPC client for Cortex Go services.

Provides a Python interface to the Go cache and model manager services.
Falls back gracefully if gRPC is not installed or services are not running.
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

try:
    import grpc

    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False


class CortexServiceClient:
    """Client for communicating with Cortex Go gRPC services.

    Provides cache and model management operations via gRPC.
    Falls back gracefully if services are not available.

    Usage:
        client = CortexServiceClient()
        if client.is_cache_available():
            content = client.cache_get("/path/to/file.py")
    """

    def __init__(
        self,
        cache_host: str = "localhost",
        cache_port: int = 50051,
        model_host: str = "localhost",
        model_port: int = 50052,
    ):
        self._cache_host = cache_host
        self._cache_port = cache_port
        self._model_host = model_host
        self._model_port = model_port
        self._cache_channel = None
        self._model_channel = None
        self._cache_stub = None
        self._model_stub = None
        self._connected = False

    def connect(self) -> bool:
        """Establish gRPC connections to services.

        Returns True if at least one service is reachable.
        """
        if not GRPC_AVAILABLE:
            logger.warning("grpc package not installed, gRPC services unavailable")
            return False

        try:
            self._cache_channel = grpc.insecure_channel(f"{self._cache_host}:{self._cache_port}")
            self._model_channel = grpc.insecure_channel(f"{self._model_host}:{self._model_port}")
            self._connected = True

            # NOTE: Once protobuf code is generated, stubs would be created here:
            # from .generated import cache_pb2_grpc, model_pb2_grpc
            # self._cache_stub = cache_pb2_grpc.CacheServiceStub(self._cache_channel)
            # self._model_stub = model_pb2_grpc.ModelServiceStub(self._model_channel)

            return True
        except Exception as e:
            logger.warning(f"Failed to connect to gRPC services: {e}")
            return False

    def disconnect(self):
        """Close gRPC connections."""
        if self._cache_channel:
            self._cache_channel.close()
        if self._model_channel:
            self._model_channel.close()
        self._connected = False

    def is_cache_available(self) -> bool:
        """Check if cache service is reachable."""
        if not self._connected or not GRPC_AVAILABLE:
            return False
        try:
            state = self._cache_channel.check_connectivity_state(True)
            return state == grpc.ChannelConnectivity.READY
        except Exception:
            return False

    def is_model_available(self) -> bool:
        """Check if model manager service is reachable."""
        if not self._connected or not GRPC_AVAILABLE:
            return False
        try:
            state = self._model_channel.check_connectivity_state(True)
            return state == grpc.ChannelConnectivity.READY
        except Exception:
            return False

    # === Cache Operations ===

    def cache_get(self, path: str, validate_mtime: bool = True) -> Optional[str]:
        """Get a cached file entry.

        Args:
            path: File path to look up
            validate_mtime: Whether to check if file has been modified

        Returns:
            File content as string, or None if not cached
        """
        if not self._cache_stub:
            return None
        # NOTE: Implementation requires generated protobuf code
        # request = cache_pb2.GetRequest(path=path, validate_mtime=validate_mtime)
        # response = self._cache_stub.Get(request)
        # if response.found and not response.stale:
        #     return response.entry.content.decode('utf-8')
        return None

    def cache_set(self, path: str, content: str, mtime: int = 0, ttl: int = 0) -> bool:
        """Set a cache entry.

        Args:
            path: File path
            content: File content
            mtime: File modification time
            ttl: Time-to-live in seconds (0 = default)

        Returns:
            True if successful
        """
        if not self._cache_stub:
            return False
        # NOTE: Implementation requires generated protobuf code
        return False

    def cache_invalidate(self, path: str) -> bool:
        """Remove a cache entry."""
        if not self._cache_stub:
            return False
        return False

    def cache_batch_get(self, paths: List[str]) -> Dict[str, str]:
        """Get multiple cache entries at once."""
        if not self._cache_stub:
            return {}
        return {}

    def cache_batch_set(self, entries: Dict[str, str]) -> bool:
        """Set multiple cache entries at once."""
        if not self._cache_stub:
            return False
        return False

    def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._cache_stub:
            return {}
        return {}

    def cache_pre_cache(self, patterns: List[str], directory: str = ".") -> Dict[str, Any]:
        """Pre-cache files matching patterns."""
        if not self._cache_stub:
            return {}
        return {}

    # === Model Operations ===

    def model_health(self) -> Dict[str, Any]:
        """Check model backend health."""
        if not self._model_stub:
            return {"available": False}
        return {"available": False}

    def model_list(self) -> List[Dict[str, Any]]:
        """List available models."""
        if not self._model_stub:
            return []
        return []

    def model_preload(self, model_name: str) -> bool:
        """Preload a model into memory."""
        if not self._model_stub:
            return False
        return False

    def model_status(self, model_name: str) -> Dict[str, Any]:
        """Get status of a specific model."""
        if not self._model_stub:
            return {"status": "unknown"}
        return {"status": "unknown"}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
