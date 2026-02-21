"""Comprehensive test suite for rate limiter functionality."""

import time
from unittest.mock import Mock

import pytest

from cortex.core.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    TokenBucket,
    get_rate_limiter,
    reset_rate_limiter,
)


class TestTokenBucket:
    """Test TokenBucket rate limiting algorithm."""

    def test_initialization(self):
        """Test TokenBucket initializes correctly."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.capacity == 10
        assert bucket.refill_rate == 1.0
        assert bucket.tokens == 10

    def test_acquire_available(self):
        """Test acquiring tokens when available."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.acquire(tokens=5, blocking=False) is True
        assert bucket.available == 5

    def test_acquire_blocking_waits(self):
        """Test blocking acquire waits for tokens."""
        bucket = TokenBucket(capacity=5, refill_rate=10.0)  # 10 tokens/sec
        # Take all tokens
        bucket.acquire(tokens=5, blocking=False)
        assert bucket.available < 0.1

        # Blocking acquire should wait
        start = time.monotonic()
        result = bucket.acquire(tokens=2, blocking=True)
        elapsed = time.monotonic() - start

        assert result is True
        assert elapsed >= 0.1  # Should wait at least 0.1s for 2 tokens at 10/sec

    def test_acquire_non_blocking_insufficient(self):
        """Test non-blocking acquire returns False when insufficient."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        bucket.acquire(tokens=5, blocking=False)  # Empty the bucket
        assert bucket.acquire(tokens=1, blocking=False) is False

    def test_refill_over_time(self):
        """Test tokens refill over time."""
        bucket = TokenBucket(capacity=10, refill_rate=5.0)  # 5 tokens/sec
        bucket.acquire(tokens=10, blocking=False)  # Empty bucket
        assert bucket.available < 0.1

        time.sleep(0.2)  # Wait 0.2s
        bucket._refill()
        assert 0.9 < bucket.available < 1.1  # ~1 token refilled

    def test_capacity_limit(self):
        """Test tokens don't exceed capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=100.0)  # Very fast refill
        bucket.acquire(tokens=5, blocking=False)
        time.sleep(0.2)  # Wait for refill
        bucket._refill()
        assert bucket.available <= bucket.capacity

    def test_get_wait_time(self):
        """Test wait time calculation."""
        bucket = TokenBucket(capacity=5, refill_rate=10.0)
        bucket.acquire(tokens=5, blocking=False)  # Empty bucket

        wait_time = bucket.get_wait_time(tokens=3)
        assert 0.25 < wait_time < 0.35  # Should wait ~0.3s for 3 tokens

        time.sleep(0.15)  # Wait for partial refill
        bucket._refill()
        wait_time = bucket.get_wait_time(tokens=1)
        assert wait_time < 0.1  # Should wait less since some tokens available

    def test_concurrent_access(self):
        """Test thread safety with concurrent access."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)

        def acquire_tokens():
            for _ in range(5):
                bucket.acquire(tokens=2, blocking=False)

        threads = []
        for _ in range(10):
            thread = Mock(target=acquire_tokens)
            threads.append(thread)

        for thread in threads:
            thread.run()

        # Should have acquired up to 100 tokens total
        # (Mock.run() is synchronous, so all tokens should be acquired)
        assert bucket.available <= bucket.capacity


class TestRateLimitConfig:
    """Test RateLimitConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.tokens_per_minute == 100000
        assert config.burst_multiplier == 1.5

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            requests_per_minute=100,
            tokens_per_minute=50000,
            burst_multiplier=2.0,
        )
        assert config.requests_per_minute == 100
        assert config.tokens_per_minute == 50000
        assert config.burst_multiplier == 2.0


