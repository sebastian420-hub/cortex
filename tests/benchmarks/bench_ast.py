"""Benchmarks for AST parsing operations."""

import pytest


def _get_parser():
    """Try to get ASTParser, skip if tree-sitter not available."""
    try:
        from cortex.code_ast.parser import ASTParser, TREE_SITTER_AVAILABLE

        if not TREE_SITTER_AVAILABLE:
            pytest.skip("tree-sitter not available")
        return ASTParser()
    except ImportError:
        pytest.skip("cortex.code_ast not available")


def _get_ast_cache():
    """Try to get ASTCache."""
    try:
        from cortex.code_ast.cache import ASTCache

        return ASTCache()
    except ImportError:
        pytest.skip("cortex.code_ast.cache not available")


@pytest.mark.performance
class TestASTParsingBenchmarks:
    """Benchmark suite for AST parsing."""

    def test_parse_python_small(self, benchmark, sample_python_code):
        """Benchmark: Parse a small Python file (~80 lines)."""
        parser = _get_parser()
        if not parser.is_language_supported("python"):
            pytest.skip("Python parser not available")

        benchmark(parser.parse, sample_python_code, "python")

    def test_parse_python_medium(self, benchmark, sample_python_code):
        """Benchmark: Parse a medium Python file (~400 lines)."""
        parser = _get_parser()
        if not parser.is_language_supported("python"):
            pytest.skip("Python parser not available")

        # Repeat the code to make it larger
        large_code = sample_python_code * 5
        benchmark(parser.parse, large_code, "python")

    def test_parse_python_large(self, benchmark, sample_python_code):
        """Benchmark: Parse a large Python file (~2000 lines)."""
        parser = _get_parser()
        if not parser.is_language_supported("python"):
            pytest.skip("Python parser not available")

        large_code = sample_python_code * 25
        benchmark(parser.parse, large_code, "python")

    def test_parse_javascript(self, benchmark):
        """Benchmark: Parse a JavaScript file."""
        parser = _get_parser()
        if not parser.is_language_supported("javascript"):
            pytest.skip("JavaScript parser not available")

        js_code = (
            """
function processData(items) {
    const results = [];
    for (const item of items) {
        if (item.type === 'valid') {
            results.push(transform(item));
        }
    }
    return results;
}

class DataManager {
    constructor(config) {
        this.config = config;
        this.cache = new Map();
    }

    async fetchData(url) {
        if (this.cache.has(url)) {
            return this.cache.get(url);
        }
        const response = await fetch(url);
        const data = await response.json();
        this.cache.set(url, data);
        return data;
    }
}

export { processData, DataManager };
"""
            * 10
        )
        benchmark(parser.parse, js_code, "javascript")


@pytest.mark.performance
class TestASTCacheBenchmarks:
    """Benchmark suite for AST caching."""

    def test_cache_hit(self, benchmark, sample_python_code):
        """Benchmark: AST cache hit (same content)."""
        cache = _get_ast_cache()
        parser = _get_parser()

        if not parser.is_language_supported("python"):
            pytest.skip("Python parser not available")

        tree = parser.parse(sample_python_code, "python")
        cache.put("test_file.py", sample_python_code, tree)

        def cache_get():
            return cache.get("test_file.py", sample_python_code)

        benchmark(cache_get)

    def test_cache_miss(self, benchmark, sample_python_code):
        """Benchmark: AST cache miss (different content)."""
        cache = _get_ast_cache()

        counter = [0]

        def cache_miss():
            counter[0] += 1
            return cache.get(f"nonexistent_{counter[0]}.py", sample_python_code)

        benchmark(cache_miss)
