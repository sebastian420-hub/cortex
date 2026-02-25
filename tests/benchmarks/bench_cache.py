"""Benchmarks for file caching operations."""

import tempfile
from pathlib import Path

import pytest

from cortex.cache.file_cache import FileCache


@pytest.fixture
def cache():
    return FileCache(max_entries=100, max_size_mb=50.0, enabled=True)


@pytest.fixture
def populated_cache(cache, benchmark_tmp_dir):
    """Cache pre-populated with 50 files."""
    files_dir = benchmark_tmp_dir / "cache_bench_files"
    files_dir.mkdir(exist_ok=True)

    for i in range(50):
        path = files_dir / f"file_{i}.py"
        content = f"# File {i}\n" + f"x = {i}\n" * 50
        path.write_text(content)
        cache.set(path, content)

    return cache, files_dir


@pytest.mark.performance
class TestFileCacheBenchmarks:
    """Benchmark suite for file cache operations."""

    def test_cache_set_small_file(self, benchmark, cache, tmp_path):
        """Benchmark: Cache set for a small file (~500 bytes)."""
        path = tmp_path / "small.py"
        content = "x = 1\n" * 10
        path.write_text(content)

        benchmark(cache.set, path, content)

    def test_cache_set_medium_file(self, benchmark, cache, tmp_path):
        """Benchmark: Cache set for a medium file (~5KB)."""
        path = tmp_path / "medium.py"
        content = "x = 1\n" * 1000
        path.write_text(content)

        benchmark(cache.set, path, content)

    def test_cache_get_hit(self, benchmark, populated_cache):
        """Benchmark: Cache get (hit)."""
        cache, files_dir = populated_cache
        path = files_dir / "file_25.py"

        benchmark(cache.get, path)

    def test_cache_get_miss(self, benchmark, cache):
        """Benchmark: Cache get (miss)."""
        benchmark(cache.get, Path("/nonexistent/path.py"))

    def test_cache_invalidate(self, benchmark, populated_cache):
        """Benchmark: Cache invalidation."""
        cache, files_dir = populated_cache
        counter = [0]

        def invalidate():
            path = files_dir / f"file_{counter[0] % 50}.py"
            cache.invalidate(path)
            counter[0] += 1

        benchmark(invalidate)

    def test_cache_eviction_under_pressure(self, benchmark, tmp_path):
        """Benchmark: Cache behavior under eviction pressure (small max_entries)."""
        small_cache = FileCache(max_entries=10, max_size_mb=1.0, enabled=True)
        counter = [0]

        def set_with_eviction():
            idx = counter[0]
            path = tmp_path / f"pressure_{idx}.py"
            content = f"# File {idx}\n" * 20
            path.write_text(content)
            small_cache.set(path, content)
            counter[0] += 1

        benchmark(set_with_eviction)

    def test_cache_stats(self, benchmark, populated_cache):
        """Benchmark: Getting cache statistics."""
        cache, _ = populated_cache

        def get_stats():
            return cache.get_stats()

        benchmark(get_stats)