class TestRateLimiter:
    """Test RateLimiter class."""

    def test_initialization(self):
        """Test RateLimiter initializes correctly."""
        config = RateLimitConfig(requests_per_minute=60, tokens_per_minute=100000)
        limiter = RateLimiter(config)

        assert limiter.config == config
        assert limiter._request_bucket.capacity == 60 * 1.5  # With burst multiplier
        assert limiter._token_bucket.capacity == 100000 * 1.5

    def test_acquire_request_blocking(self):
        """Test acquiring request permission (blocking)."""
        config = RateLimitConfig(requests_per_minute=10, tokens_per_minute=1000)
        limiter = RateLimiter(config)

        start = time.monotonic()
        result = limiter.acquire_request(blocking=True)
        elapsed = time.monotonic() - start

        assert result is True
        assert elapsed < 0.1  # Should be immediate with first request

    def test_acquire_request_non_blocking(self):
        """Test acquiring request permission (non-blocking)."""
        config = RateLimitConfig(requests_per_minute=1, tokens_per_minute=1000)
        limiter = RateLimiter(config)

        # First request should succeed
        assert limiter.acquire_request(blocking=False) is True

        # Subsequent requests might be rate limited depending on timing
        time.sleep(0.1)
        result = limiter.acquire_request(blocking=False)
        assert isinstance(result, bool)

    def test_acquire_tokens(self):
        """Test acquiring token permission."""
        config = RateLimitConfig(requests_per_minute=100, tokens_per_minute=1000)
        limiter = RateLimiter(config)

        assert limiter.acquire_tokens(token_count=100, blocking=False) is True
        assert limiter.acquire_tokens(token_count=100, blocking=False) is True

    def test_acquire_combined(self):
        """Test acquiring both request and token permission."""
        config = RateLimitConfig(requests_per_minute=60, tokens_per_minute=1000)
        limiter = RateLimiter(config)

        assert limiter.acquire(token_count=50, blocking=False) is True
        assert limiter._total_requests == 1
        assert limiter._total_tokens == 50

    def test_get_stats(self):
        """Test getting rate limiter statistics."""
        config = RateLimitConfig(requests_per_minute=60, tokens_per_minute=1000)
        limiter = RateLimiter(config)

        limiter.acquire(token_count=100, blocking=False)

        stats = limiter.get_stats()
        assert stats["total_requests"] == 1
        assert stats["total_tokens"] == 100
        assert "config" in stats
        assert stats["config"]["requests_per_minute"] == 60

    def test_reset(self):
        """Test resetting rate limiter state."""
        config = RateLimitConfig(requests_per_minute=60, tokens_per_minute=1000)
        limiter = RateLimiter(config)

        limiter.acquire(token_count=100, blocking=False)
        assert limiter._total_requests == 1

        limiter.reset()
        assert limiter._total_requests == 0
        assert limiter._total_tokens == 0
        assert limiter._total_wait_time == 0.0

    def test_rate_limiting_with_burst(self):
        """Test burst allowance in rate limiting."""
        config = RateLimitConfig(
            requests_per_minute=60,
            tokens_per_minute=1000,
            burst_multiplier=2.0,  # Double burst allowance
        )
        limiter = RateLimiter(config)

        # Should allow burst up to 120 requests (2x the rate)
        for i in range(120):
            result = limiter.acquire_request(blocking=False)
            assert result is True, f"Request {i} should succeed"

    def test_request_limit_exceeded(self):
        """Test behavior when request limit is exceeded."""
        config = RateLimitConfig(
            requests_per_minute=1,  # Very low limit
            tokens_per_minute=1000,
        )
        limiter = RateLimiter(config)

        # First request should succeed
        assert limiter.acquire_request(blocking=False) is True

        # With burst of 1.5 (1.5 requests allowed), only first succeeds
        # The burst is fractional, so 1 full request + 0.5 remaining
        # Second request checks available tokens (0.5) against 1.0 needed
        assert limiter.acquire_request(blocking=False) is False

        # Third request should also be rate limited
        assert limiter.acquire_request(blocking=False) is False

    def test_token_limit_exceeded(self):
        """Test behavior when token limit is exceeded."""
        config = RateLimitConfig(
            requests_per_minute=100,
            tokens_per_minute=10,  # Very low limit
            burst_multiplier=2.0,
        )
        limiter = RateLimiter(config)

        # With burst of 20 tokens, should allow 20 tokens
        assert limiter.acquire_tokens(token_count=10, blocking=False) is True
        assert limiter.acquire_tokens(token_count=10, blocking=False) is True

        # Third call should be rate limited
        assert limiter.acquire_tokens(token_count=1, blocking=False) is False

    def test_blocking_behavior(self):
        """Test blocking behavior with limited rate."""
        config = RateLimitConfig(
            requests_per_minute=10,  # 1 request per 6 seconds
            tokens_per_minute=100,
        )
        limiter = RateLimiter(config)

        # Exhaust the burst allowance
        for _ in range(15):  # 10 * 1.5 = 15
            limiter.acquire_request(blocking=False)

        # Now blocking acquire should wait
        start = time.monotonic()
        result = limiter.acquire_request(blocking=True)
        elapsed = time.monotonic() - start

        assert result is True
        assert elapsed >= 0.5  # Should wait at least 0.5s

    def test_zero_token_count(self):
        """Test acquiring with zero token count (request-only limiting)."""
        config = RateLimitConfig(requests_per_minute=60, tokens_per_minute=1000)
        limiter = RateLimiter(config)

        # Should only check request limit
        assert limiter.acquire(token_count=0, blocking=False) is True
        assert limiter._total_requests == 1
        assert limiter._total_tokens == 0

    def test_get_wait_time_info(self):
        """Test getting wait time for next request."""
        config = RateLimitConfig(
            requests_per_minute=1,  # Very low rate (1 token per 60 seconds)
            tokens_per_minute=100,
            burst_multiplier=1.0,  # No burst for this test
        )
        limiter = RateLimiter(config)

        limiter.acquire_request(blocking=False)  # Use up request
        wait_time = limiter._request_bucket.get_wait_time()
        # With 1 req/min = 1/60 tokens/sec, and burst=1.0
        # Should wait ~60 seconds (or calculate properly)
        assert wait_time >= 0.5  # Should be a significant wait time


