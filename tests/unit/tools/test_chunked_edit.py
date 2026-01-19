"""Tests for ChunkedEditTool."""

import pytest
import tempfile
from pathlib import Path

from cortex.tools.chunked_edit_tool import ChunkedEditTool, EditOperation


class TestChunkedEditTool:
    """Test ChunkedEditTool functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.tool = ChunkedEditTool(project_dir=Path(self.temp_dir))
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_chunked_edit_tool(self):
        """Test creating a ChunkedEditTool."""
        assert self.tool is not None
        assert self.tool.project_dir == Path(self.temp_dir)
        assert hasattr(self.tool, 'chunker')
        assert hasattr(self.tool, 'context_window')
    
    def test_read_file_chunked_small_file(self):
        """Test reading small file (should not chunk)."""
        test_file = Path(self.temp_dir) / "small.txt"
        test_file.write_text("This is a small file.")
        
        result = self.tool.read_file_chunked("small.txt")
        
        assert result["success"] is True
        assert result["data"]["is_chunked"] is False
    
    def test_read_file_chunked_large_file(self):
        """Test reading large file (should chunk)."""
        test_file = Path(self.temp_dir) / "large.txt"
        # Create large content (>10KB)
        content = "line\n" * 5000
        test_file.write_text(content)
        
        result = self.tool.read_file_chunked("large.txt")
        
        assert result["success"] is True
        assert result["data"]["is_chunked"] is True
        assert result["data"]["chunks"] > 0
        assert result["data"]["total_tokens"] > 0
    
    def test_read_file_chunked_python_file(self):
        """Test chunking Python file by function."""
        test_file = Path(self.temp_dir) / "test.py"
        content = """
def func1():
    pass

def func2():
    pass

def func3():
    pass
"""
        test_file.write_text(content)
        
        result = self.tool.read_file_chunked("test.py")
        
        assert result["success"] is True
        # Python file with 3 functions should be chunked
        assert result["data"]["is_chunked"] is True
    
    def test_get_file_chunks(self):
        """Test getting chunks for a file."""
        test_file = Path(self.temp_dir) / "large.txt"
        content = "x" * 15000
        test_file.write_text(content)
        
        # First chunk the file
        self.tool.read_file_chunked("large.txt")
        
        # Now get chunks
        result = self.tool.get_file_chunks("large.txt")
        
        assert result["success"] is True
        assert "chunks" in result["data"]
        assert result["data"]["total_chunks"] > 0
    
    def test_edit_file_standard(self):
        """Test standard file edit (small file)."""
        test_file = Path(self.temp_dir) / "small.txt"
        test_file.write_text("Hello World!")
        
        result = self.tool.execute(
            path="small.txt",
            old_string="World",
            new_string="Universe"
        )
        
        assert result["success"] is True
        assert result["data"]["changes"] == 1
        
        # Verify file was modified
        content = test_file.read_text()
        assert "Universe" in content
        assert "World" not in content
    
    def test_edit_file_chunked(self):
        """Test chunked file edit (large file)."""
        test_file = Path(self.temp_dir) / "large.txt"
        content = "line1\n" * 3000 + "TARGET_TEXT" + "\nline2\n" * 3000
        test_file.write_text(content)
        
        result = self.tool.execute(
            path="large.txt",
            old_string="TARGET_TEXT",
            new_string="REPLACED_TEXT"
        )
        
        assert result["success"] is True
        assert result["data"]["chunks_modified"] == 1
        
        # Verify file was modified
        modified_content = test_file.read_text()
        assert "REPLACED_TEXT" in modified_content
        assert "TARGET_TEXT" not in modified_content
    
    def test_edit_chunk_surgically(self):
        """Test surgical edit on specific chunk."""
        test_file = Path(self.temp_dir) / "large.txt"
        content = "x" * 15000 + "\nTARGET_TEXT" + "\n" + "y" * 15000
        test_file.write_text(content)
        
        # First chunk the file
        result = self.tool.read_file_chunked("large.txt")
        assert result["success"] is True
        
        # Get chunk IDs
        chunk_ids = result["data"]["chunk_ids"]
        assert len(chunk_ids) > 0
        
        # Find chunk containing TARGET_TEXT
        target_chunk_id = None
        for chunk_id in chunk_ids:
            chunk = self.tool.chunk_cache.get(chunk_id)
            if chunk and "TARGET_TEXT" in chunk.content:
                target_chunk_id = chunk_id
                break
        
        assert target_chunk_id is not None
        
        # Edit that specific chunk
        result = self.tool.execute(
            path="large.txt",
            chunk_id=target_chunk_id,
            old_string="TARGET_TEXT",
            new_string="REPLACED_TEXT"
        )
        
        assert result["success"] is True
        assert result["data"]["chunk_id"] == target_chunk_id
        
        # Verify file was modified
        modified_content = test_file.read_text()
        assert "REPLACED_TEXT" in modified_content
    
    def test_edit_not_found(self):
        """Test edit with text not found."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("Hello World!")
        
        result = self.tool.execute(
            path="test.txt",
            old_string="NotFound",
            new_string="Replacement"
        )
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    def test_edit_file_not_found(self):
        """Test edit with non-existent file."""
        result = self.tool.execute(
            path="nonexistent.txt",
            old_string="text",
            new_string="replacement"
        )
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    def test_rollback_last_edit(self):
        """Test rollback functionality."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("original")
        
        # Make an edit
        self.tool.execute(
            path="test.txt",
            old_string="original",
            new_string="modified"
        )
        
        # Rollback
        result = self.tool.rollback_last_edit()
        
        assert result["success"] is True
        assert result["data"]["remaining_operations"] == 0
    
    def test_rollback_no_operations(self):
        """Test rollback with no operations."""
        result = self.tool.rollback_last_edit()
        
        assert result["success"] is False
        assert "no edit operations" in result["error"].lower()
    
    def test_edit_missing_parameters(self):
        """Test edit with missing old_string or new_string."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("content")
        
        # Missing old_string
        result = self.tool.execute(path="test.txt", new_string="new")
        assert result["success"] is False
        
        # Missing new_string
        result = self.tool.execute(path="test.txt", old_string="old")
        assert result["success"] is False
    
    def test_edit_chunk_not_found(self):
        """Test edit with non-existent chunk ID."""
        test_file = Path(self.temp_dir) / "large.txt"
        content = "x" * 15000
        test_file.write_text(content)
        
        # Try to edit non-existent chunk
        result = self.tool.execute(
            path="large.txt",
            chunk_id="nonexistent_chunk_id",
            old_string="text",
            new_string="replacement"
        )
        
        assert result["success"] is False
        assert "chunk not found" in result["error"].lower()


