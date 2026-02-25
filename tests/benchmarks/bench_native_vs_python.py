"""Side-by-side benchmarks comparing native Rust vs Python implementations.

Skips native benchmarks if the Rust extension is not available.
"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

try:
    from cortex.native import (
        native_search,
        native_parse_code,
        native_count_tokens,
        NATIVE_AVAILABLE,
    )
except ImportError:
    NATIVE_AVAILABLE = False

from cortex.core.context import estimate_tokens


@pytest.mark.performance
class TestSearchComparison:
    """Compare native Rust search vs ripgrep subprocess."""

    @pytest.mark.skipif(not NATIVE_AVAILABLE, reason="Native extension not available")
    def test_native_search(self, benchmark, small_codebase):
        """Benchmark: Native Rust search on 100 files."""
        result = benchmark(
            native_search,
            pattern="function",
            path=str(small_codebase),
            output_mode="files_with_matches",
            head_limit=100,
            offset=0,
        )
        assert result.files_searched > 0

    def test_python_search(self, benchmark, small_codebase):
        """Benchmark: Python ripgrep subprocess on 100 files (baseline)."""
        from cortex.tools.grep_tool import GrepTool

        project_path = Path(small_codebase)
        tool = GrepTool(
            project_dir=project_path,
            permission_mode="auto-approve",
            console=MagicMock(),
        )
        result = benchmark(
            tool.execute,
            pattern="function",
            path=str(project_path),
            output_mode="files_with_matches",
        )
        assert "error" not in result or not result.get("is_error")


@pytest.mark.performance
class TestASTComparison:
    """Compare native Rust AST vs Python tree-sitter."""

    @pytest.mark.skipif(not NATIVE_AVAILABLE, reason="Native extension not available")
    def test_native_ast_parse(self, benchmark, sample_python_code):
        """Benchmark: Native Rust AST parsing."""
        result = benchmark(native_parse_code, sample_python_code, "python")
        assert result.node_count > 0

    def test_python_ast_parse(self, benchmark, sample_python_code):
        """Benchmark: Python tree-sitter AST parsing (baseline)."""
        try:
            from cortex.code_ast.parser import ASTParser, TREE_SITTER_AVAILABLE

            if not TREE_SITTER_AVAILABLE:
                pytest.skip("tree-sitter not available")
            parser = ASTParser()
            if not parser.is_language_supported("python"):
                pytest.skip("Python parser not available")
            benchmark(parser.parse, sample_python_code, "python")
        except ImportError:
            pytest.skip("AST parser not available")


@pytest.mark.performance
class TestTokenizerComparison:
    """Compare native Rust tokenizer vs Python tiktoken."""

    @pytest.mark.skipif(not NATIVE_AVAILABLE, reason="Native extension not available")
    def test_native_token_count_10k(self, benchmark, sample_text_10k):
        """Benchmark: Native Rust token counting (10K chars)."""
        count = benchmark(native_count_tokens, sample_text_10k, "gpt-4")
        assert count > 0

    def test_python_token_count_10k(self, benchmark, sample_text_10k):
        """Benchmark: Python tiktoken token counting (10K chars, baseline)."""
        count = benchmark(estimate_tokens, sample_text_10k, "gpt-4")
        assert count > 0

    @pytest.mark.skipif(not NATIVE_AVAILABLE, reason="Native extension not available")
    def test_native_token_count_100k(self, benchmark, sample_text_100k):
        """Benchmark: Native Rust token counting (100K chars)."""
        count = benchmark(native_count_tokens, sample_text_100k, "gpt-4")
        assert count > 0

    def test_python_token_count_100k(self, benchmark, sample_text_100k):
        """Benchmark: Python tiktoken token counting (100K chars, baseline)."""
        count = benchmark(estimate_tokens, sample_text_100k, "gpt-4")
        assert count > 0
