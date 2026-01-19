"""Rate limiting for API calls using token bucket algorithm."""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    burst_multiplier: float = 1.5  # Allow burst up to 1.5x the rate


class TokenBucket:
    """
    Token bucket rate limiter.

    Allows bursting up to bucket capacity, then rate-limits to refill rate.
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,  # tokens per second
    ):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def acquire(self, tokens: float = 1.0, blocking: bool = True) -> bool:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire
            blocking: If True, wait for tokens. If False, return immediately.

        Returns:
            True if tokens acquired, False if non-blocking and insufficient tokens
        """
        with self._lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            if not blocking:
                return False

            # Calculate wait time
            needed = tokens - self.tokens
            wait_time = needed / self.refill_rate

        # Wait outside lock
        time.sleep(wait_time)

        with self._lock:
            self._refill()
            self.tokens -= tokens
            return True

    def get_wait_time(self, tokens: float = 1.0) -> float:
        """Get estimated wait time to acquire tokens."""
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                return 0.0
            needed = tokens - self.tokens
            return needed / self.refill_rate

    @property
    def available(self) -> float:
        """Get currently available tokens."""
        with self._lock:
            self._refill()
            return self.tokens


class RateLimiter:
    """
    Rate limiter for API calls.

    Supports both request-based and token-based rate limiting.
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()

        # Request rate limiter (requests per minute)
        request_capacity = self.config.requests_per_minute * self.config.burst_multiplier
        request_rate = self.config.requests_per_minute / 60.0
        self._request_bucket = TokenBucket(request_capacity, request_rate)

        # Token rate limiter (tokens per minute)
        token_capacity = self.config.tokens_per_minute * self.config.burst_multiplier
        token_rate = self.config.tokens_per_minute / 60.0
        self._token_bucket = TokenBucket(token_capacity, token_rate)

        # Statistics
        self._total_requests = 0
        self._total_tokens = 0
        self._total_wait_time = 0.0
        self._lock = threading.Lock()

    def acquire_request(self, blocking: bool = True) -> bool:
        """
        Acquire permission for one API request.

        Args:
            blocking: If True, wait until permitted

        Returns:
            True if permitted, False if non-blocking and rate limited
        """
        start = time.monotonic()
        result = self._request_bucket.acquire(1.0, blocking)
        wait_time = time.monotonic() - start

        with self._lock:
            if result:
                self._total_requests += 1
            self._total_wait_time += wait_time

        if wait_time > 0.1:
            logger.debug(f"Rate limiter waited {wait_time:.2f}s for request")

        return result

    def acquire_tokens(self, token_count: int, blocking: bool = True) -> bool:
        """
        Acquire permission for token usage.

        Args:
            token_count: Number of tokens to be used
            blocking: If True, wait until permitted

        Returns:
            True if permitted, False if non-blocking and rate limited
        """
        start = time.monotonic()
        result = self._token_bucket.acquire(float(token_count), blocking)
        wait_time = time.monotonic() - start

        with self._lock:
            if result:
                self._total_tokens += token_count
            self._total_wait_time += wait_time

        if wait_time > 0.1:
            logger.debug(f"Rate limiter waited {wait_time:.2f}s for {token_count} tokens")

        return result

    def acquire(
        self,
        token_count: int = 0,
        blocking: bool = True,
    ) -> bool:
        """
        Acquire permission for an API call.

        Args:
            token_count: Estimated token count (0 for request-only limiting)
            blocking: If True, wait until permitted

        Returns:
            True if permitted, False if non-blocking and rate limited
        """
        # Always check request limit
        if not self.acquire_request(blocking):
            return False

        # Check token limit if specified
        if token_count > 0:
            if not self.acquire_tokens(token_count, blocking):
                return False

        return True

    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        with self._lock:
            return {
                "total_requests": self._total_requests,
                "total_tokens": self._total_tokens,
                "total_wait_time_seconds": round(self._total_wait_time, 2),
                "requests_available": round(self._request_bucket.available, 1),
                "tokens_available": round(self._token_bucket.available, 0),
                "config": {
                    "requests_per_minute": self.config.requests_per_minute,
                    "tokens_per_minute": self.config.tokens_per_minute,
                },
            }

    def reset(self) -> None:
        """Reset rate limiter state (for testing)."""
        self._request_bucket.tokens = self._request_bucket.capacity
        self._token_bucket.tokens = self._token_bucket.capacity
        with self._lock:
            self._total_requests = 0
            self._total_tokens = 0
            self._total_wait_time = 0.0


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """
    Get or create the global rate limiter.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        Global RateLimiter instance
    """
    global _global_rate_limiter
    with _rate_limiter_lock:
        if _global_rate_limiter is None:
            _global_rate_limiter = RateLimiter(config)
        return _global_rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (for testing)."""
    global _global_rate_limiter
    with _rate_limiter_lock:
        _global_rate_limiter = None
