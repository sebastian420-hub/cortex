"""End-to-end workflow benchmarks simulating real Cortex usage patterns."""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from cortex.tools.grep_tool import GrepTool
from cortex.tools.glob_tool import GlobTool
from cortex.core.context import estimate_tokens, truncate_history
from cortex.cache.file_cache import FileCache


@pytest.fixture
def tools(small_codebase):
    console = MagicMock()
    # Ensure project_dir is a Path object
    project_path = Path(small_codebase)
    grep = GrepTool(
        project_dir=project_path,
        permission_mode="auto-approve",
        console=console,
    )
    glob = GlobTool(
        project_dir=project_path,
        permission_mode="auto-approve",
        console=console,
    )
    return grep, glob


@pytest.fixture
def cache():
    return FileCache(max_entries=100, max_size_mb=50.0, enabled=True)


@pytest.mark.performance
class TestE2EWorkflowBenchmarks:
    """Benchmark suite for end-to-end workflows."""

    def test_workflow_code_search(self, benchmark, tools, small_codebase):
        """Benchmark: Code search workflow (glob → grep → read → count tokens).

        Simulates: User asks "find all functions that take two arguments"
        """
        grep, glob = tools
        project_path = Path(small_codebase)

        def code_search_workflow():
            # Step 1: Find Python files
            files_result = glob.execute(pattern="**/*.py", path=str(project_path))

            # Step 2: Search for pattern
            search_result = grep.execute(
                pattern=r"def \w+\(arg1, arg2\)",
                path=str(project_path),
                glob="*.py",
                output_mode="content",
                head_limit=20,
            )

            # Step 3: Count tokens in result
            result_text = str(search_result)
            tokens = estimate_tokens(result_text)

            return tokens

        benchmark(code_search_workflow)

    def test_workflow_file_analysis(self, benchmark, tools, small_codebase):
        """Benchmark: File analysis workflow (glob → read files → count tokens).

        Simulates: User asks "analyze the source files in src/"
        """
        _, glob = tools
        project_path = Path(small_codebase)

        def file_analysis_workflow():
            # Step 1: Find files
            files_result = glob.execute(
                pattern="src/**/*", path=str(project_path), max_results=20
            )

            # Step 2: Read a few files and count tokens
            total_tokens = 0
            src_dir = project_path / "src"
            if src_dir.exists():
                for f in list(src_dir.iterdir())[:10]:
                    if f.is_file():
                        content = f.read_text(errors="ignore")
                        total_tokens += estimate_tokens(content)

            return total_tokens

        benchmark(file_analysis_workflow)

    def test_workflow_cached_reads(self, benchmark, cache, small_codebase):
        """Benchmark: Cached file reading workflow.

        Simulates: Reading the same files repeatedly (cache hit scenario)
        """
        project_path = Path(small_codebase)
        # Pre-populate cache
        files = list((project_path / "src").iterdir())[:20]
        for f in files:
            if f.is_file():
                content = f.read_text(errors="ignore")
                cache.set(f, content)

        def cached_read_workflow():
            total_tokens = 0
            for f in files[:10]:
                if f.is_file():
                    content = cache.get(f)
                    if content:
                        total_tokens += estimate_tokens(content)
            return total_tokens

        benchmark(cached_read_workflow)

    def test_workflow_context_management(self, benchmark, sample_conversation):
        """Benchmark: Context management workflow (count → truncate → recount).

        Simulates: Managing context window during a long conversation
        """

        def context_management_workflow():
            # Step 1: Count total conversation tokens
            total = sum(estimate_tokens(str(msg)) for msg in sample_conversation)

            # Step 2: Truncate if needed
            truncated = truncate_history(
                sample_conversation,
                max_tokens=5000,
                keep_recent=10,
                model="gpt-4",
            )

            # Step 3: Recount after truncation
            new_total = sum(estimate_tokens(str(msg)) for msg in truncated)

            return total, new_total

        benchmark(context_management_workflow)

    def test_workflow_multi_search(self, benchmark, tools, small_codebase):
        """Benchmark: Multi-pattern search workflow.

        Simulates: User asks "find all classes and their methods"
        """
        grep, _ = tools
        project_path = Path(small_codebase)

        def multi_search_workflow():
            # Search for classes
            classes = grep.execute(
                pattern=r"class \w+",
                path=str(project_path),
                glob="*.py",
                output_mode="content",
                head_limit=20,
            )

            # Search for methods
            methods = grep.execute(
                pattern=r"def \w+\(self",
                path=str(project_path),
                glob="*.py",
                output_mode="content",
                head_limit=20,
            )

            return len(str(classes)), len(str(methods))

        benchmark(multi_search_workflow)
