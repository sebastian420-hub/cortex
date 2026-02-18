"""Tests for context window management."""

import pytest
from typing import List, Dict, Any

from cortex.core.memory_chunked.chunk import EditChunk, ChunkType
from cortex.core.memory_chunked.context_window import (
    ContextWindowManager,
    TokenBudget,
    ContextInjectionStrategy,
    create_context_window_from_file,
    estimate_context_usage,
)


class TestTokenBudget:
    """Test TokenBudget data structure."""
    
    def test_create_token_budget(self):
        """Test creating a token budget."""
        budget = TokenBudget(total_tokens=1000)
        
        assert budget.total_tokens == 1000
        assert budget.used_tokens == 0
        assert budget.get_remaining() == 1000

    def test_allocate_tokens(self):
        """Test token allocation."""
        budget = TokenBudget(total_tokens=1000)

        # Successful allocation
        assert budget.allocate(500, "read") is True        
        assert budget.used_tokens == 500

        # Allocation beyond limit
        assert budget.allocate(600, "read") is False       
        assert budget.used_tokens == 500  # Unchanged      

    def test_release_tokens(self):
        """Test token release."""
        budget = TokenBudget(total_tokens=1000)
        budget.allocate(500)

        budget.release(200)
        assert budget.used_tokens == 300

    def test_operation_specific_limits(self):
        """Test operation-specific token limits."""        
        budget = TokenBudget(total_tokens=20000)

        # Read operation has 10k limit
        assert budget.allocate(8000, "read") is True       

        # Edit operation has 5k limit - should fail because 8000 + 3000 = 11000 > 5000
        assert budget.allocate(3000, "edit") is False      

    def test_get_utilization(self):
        """Test utilization calculation."""
        budget = TokenBudget(total_tokens=1000)
        budget.allocate(500)

        assert budget.get_utilization() == 50.0


class TestContextWindowManager:
    """Test ContextWindowManager."""

    def test_create_context_window(self):
        """Test creating a context window manager."""      
        context = ContextWindowManager(model="test-model", max_tokens=50000)

        assert context.max_tokens == 50000
        assert len(context.active_chunks) == 0
        assert len(context.available_chunks) == 0

    def test_add_chunk(self):
        """Test adding a chunk."""
        context = ContextWindowManager(model="test-model", max_tokens=1000)
        chunk = EditChunk(
            content="test content",
            chunk_type=ChunkType.FILE_CONTENT
        )

        context.add_chunk(chunk)

        assert len(context.available_chunks) == 1
        assert context.available_chunks[0] == chunk        

    def test_add_chunks(self):
        """Test adding multiple chunks."""
        context = ContextWindowManager(model="test-model", max_tokens=1000)
        chunks = [
            EditChunk(content=f"chunk {i}", chunk_type=ChunkType.FILE_CONTENT)
            for i in range(5)
        ]

        context.add_chunks(chunks)

        assert len(context.available_chunks) == 5

    def test_inject_context_all(self):
        """Test context injection with ALL strategy."""    
        context = ContextWindowManager(
            model="test-model",
            max_tokens=1000,
            injection_strategy=ContextInjectionStrategy.ALL
        )

        chunks = [
            EditChunk(content="chunk 1", chunk_type=ChunkType.FILE_CONTENT),
            EditChunk(content="chunk 2", chunk_type=ChunkType.FILE_CONTENT),
        ]
        context.add_chunks(chunks)

        messages: List[Dict[str, Any]] = [{"role": "user", "content": "test"}]
        updated, info = context.inject_context(messages, task="test")

        assert len(updated) == 3  # Original + 2 chunks    
        assert info["injected"] == 2
        assert info["tokens_injected"] > 0
        assert len(context.active_chunks) == 2

    def test_inject_context_relevant(self):
        """Test context injection with RELEVANT strategy."""
        context = ContextWindowManager(
            model="test-model",
            max_tokens=1000,
            injection_strategy=ContextInjectionStrategy.RELEVANT
        )

        # Create chunks with different relevance
        chunk1 = EditChunk(
            content="python code for processing",
            chunk_type=ChunkType.SOURCE_CODE,
            metadata={"file_path": "process.py", "function": "process_data"}
        )
        chunk2 = EditChunk(
            content="unrelated content",
            chunk_type=ChunkType.FILE_CONTENT,
            metadata={"file_path": "other.txt"}
        )

        context.add_chunks([chunk1, chunk2])

        messages: List[Dict[str, Any]] = [{"role": "user", "content": "test"}]
        updated, info = context.inject_context(messages, task="process data in python")

        # Should inject the relevant chunk first
        assert info["injected"] >= 1
        assert len(context.active_chunks) >= 1

    def test_inject_context_budget_limit(self):
        """Test budget enforcement during injection."""    
        context = ContextWindowManager(
            model="test-model",
            max_tokens=100,
            injection_strategy=ContextInjectionStrategy.ALL,
            budget_per_operation=True
        )

        # Create large chunks that exceed budget
        large_chunk = EditChunk(
            content="x" * 1000,  # ~250 tokens
            chunk_type=ChunkType.FILE_CONTENT
        )
        context.add_chunk(large_chunk)

        messages: List[Dict[str, Any]] = [{"role": "user", "content": "test"}]
        updated, info = context.inject_context(messages, task="test")

        # Should respect budget
        assert info["budget_remaining"] >= 0
        assert len(context.active_chunks) <= 1

    def test_clear_active_context(self):
        """Test clearing active context."""
        context = ContextWindowManager(model="test-model", max_tokens=1000)    

        chunks = [
            EditChunk(content=f"chunk {i}", chunk_type=ChunkType.FILE_CONTENT)
            for i in range(3)
        ]
        context.add_chunks(chunks)

        # Inject chunks
        messages: List[Dict[str, Any]] = [{"role": "user", "content": "test"}]
        context.inject_context(messages)

        assert len(context.active_chunks) == 3

        # Clear context
        context.clear_active_context()

        assert len(context.active_chunks) == 0
        assert context.token_budget.used_tokens == 0       

    def test_get_chunk_by_id(self):
        """Test retrieving chunk by ID."""
        context = ContextWindowManager(model="test-model", max_tokens=1000)    

        chunk = EditChunk(
            content="test",
            chunk_type=ChunkType.FILE_CONTENT
        )
        context.add_chunk(chunk)

        retrieved = context.get_chunk_by_id(chunk.chunk_id)

        assert retrieved is not None
        assert retrieved.chunk_id == chunk.chunk_id        

    def test_visualize(self):
        """Test context window visualization."""
        context = ContextWindowManager(model="test-model", max_tokens=1000)    

        chunk = EditChunk(content="x" * 1000, chunk_type=ChunkType.FILE_CONTENT)
        context.add_chunk(chunk)

        messages: List[Dict[str, Any]] = [{"role": "user", "content": "test"}]
        context.inject_context(messages)

        viz = context.visualize()

        assert "Context Window Status" in viz
        assert "tokens" in viz.lower()
        assert "chunks" in viz.lower()

    def test_get_stats(self):
        """Test getting context statistics."""
        context = ContextWindowManager(model="test-model", max_tokens=1000)    

        chunk = EditChunk(content="test", chunk_type=ChunkType.FILE_CONTENT)
        context.add_chunk(chunk)

        messages: List[Dict[str, Any]] = [{"role": "user", "content": "test"}]
        context.inject_context(messages)

        stats = context.get_stats()

        assert stats["max_tokens"] == 1000
        assert stats["active_chunks"] >= 1
        assert stats["available_chunks"] == 1
        assert "utilization" in stats