class TestEditOperation:
    """Test EditOperation data structure."""
    
    def test_create_edit_operation(self):
        """Test creating an EditOperation."""
        op = EditOperation(
            chunk_id="test_chunk",
            operation_type="replace",
            old_text="old",
            new_text="new"
        )
        
        assert op.chunk_id == "test_chunk"
        assert op.operation_type == "replace"
        assert op.old_text == "old"
        assert op.new_text == "new"


class TestIntegration:
    """Integration tests for ChunkedEditTool."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.tool = ChunkedEditTool(project_dir=Path(self.temp_dir))
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_workflow_large_python_file(self):
        """Test complete workflow with large Python file."""
        test_file = Path(self.temp_dir) / "module.py"
        
        # Create realistic Python file
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
        
        test_file.write_text(content)
        
        # Step 1: Chunk the file
        result = self.tool.read_file_chunked("module.py")
        assert result["success"] is True
        assert result["data"]["is_chunked"] is True
        
        # Step 2: Get chunks
        chunks_result = self.tool.get_file_chunks("module.py")
        assert chunks_result["success"] is True
        assert chunks_result["data"]["total_chunks"] > 0
        
        # Step 3: Edit a specific chunk (replace "print" with "print_debug")
        chunk_ids = chunks_result["data"]["chunks"]
        target_chunk_id = None
        
        for chunk_info in chunk_ids:
            chunk = self.tool.chunk_cache.get(chunk_info["id"])
            if chunk and "print(result)" in chunk.content:
                target_chunk_id = chunk_info["id"]
                break
        
        assert target_chunk_id is not None
        
        edit_result = self.tool.execute(
            path="module.py",
            chunk_id=target_chunk_id,
            old_string="print(result)",
            new_string="print_debug(result)"
        )
        
        assert edit_result["success"] is True
        
        # Step 4: Verify the change
        modified_content = test_file.read_text()
        assert "print_debug(result)" in modified_content
        assert "print(result)" not in modified_content
    
    def test_context_window_integration(self):
        """Test integration with context window management."""
        test_file = Path(self.temp_dir) / "large_code.py"
        
        # Create large file
        content = "# " + "x" * 10000 + "\n"
        for i in range(5):
            content += f"\ndef func{i}():\n    pass\n"
        test_file.write_text(content)
        
        # Chunk the file
        result = self.tool.read_file_chunked("large_code.py")
        assert result["success"] is True
        
        # Verify context window was created
        context = self.tool.get_chunk_context("large_code.py")
        assert context is not None
        assert len(context.available_chunks) > 0
    
    def test_multiple_edits_same_file(self):
        """Test making multiple edits to the same file."""
        test_file = Path(self.temp_dir) / "multi_edit.txt"
        test_file.write_text("First line\nSecond line\nThird line\n")
        
        # First edit
        result1 = self.tool.execute(
            path="multi_edit.txt",
            old_string="First",
            new_string="Updated First"
        )
        assert result1["success"] is True
        
        # Second edit
        result2 = self.tool.execute(
            path="multi_edit.txt",
            old_string="Second",
            new_string="Updated Second"
        )
        assert result2["success"] is True
        
        # Verify both edits
        content = test_file.read_text()
        assert "Updated First" in content
        assert "Updated Second" in content
        assert "First" not in content or "Updated First" in content
        assert "Second" not in content or "Updated Second" in content
    
    def test_edit_operations_history(self):
        """Test that edit operations are tracked."""
        test_file = Path(self.temp_dir) / "history.txt"
        test_file.write_text("original content")
        
        # Make edits
        self.tool.execute(
            path="history.txt",
            old_string="original",
            new_string="first edit"
        )
        self.tool.execute(
            path="history.txt",
            old_string="content",
            new_string="text"
        )
        
        # Check history
        assert len(self.tool.operation_history) == 2
        assert self.tool.operation_history[0].operation_type == "replace"
        assert self.tool.operation_history[1].operation_type == "replace"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
