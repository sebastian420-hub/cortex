"""Benchmarks for file search operations (grep and glob tools)."""

import pytest
from unittest.mock import MagicMock

from cortex.tools.grep_tool import GrepTool
from cortex.tools.glob_tool import GlobTool


@pytest.fixture
def grep_tool(small_codebase):
    tool = GrepTool(
        project_dir=str(small_codebase),
        permission_mode="auto-approve",
        console=MagicMock(),
    )
    return tool


@pytest.fixture
def glob_tool(small_codebase):
    tool = GlobTool(
        project_dir=str(small_codebase),
        permission_mode="auto-approve",
        console=MagicMock(),
    )
    return tool


@pytest.fixture
def grep_tool_medium(medium_codebase):
    tool = GrepTool(
        project_dir=str(medium_codebase),
        permission_mode="auto-approve",
        console=MagicMock(),
    )
    return tool


@pytest.fixture
def glob_tool_medium(medium_codebase):
    tool = GlobTool(
        project_dir=str(medium_codebase),
        permission_mode="auto-approve",
        console=MagicMock(),
    )
    return tool


@pytest.mark.performance
class TestGrepBenchmarks:
    """Benchmark suite for grep/search operations."""

    def test_grep_simple_pattern_small(self, benchmark, grep_tool, small_codebase):
        """Benchmark: Simple pattern search on 100 files."""
        result = benchmark(
            grep_tool.execute,
            pattern="function",
            path=str(small_codebase),
            output_mode="files_with_matches",
        )
        assert "error" not in result or not result.get("is_error")

    def test_grep_regex_pattern_small(self, benchmark, grep_tool, small_codebase):
        """Benchmark: Regex pattern search on 100 files."""
        result = benchmark(
            grep_tool.execute,
            pattern=r"def \w+\(.*\):",
            path=str(small_codebase),
            output_mode="files_with_matches",
        )
        assert "error" not in result or not result.get("is_error")

    def test_grep_content_mode_small(self, benchmark, grep_tool, small_codebase):
        """Benchmark: Content output mode on 100 files."""
        result = benchmark(
            grep_tool.execute,
            pattern="import",
            path=str(small_codebase),
            output_mode="content",
            head_limit=50,
        )
        assert "error" not in result or not result.get("is_error")

    def test_grep_with_glob_filter(self, benchmark, grep_tool, small_codebase):
        """Benchmark: Search with glob filter on 100 files."""
        result = benchmark(
            grep_tool.execute,
            pattern="class",
            path=str(small_codebase),
            glob="*.py",
            output_mode="files_with_matches",
        )
        assert "error" not in result or not result.get("is_error")

    def test_grep_count_mode(self, benchmark, grep_tool, small_codebase):
        """Benchmark: Count mode on 100 files."""
        result = benchmark(
            grep_tool.execute,
            pattern="Line",
            path=str(small_codebase),
            output_mode="count",
        )
        assert "error" not in result or not result.get("is_error")

    def test_grep_simple_pattern_medium(self, benchmark, grep_tool_medium, medium_codebase):
        """Benchmark: Simple pattern search on 1000 files."""
        result = benchmark(
            grep_tool_medium.execute,
            pattern="function",
            path=str(medium_codebase),
            output_mode="files_with_matches",
        )
        assert "error" not in result or not result.get("is_error")

    def test_grep_regex_pattern_medium(self, benchmark, grep_tool_medium, medium_codebase):
        """Benchmark: Regex pattern search on 1000 files."""
        result = benchmark(
            grep_tool_medium.execute,
            pattern=r"def \w+\(",
            path=str(medium_codebase),
            output_mode="files_with_matches",
        )
        assert "error" not in result or not result.get("is_error")


@pytest.mark.performance
class TestGlobBenchmarks:
    """Benchmark suite for glob/file matching operations."""

    def test_glob_all_python_small(self, benchmark, glob_tool, small_codebase):
        """Benchmark: Glob all Python files in 100-file codebase."""
        result = benchmark(
            glob_tool.execute,
            pattern="**/*.py",
            path=str(small_codebase),
        )
        assert "error" not in result or not result.get("is_error")

    def test_glob_all_files_small(self, benchmark, glob_tool, small_codebase):
        """Benchmark: Glob all files in 100-file codebase."""
        result = benchmark(
            glob_tool.execute,
            pattern="**/*",
            path=str(small_codebase),
        )
        assert "error" not in result or not result.get("is_error")

    def test_glob_specific_dir(self, benchmark, glob_tool, small_codebase):
        """Benchmark: Glob in specific subdirectory."""
        result = benchmark(
            glob_tool.execute,
            pattern="src/**/*.py",
            path=str(small_codebase),
        )
        assert "error" not in result or not result.get("is_error")

    def test_glob_all_python_medium(self, benchmark, glob_tool_medium, medium_codebase):
        """Benchmark: Glob all Python files in 1000-file codebase."""
        result = benchmark(
            glob_tool_medium.execute,
            pattern="**/*.py",
            path=str(medium_codebase),
        )
        assert "error" not in result or not result.get("is_error")

    def test_glob_all_files_medium(self, benchmark, glob_tool_medium, medium_codebase):
        """Benchmark: Glob all files in 1000-file codebase."""
        result = benchmark(
            glob_tool_medium.execute,
            pattern="**/*",
            path=str(medium_codebase),
        )
        assert "error" not in result or not result.get("is_error")
