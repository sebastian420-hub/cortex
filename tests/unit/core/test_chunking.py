"""Tests for chunked editing system."""

import pytest
from pathlib import Path
import tempfile
import os

from cortex.core.memory_chunked.chunk import EditChunk, ChunkType, create_file_chunk, create_source_code_chunk  # noqa: E501
from cortex.core.memory_chunked.chunking import (
    FileChunker,
    ChunkingStrategy,
    chunk_file_by_function,
    chunk_file_by_size,
    should_chunk_file,
)


class TestEditChunk:
    """Test EditChunk data structure."""

    def test_create_edit_chunk(self):
        """Test creating an EditChunk."""
        content = "def hello():\n    print('Hello, World!')"
        chunk = EditChunk(
            content=content,
            chunk_type=ChunkType.SOURCE_CODE,
            parent_context="test.py",
            metadata={"line_start": 1, "line_end": 3}
        )

        assert chunk.content == content
        assert chunk.chunk_type == ChunkType.SOURCE_CODE
        assert chunk.parent_context == "test.py"
        assert chunk.token_estimate > 0
        assert len(chunk.chunk_id) > 0
        assert chunk.metadata["line_start"] == 1

    def test_update_chunk_content(self):
        """Test updating chunk content."""
        chunk = EditChunk(
            content="original",
            chunk_type=ChunkType.FILE_CONTENT
        )
        original_hash = chunk.hash

        chunk.update_content("updated")

        assert chunk.content == "updated"
        assert chunk.current_length == len("updated")
        assert chunk.hash != original_hash

    def test_chunk_to_message(self):
        """Test converting chunk to message format."""
        chunk = EditChunk(
            content="test content",
            chunk_type=ChunkType.FILE_CONTENT,
            metadata={"file_path": "test.txt"}
        )

        message = chunk.to_message()

        assert message["role"] == "system"
        assert chunk.chunk_id in message["content"]
        assert "test content" in message["content"]

    def test_chunk_summary(self):
        """Test getting chunk summary."""
        chunk = EditChunk(
            content="x" * 1000,
            chunk_type=ChunkType.FILE_CONTENT,
            metadata={"file_path": "large_file.txt"}
        )

        summary = chunk.get_summary()

        assert "large_file.txt" in summary
        assert "tokens" in summary


class TestFileChunker:
    """Test FileChunker utility."""

    def test_chunk_fixed_size(self):
        """Test fixed-size chunking."""
        content = "line1\nline2\nline3\n" * 100  # ~1500 chars
        chunker = FileChunker(
            max_chunk_size=500,
            strategy=ChunkingStrategy.FIXED_SIZE
        )

        chunks = chunker.chunk_file(content, "test.txt")

        assert len(chunks) > 1
        assert all(isinstance(c, EditChunk) for c in chunks)

    def test_chunk_python_by_function(self):
        """Test Python function-based chunking."""
        content = """
def func1():
    pass

def func2():
    pass

class MyClass:
    def method(self):
        pass
"""
        chunker = FileChunker(strategy=ChunkingStrategy.FUNCTION_BASED)
        chunks = chunker.chunk_file(content, "test.py")

        assert len(chunks) >= 3
        assert all(c.chunk_type == ChunkType.SOURCE_CODE for c in chunks)

    def test_chunk_smart(self):
        """Test smart chunking."""
        # Large content
        content = "x" * 15000
        chunker = FileChunker(strategy=ChunkingStrategy.SMART)

        chunks = chunker.chunk_file(content, "large.txt")

        assert len(chunks) > 1

    def test_chunk_small_file(self):
        """Test chunking small file (should return single chunk)."""
        content = "small file content"
        chunker = FileChunker(strategy=ChunkingStrategy.SMART)

        chunks = chunker.chunk_file(content, "small.txt")

        assert len(chunks) == 1


class TestChunkingFunctions:
    """Test convenience chunking functions."""

    def test_chunk_file_by_function(self):
        """Test chunk_file_by_function."""
        content = """
def hello():
    print("Hello")

def goodbye():
    print("Goodbye")
"""
        chunks = chunk_file_by_function(content, "test.py")

        assert len(chunks) >= 2
        assert all(isinstance(c, EditChunk) for c in chunks)

    def test_chunk_file_by_size(self):
        """Test chunk_file_by_size."""
        content = "x" * 5000
        chunks = chunk_file_by_size(content, "large.txt", max_size=1000)

        assert len(chunks) >= 5

    def test_should_chunk_file(self):
        """Test should_chunk_file decision logic."""
        # Large file should be chunked
        large_content = "x" * 15000
        assert should_chunk_file(large_content, "large.txt")

        # Small file should not be chunked
        small_content = "small"
        assert not should_chunk_file(small_content, "small.txt")

        # Python file with multiple functions should be chunked
        python_content = """
def func1(): pass
def func2(): pass
def func3(): pass
def func4(): pass
"""
        assert should_chunk_file(python_content, "test.py")


class TestFactoryFunctions:
    """Test factory functions for creating chunks."""

    def test_create_file_chunk(self):
        """Test create_file_chunk convenience function."""
        chunk = create_file_chunk(
            content="test content",
            file_path="test.txt",
            line_range=(1, 5)
        )

        assert chunk.chunk_type == ChunkType.FILE_CONTENT
        assert chunk.metadata["file_path"] == "test.txt"
        assert chunk.metadata["line_start"] == 1
        assert chunk.metadata["line_end"] == 5

    def test_create_source_code_chunk(self):
        """Test create_source_code_chunk convenience function."""
        chunk = create_source_code_chunk(
            content="def test(): pass",
            file_path="test.py",
            language="python",
            function_name="test",
            line_range=(1, 1)
        )

        assert chunk.chunk_type == ChunkType.SOURCE_CODE
        assert chunk.metadata["function"] == "test"
        assert chunk.metadata["language"] == "python"


class TestIntegration:
    """Integration tests for chunking system."""

    def test_chunk_large_python_file(self):
        """Test chunking a realistic Python file."""
        content = """
import os
import sys
from typing import List, Dict

def process_data(data: List[str]) -> Dict[str, int]:
    '''Process data and return counts.'''
    result = {}
    for item in data:
        result[item] = result.get(item, 0) + 1
    return result

def main():
    data = ["a", "b", "a", "c", "b", "a"]
    result = process_data(data)
    print(result)
    return result

class DataProcessor:
    def __init__(self):
        self.data = []

    def add(self, item):
        self.data.append(item)

    def process(self):
        return process_data(self.data)

if __name__ == "__main__":
    main()
"""

        chunker = FileChunker(strategy=ChunkingStrategy.FUNCTION_BASED)
        chunks = chunker.chunk_file(content, "realistic.py")

        assert len(chunks) >= 3  # At least process_data, main, DataProcessor
        assert any("process_data" in str(c.metadata.get("function", "")) for c in chunks)
        assert any("main" in str(c.metadata.get("function", "")) for c in chunks)

    def test_chunk_mixed_content(self):
        """Test chunking mixed text and code."""
        content = """
# Documentation
This is a markdown file with code:

```python
def example():
    pass
```

Some more text here.
"""
        chunker = FileChunker(strategy=ChunkingStrategy.SMART)
        chunks = chunker.chunk_file(content, "mixed.md")

        assert len(chunks) > 0
        assert all(isinstance(c, EditChunk) for c in chunks)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
