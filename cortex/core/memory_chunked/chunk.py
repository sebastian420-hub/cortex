"""Chunk data structures for memory-efficient file editing."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import hashlib
import time


class ChunkType(Enum):
    """Types of content chunks."""
    
    FILE_CONTENT = "file_content"
    CONVERSATION_SUMMARY = "conversation_summary"
    TOOL_RESULT = "tool_result"
    ERROR_CONTEXT = "error_context"
    SOURCE_CODE = "source_code"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    TEST_CODE = "test_code"


class EditChunk:
    """
    Represents a chunk of content for memory-efficient editing.
    
    Each chunk tracks its content, metadata, and token estimates to enable
    surgical editing without loading entire files into memory.
    
    Attributes:
        chunk_id: Unique identifier for the chunk (SHA256 of content + metadata)
        chunk_type: Type of content in this chunk
        content: The actual text content
        original_length: Length of content when chunk was created (bytes)
        current_length: Current length of content
        token_estimate: Estimated token count (conservative)
        parent_context: Optional reference to parent chunk or file
        metadata: Additional context (line ranges, file info, etc.)
        created_at: Timestamp when chunk was created
        last_modified: Timestamp when chunk was last modified
        hash: Content hash for quick comparison
    """
    
    def __init__(
        self,
        content: str,
        chunk_type: ChunkType,
        parent_context: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.content = content
        self.chunk_type = chunk_type
        self.original_length = len(content)
        self.current_length = self.original_length
        self.parent_context = parent_context
        self.metadata = metadata or {}
        
        # Generate unique ID based on content and metadata
        self.hash = self._compute_hash()
        self.chunk_id = f"{chunk_type.value}_{self.hash[:16]}"
        
        # Token estimation (conservative: 4 chars per token)
        self.token_estimate = max(1, len(content) // 4)
        
        # Timestamps
        self.created_at = time.time()
        self.last_modified = self.created_at
    
    def _compute_hash(self) -> str:
        """Compute SHA256 hash of content + important metadata."""
        hash_input = f"{self.content}{self.chunk_type.value}{self.parent_context or ''}"
        return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
    
    def update_content(self, new_content: str) -> None:
        """Update chunk content and refresh metadata."""
        self.content = new_content
        self.current_length = len(new_content)
        self.token_estimate = max(1, len(new_content) // 4)
        self.last_modified = time.time()
        
        # Recompute hash for changed content
        self.hash = self._compute_hash()
        self.chunk_id = f"{self.chunk_type.value}_{self.hash[:16]}"
    
    def to_message(self) -> Dict[str, Any]:
        """
        Convert chunk to a message format for injection into conversation.
        
        Returns:
            Dictionary with role='system' and formatted chunk content
        """
        sections = [f"[CHUNK: {self.chunk_id} - {self.chunk_type.value}]"]
        
        if self.metadata:
            for key, value in self.metadata.items():
                sections.append(f"{key}: {value}")
        
        sections.append("")
        sections.append(self.content)
        
        return {
            "role": "system",
            "content": "\n".join(sections)
        }
    
    def get_summary(self) -> str:
        """
        Get a brief summary of the chunk for context display.
        
        Returns:
            Short summary string
        """
        if self.metadata.get('file_path'):
            file_info = f"File: {self.metadata['file_path']}"
        else:
            file_info = self.chunk_type.value
        
        return f"{file_info} - {self.token_estimate} tokens - {self.current_length} chars"
    
    def __str__(self) -> str:
        return f"EditChunk(id={self.chunk_id}, type={self.chunk_type.value}, tokens={self.token_estimate})"
    
    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class ChunkCollection:
    """
    A collection of chunks with metadata for bulk operations.
    
    Useful for managing multiple chunks from the same file or conversation.
    """
    
    collection_id: str
    chunks: List[EditChunk] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_chunk(self, chunk: EditChunk) -> None:
        """Add a chunk to the collection."""
        self.chunks.append(chunk)
    
    def get_total_tokens(self) -> int:
        """Get total token count for all chunks in collection."""
        return sum(chunk.token_estimate for chunk in self.chunks)
    
    def get_total_size(self) -> int:
        """Get total size in characters for all chunks."""
        return sum(chunk.current_length for chunk in self.chunks)
    
    def find_chunk_by_id(self, chunk_id: str) -> Optional[EditChunk]:
        """Find a chunk by its ID."""
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None
    
    def find_chunks_by_type(self, chunk_type: ChunkType) -> List[EditChunk]:
        """Find all chunks of a specific type."""
        return [chunk for chunk in self.chunks if chunk.chunk_type == chunk_type]
    
    def to_messages(self) -> List[Dict[str, Any]]:
        """Convert all chunks to message format."""
        return [chunk.to_message() for chunk in self.chunks]


def create_file_chunk(
    content: str,
    file_path: str,
    line_range: Optional[tuple] = None,
    chunk_type: ChunkType = ChunkType.FILE_CONTENT
) -> EditChunk:
    """
    Convenience function to create a file content chunk.
    
    Args:
        content: The file content
        file_path: Path to the file
        line_range: Optional (start_line, end_line) tuple
        chunk_type: Type of chunk (default: FILE_CONTENT)
    
    Returns:
        EditChunk instance
    """
    metadata = {
        "file_path": file_path,
    }
    
    if line_range:
        metadata["line_start"] = line_range[0]
        metadata["line_end"] = line_range[1]
    
    return EditChunk(
        content=content,
        chunk_type=chunk_type,
        parent_context=file_path,
        metadata=metadata
    )


def create_source_code_chunk(
    content: str,
    file_path: str,
    language: str = "python",
    function_name: Optional[str] = None,
    line_range: Optional[tuple] = None
) -> EditChunk:
    """
    Convenience function to create a source code chunk.
    
    Args:
        content: The source code
        file_path: Path to the file
        language: Programming language
        function_name: Optional function/class name
        line_range: Optional (start_line, end_line) tuple
    
    Returns:
        EditChunk instance with SOURCE_CODE type
    """
    metadata = {
        "file_path": file_path,
        "language": language,
    }
    
    if function_name:
        metadata["function"] = function_name
    
    if line_range:
        metadata["line_start"] = line_range[0]
        metadata["line_end"] = line_range[1]
    
    return EditChunk(
        content=content,
        chunk_type=ChunkType.SOURCE_CODE,
        parent_context=file_path,
        metadata=metadata
    )
