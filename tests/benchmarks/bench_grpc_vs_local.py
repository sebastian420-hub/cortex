"""Benchmarks comparing gRPC cache vs local Python cache.

Skips gRPC benchmarks if Go services are not running.
"""

import pytest

from cortex.cache.file_cache import FileCache

try:
    from cortex.services.client import CortexServiceClient, GRPC_AVAILABLE
except ImportError:
    GRPC_AVAILABLE = False


@pytest.fixture
def local_cache():
    return FileCache(max_entries=100, max_size_mb=50.0, enabled=True)


@pytest.fixture
def populated_local_cache(local_cache, benchmark_tmp_dir):
    """Pre-populate local cache with test files."""
    files_dir = benchmark_tmp_dir / "grpc_bench_files"
    files_dir.mkdir(exist_ok=True)

    for i in range(50):
        path = files_dir / f"file_{i}.py"
        content = f"# File {i}\n" + f"x = {i}\n" * 50
        path.write_text(content)
        local_cache.set(str(path), content)

    return local_cache, files_dir


@pytest.mark.performance
class TestLocalCacheBaseline:
    """Baseline benchmarks for local Python cache."""

    def test_local_cache_get_hit(self, benchmark, populated_local_cache):
        """Benchmark: Local cache get (hit)."""
        cache, files_dir = populated_local_cache
        path = str(files_dir / "file_25.py")

        benchmark(cache.get, path)

    def test_local_cache_get_miss(self, benchmark, local_cache):
        """Benchmark: Local cache get (miss)."""
        benchmark(local_cache.get, "/nonexistent/path.py")

    def test_local_cache_set(self, benchmark, local_cache, tmp_path):
        """Benchmark: Local cache set."""
        path = tmp_path / "bench.py"
        content = "x = 1\n" * 100
        path.write_text(content)

        benchmark(local_cache.set, str(path), content)

    def test_local_cache_batch_read(self, benchmark, populated_local_cache):
        """Benchmark: Local cache batch read (10 files)."""
        cache, files_dir = populated_local_cache
        paths = [str(files_dir / f"file_{i}.py") for i in range(10)]

        def batch_read():
            return [cache.get(p) for p in paths]

        benchmark(batch_read)


@pytest.mark.performance
@pytest.mark.skipif(not GRPC_AVAILABLE, reason="grpc not available")
class TestGrpcCacheBenchmarks:
    """Benchmarks for gRPC cache service (requires running Go services)."""

    def test_grpc_cache_get(self, benchmark):
        """Benchmark: gRPC cache get."""
        with CortexServiceClient() as client:
            if not client.is_cache_available():
                pytest.skip("Cache service not running")

            benchmark(client.cache_get, "/test/file.py")

    def test_grpc_cache_set(self, benchmark):
        """Benchmark: gRPC cache set."""
        with CortexServiceClient() as client:
            if not client.is_cache_available():
                pytest.skip("Cache service not running")

            benchmark(client.cache_set, "/test/file.py", "x = 1\n" * 100)

    def test_grpc_cache_batch_get(self, benchmark):
        """Benchmark: gRPC cache batch get (10 files)."""
        with CortexServiceClient() as client:
            if not client.is_cache_available():
                pytest.skip("Cache service not running")

            paths = [f"/test/file_{i}.py" for i in range(10)]
            benchmark(client.cache_batch_get, paths)