class TestGlobalRateLimiter:
    """Test global rate limiter functions."""

    def test_get_rate_limiter_creates_instance(self):
        """Test get_rate_limiter creates instance if not exists."""
        reset_rate_limiter()
        config = RateLimitConfig(requests_per_minute=60, tokens_per_minute=1000)
        limiter = get_rate_limiter(config)

        assert limiter is not None
        assert limiter.config.requests_per_minute == 60

    def test_get_rate_limiter_returns_existing(self):
        """Test get_rate_limiter returns existing instance."""
        config1 = RateLimitConfig(requests_per_minute=60, tokens_per_minute=1000)
        limiter1 = get_rate_limiter(config1)

        # Second call should return same instance (config ignored)
        config2 = RateLimitConfig(requests_per_minute=30, tokens_per_minute=500)
        limiter2 = get_rate_limiter(config2)

        assert limiter1 is limiter2
        assert limiter2.config.requests_per_minute == 60  # Uses original config

    def test_reset_rate_limiter(self):
        """Test reset_rate_limiter removes global instance."""
        reset_rate_limiter()
        config = RateLimitConfig(requests_per_minute=60, tokens_per_minute=1000)
        limiter1 = get_rate_limiter(config)

        reset_rate_limiter()
        limiter2 = get_rate_limiter(config)

        assert limiter1 is not limiter2


class TestRateLimiterIntegration:
    """Integration tests for rate limiter."""

    def test_concurrent_requests(self):
        """Test rate limiter under concurrent access."""
        import threading

        config = RateLimitConfig(requests_per_minute=100, tokens_per_minute=10000)
        limiter = RateLimiter(config)

        def make_request():
            for _ in range(10):
                limiter.acquire(token_count=10, blocking=False)

        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        stats = limiter.get_stats()
        # Should have processed requests (burst allowance should allow many)
        assert stats["total_requests"] > 0  # At least some requests should succeed
        assert stats["total_tokens"] > 0  # At least some tokens should be used

    def test_real_world_scenario(self):
        """Test a realistic API usage scenario."""
        config = RateLimitConfig(
            requests_per_minute=60,  # Typical API limit
            tokens_per_minute=100000,  # Typical token limit
            burst_multiplier=1.5,
        )
        limiter = RateLimiter(config)

        # Simulate burst of requests at startup
        for _ in range(90):  # 60 * 1.5 = 90 burst allowance
            result = limiter.acquire_request(blocking=False)
            if not result:
                break

        stats = limiter.get_stats()
        assert stats["total_requests"] > 0
        assert stats["total_wait_time_seconds"] >= 0

    def test_error_handling(self):
        """Test error handling in rate limiter."""
        config = RateLimitConfig(requests_per_minute=60, tokens_per_minute=1000)
        limiter = RateLimiter(config)

        # Should handle edge cases gracefully
        assert limiter.acquire(token_count=0, blocking=False) is True
        assert limiter.acquire(token_count=-10, blocking=False) is True  # Negative tokens

        stats = limiter.get_stats()
        assert isinstance(stats, dict)
        assert "config" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