class TestContextWindowFunctions:
    """Test context window convenience functions."""       

    def test_create_context_window_from_file(self):        
        """Test creating context window from file."""      
        content = "def test():\n    pass\n" * 100  # Large content

        context = create_context_window_from_file(
            content=content,
            file_path="test.py",
            model="test-model",
            max_tokens=5000
        )

        assert context.max_tokens == 5000
        assert len(context.available_chunks) > 0

    def test_estimate_context_usage(self):
        """Test context usage estimation."""
        context = ContextWindowManager(model="test-model", max_tokens=10000)

        chunk = EditChunk(content="x" * 1000, chunk_type=ChunkType.FILE_CONTENT)
        context.add_chunk(chunk)

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": "test message"}    
        ]
        context.inject_context(messages)

        usage = estimate_context_usage(context, messages)  

        assert "message_tokens" in usage
        assert "chunk_tokens" in usage
        assert "total_tokens" in usage
        assert "utilization" in usage


class TestIntegration:
    """Integration tests for context window system."""     

    def test_full_workflow(self):
        """Test complete workflow with chunking and injection."""
        # Create context window
        context = ContextWindowManager(
            model="test-model",
            max_tokens=10000,
            injection_strategy=ContextInjectionStrategy.SMART
        )

        # Add multiple chunks with varying relevance       
        chunks = [
            EditChunk(
                content="python processing functions",     
                chunk_type=ChunkType.SOURCE_CODE,
                metadata={"file_path": "process.py", "function": "process_data"}
            ),
            EditChunk(
                content="configuration settings",
                chunk_type=ChunkType.CONFIGURATION,        
                metadata={"file_path": "config.yaml"}      
            ),
            EditChunk(
                content="test documentation",
                chunk_type=ChunkType.DOCUMENTATION,        
                metadata={"file_path": "README.md"}        
            ),
        ]
        context.add_chunks(chunks)

        # Inject context for specific task
        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": "Help me process data"}
        ]
        updated, info = context.inject_context(
            messages,
            task="process data using python"
        )

        # Verify injection
        assert len(updated) > len(messages)
        assert info["injected"] > 0
        assert info["tokens_injected"] > 0

        # Verify visualization works
        viz = context.visualize(detailed=True)
        assert isinstance(viz, str)
        assert len(viz) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])