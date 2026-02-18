"""Feature flag system for Cortex hybrid architecture.

Enables gradual rollout of native (Rust/Go) components with safe fallback
to Python implementations.
"""

import logging
import threading
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FeatureFlag(Enum):
    """Available feature flags for hybrid components."""

    # Rust native extensions (Phase 2)
    RUST_SEARCH = "rust_search"
    RUST_AST = "rust_ast"
    RUST_TOKENIZER = "rust_tokenizer"

    # Go services (Phase 3)
    GO_CACHE = "go_cache"
    GO_MODEL_MANAGER = "go_model_manager"

    # Infrastructure
    PROFILING = "profiling"


# Default states for all flags
_DEFAULT_FLAGS: Dict[FeatureFlag, bool] = {
    FeatureFlag.RUST_SEARCH: True,
    FeatureFlag.RUST_AST: True,
    FeatureFlag.RUST_TOKENIZER: True,
    FeatureFlag.GO_CACHE: True,
    FeatureFlag.GO_MODEL_MANAGER: True,
    FeatureFlag.PROFILING: False,
}


class FeatureManager:
    """Manages feature flags for hybrid Cortex components.

    Supports:
    - Enable/disable flags at runtime
    - Platform capability detection (is the native extension available?)
    - Automatic fallback from native to Python implementation
    - Usage statistics tracking

    Usage:
        fm = FeatureManager.get_instance()

        if fm.is_enabled(FeatureFlag.RUST_SEARCH):
            result = native_search(...)
        else:
            result = python_search(...)

        # Or with automatic fallback:
        result = fm.with_fallback(
            FeatureFlag.RUST_SEARCH,
            native_fn=native_search,
            fallback_fn=python_search,
            pattern, path
        )
    """

    _instance: Optional["FeatureManager"] = None
    _lock = threading.Lock()

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._flags: Dict[FeatureFlag, bool] = dict(_DEFAULT_FLAGS)
        self._stats_lock = threading.Lock()
        self._stats: Dict[str, Dict[str, int]] = {}
        self._capability_cache: Dict[FeatureFlag, bool] = {}

        if config:
            self._apply_config(config)

    @classmethod
    def get_instance(cls, config: Optional[Dict[str, Any]] = None) -> "FeatureManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    def _apply_config(self, config: Dict[str, Any]):
        """Apply configuration to feature flags."""
        for flag in FeatureFlag:
            key = flag.value
            if key in config:
                self._flags[flag] = bool(config[key])

    def is_enabled(self, flag: FeatureFlag) -> bool:
        """Check if a feature flag is enabled."""
        return self._flags.get(flag, False)

    def enable(self, flag: FeatureFlag):
        """Enable a feature flag."""
        self._flags[flag] = True
        logger.info(f"Feature flag enabled: {flag.value}")

    def disable(self, flag: FeatureFlag):
        """Disable a feature flag."""
        self._flags[flag] = False
        logger.info(f"Feature flag disabled: {flag.value}")

    def get_all_flags(self) -> Dict[str, bool]:
        """Get all feature flags and their current states."""
        return {flag.value: enabled for flag, enabled in self._flags.items()}

    def check_capability(self, flag: FeatureFlag) -> bool:
        """Check if the native capability for a flag is actually available.

        This checks whether the required native extension/service is
        importable or reachable, regardless of whether the flag is enabled.
        """
        if flag in self._capability_cache:
            return self._capability_cache[flag]

        available = False
        try:
            if flag in (FeatureFlag.RUST_SEARCH, FeatureFlag.RUST_AST, FeatureFlag.RUST_TOKENIZER):
                available = _check_rust_available()
            elif flag == FeatureFlag.GO_CACHE:
                available = _check_go_cache_available()
            elif flag == FeatureFlag.GO_MODEL_MANAGER:
                available = _check_go_model_manager_available()
            elif flag == FeatureFlag.PROFILING:
                available = True
        except Exception:
            available = False

        self._capability_cache[flag] = available
        return available

    def clear_capability_cache(self):
        """Clear the capability cache (e.g., after installing an extension)."""
        self._capability_cache.clear()

    def with_fallback(
        self,
        flag: FeatureFlag,
        native_fn: Callable[..., T],
        fallback_fn: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """Execute native function if flag enabled, fallback on error.

        Args:
            flag: Feature flag to check
            native_fn: Native (Rust/Go) implementation
            fallback_fn: Python fallback implementation
            *args, **kwargs: Arguments passed to the chosen function

        Returns:
            Result from whichever function succeeds
        """
        flag_name = flag.value

        if self.is_enabled(flag):
            try:
                result = native_fn(*args, **kwargs)
                self._record_stat(flag_name, "native_success")
                return result
            except (ImportError, OSError, RuntimeError) as e:
                logger.warning(
                    f"Native implementation for {flag_name} failed, "
                    f"falling back to Python: {e}"
                )
                self._record_stat(flag_name, "native_fallback")

        result = fallback_fn(*args, **kwargs)
        self._record_stat(flag_name, "python_used")
        return result

    def _record_stat(self, flag_name: str, event: str):
        with self._stats_lock:
            if flag_name not in self._stats:
                self._stats[flag_name] = {}
            self._stats[flag_name][event] = self._stats[flag_name].get(event, 0) + 1

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get usage statistics for all flags."""
        with self._stats_lock:
            return dict(self._stats)

    def get_flag_stats(self, flag: FeatureFlag) -> Dict[str, int]:
        """Get usage statistics for a specific flag."""
        with self._stats_lock:
            return dict(self._stats.get(flag.value, {}))


def _check_rust_available() -> bool:
    """Check if Rust native extension (cortex_native) is importable."""
    try:
        import cortex_native  # noqa: F401

        return True
    except ImportError:
        return False


def _check_go_cache_available() -> bool:
    """Check if Go cache gRPC service is reachable."""
    try:
        import grpc

        channel = grpc.insecure_channel("localhost:50051")
        state = channel.check_connectivity_state(True)
        channel.close()
        return state == grpc.ChannelConnectivity.READY
    except Exception:
        return False


def _check_go_model_manager_available() -> bool:
    """Check if Go model manager gRPC service is reachable."""
    try:
        import grpc

        channel = grpc.insecure_channel("localhost:50052")
        state = channel.check_connectivity_state(True)
        channel.close()
        return state == grpc.ChannelConnectivity.READY
    except Exception:
        return False
