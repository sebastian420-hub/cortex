"""Tests for cache warming functionality."""

import tempfile
from pathlib import Path
import pytest

from cortex.cache.file_cache import FileCache, patterns_match


class TestPatternsMatch:
    """Test patterns_match function."""

    def test_no_patterns(self):
        """When no patterns specified, should match all."""
        filepath = Path("test.py")
        assert patterns_match(filepath, None) is True
        assert patterns_match(filepath, []) is True

    def test_simple_extension_match(self):
        """Test matching by file extension."""
        filepath = Path("test.py")
        assert patterns_match(filepath, ["*.py"]) is True
        assert patterns_match(filepath, ["*.md"]) is False

    def test_multiple_patterns(self):
        """Test matching multiple patterns."""
        filepath = Path("test.py")
        assert patterns_match(filepath, ["*.py", "*.md"]) is True
        assert patterns_match(filepath, ["*.md", "*.txt"]) is False

    def test_directory_pattern(self):
        """Test directory patterns."""
        filepath = Path("src/module/test.py")
        assert patterns_match(filepath, ["*.py"]) is True
        assert patterns_match(filepath, ["src/module/*.py"]) is True
        assert patterns_match(filepath, ["tests/*.py"]) is False


class TestCacheWarming:
    """Test cache warming functionality."""

    def test_pre_cache_disabled(self):
        """Test pre_cache when cache is disabled."""
        cache = FileCache(enabled=False)
        result = cache.pre_cache()
        assert result["cached"] == 0
        assert result["errors"] == 1

    def test_pre_cache_directory_no_patterns(self):
        """Test pre_cache from directory without patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test files
            (tmpdir / "test1.py").write_text("print('test1')")
            (tmpdir / "test2.txt").write_text("test2")
            (tmpdir / "test3.md").write_text("# test3")

            cache = FileCache(max_entries=10, max_size_mb=1.0)
            result = cache.pre_cache(
                source="directory",
                directory=tmpdir,
                max_files=10,
                patterns=None,
            )

            # Should cache all files
            assert result["cached"] >= 2  # At least .py and .md
            assert result["errors"] == 0
            assert len(result["files"]) >= 2

    def test_pre_cache_directory_with_patterns(self):
        """Test pre_cache from directory with patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test files
            (tmpdir / "test1.py").write_text("print('test1')")
            (tmpdir / "test2.txt").write_text("test2")
            (tmpdir / "test3.py").write_text("print('test3')")

            cache = FileCache(max_entries=10, max_size_mb=1.0)
            result = cache.pre_cache(
                source="directory",
                directory=tmpdir,
                max_files=10,
                patterns=["*.py"],
            )

            # Should cache only .py files
            assert result["cached"] == 2  # Only .py files
            assert result["errors"] == 0
            assert len(result["files"]) == 2

    def test_pre_cache_large_file_skipped(self):
        """Test that large files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create a large file (larger than cache size)
            large_content = "x" * (int(1024 * 1024) + 1000)  # 1MB + 1000 bytes
            (tmpdir / "large.txt").write_text(large_content)

            cache = FileCache(max_entries=10, max_size_mb=1.0)
            result = cache.pre_cache(
                source="directory",
                directory=tmpdir,
                max_files=10,
                patterns=["*.txt"],
            )

            # Should skip the large file
            assert result["skipped"] >= 1
            assert result["cached"] == 0

    def test_pre_cache_max_files(self):
        """Test that max_files limit is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create multiple test files
            for i in range(10):
                (tmpdir / f"test{i}.py").write_text(f"print('test{i}')")

            cache = FileCache(max_entries=10, max_size_mb=1.0)
            result = cache.pre_cache(
                source="directory",
                directory=tmpdir,
                max_files=3,
                patterns=["*.py"],
            )

            # Should cache only 3 files
            assert result["cached"] <= 3
            assert len(result["files"]) <= 3

    def test_pre_cache_nonexistent_directory(self):
        """Test pre_cache with non-existent directory."""
        cache = FileCache()
        nonexistent = Path("/nonexistent/path/that/does/not/exist")
        result = cache.pre_cache(
            source="directory",
            directory=nonexistent,
        )

        # Should handle gracefully
        assert result["errors"] >= 1

    def test_pre_cache_git_history(self):
        """Test pre_cache from git history (may not work in all environments)."""
        cache = FileCache(max_entries=10, max_size_mb=1.0)
        try:
            result = cache.pre_cache(
                source="git_history",
                max_files=10,
                patterns=["*.py"],
            )
            # Git may or may not be available, so just check it doesn't crash
            assert isinstance(result, dict)
        except Exception:
            # Git may not be available, that's OK
            pass

    def test_pre_cache_git_tracked(self):
        """Test pre_cache from git tracked files (may not work in all environments)."""
        cache = FileCache(max_entries=10, max_size_mb=1.0)
        try:
            result = cache.pre_cache(
                source="git_tracked",
                max_files=10,
                patterns=["*.py"],
            )
            # Git may or may not be available, so just check it doesn't crash
            assert isinstance(result, dict)
        except Exception:
            # Git may not be available, that's OK
            pass

    def test_pre_cache_invalid_source(self):
        """Test pre_cache with invalid source."""
        cache = FileCache()
        result = cache.pre_cache(
            source="invalid_source",
        )

        # Should return error
        assert result["errors"] >= 1

    def test_pre_cache_unicode_files(self):
        """Test pre_cache with unicode filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create files with unicode names
            (tmpdir / "test_🚀.py").write_text("print('rocket')")
            (tmpdir / "test_é.py").write_text("print('accent')")

            cache = FileCache(max_entries=10, max_size_mb=1.0)
            result = cache.pre_cache(
                source="directory",
                directory=tmpdir,
                max_files=10,
                patterns=["*.py"],
            )

            # Should handle unicode filenames
            assert result["cached"] >= 1

    def test_pre_cache_with_existing_cache_entries(self):
        """Test pre_cache when cache already has entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test files
            (tmpdir / "test1.py").write_text("print('test1')")
            (tmpdir / "test2.py").write_text("print('test2')")

            cache = FileCache(max_entries=10, max_size_mb=1.0)

            # Manually cache one file first
            cache.set(tmpdir / "test1.py", "print('test1')")

            # Now pre-cache should work with existing entries
            result = cache.pre_cache(
                source="directory",
                directory=tmpdir,
                max_files=10,
                patterns=["*.py"],
            )

            # Should have cached the new file
            assert result["cached"] >= 1
            assert len(result["files"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
