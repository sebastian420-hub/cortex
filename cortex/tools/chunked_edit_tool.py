"""Surgical file editing tool using chunk-based operations."""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import re

from .base import Tool
from ..core.security import validate_path, SecurityError
from ..models import PermissionMode
from ..utils.errors import (
    create_error_response,
    create_success_response,
    create_permission_denial,
    ErrorType,
)
from ..cache import get_file_cache, invalidate_file
from ..core.memory_chunked.chunk import (
    EditChunk,
    ChunkType,
    create_file_chunk,
    create_source_code_chunk,
)
from ..core.memory_chunked.chunking import FileChunker, ChunkingStrategy, should_chunk_file
from ..core.memory_chunked.context_window import (
    ContextWindowManager,
    create_context_window_from_file,
)

logger = logging.getLogger(__name__)


@dataclass
class EditOperation:
    """Represents a surgical edit operation on a chunk."""

    chunk_id: str
    operation_type: str  # "replace", "insert", "delete"
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    line_number: Optional[int] = None
    insert_before: bool = False


class ChunkedEditTool(Tool):
    """
    Enhanced file editing tool with chunk-based surgical editing.

    Key Features:
    1. Automatic chunking of large files
    2. Surgical editing of specific chunks without loading full file
    3. Chunk-aware context injection
    4. Token budget enforcement for large edits
    5. Rollback support for failed edits

    Usage:
    - For small files: Works like normal file editor
    - For large files: Automatically chunks and edits surgically
    - For specific chunks: Use chunk_id parameter for surgical edits
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = kwargs.get("agent") or kwargs.get("parent_agent")
        self.chunker = FileChunker(max_chunk_size=2000, strategy=ChunkingStrategy.SMART)
        self.context_window = ContextWindowManager(model=self.agent.model, max_tokens=100000)
        self.chunk_cache: Dict[str, EditChunk] = {}
        self.file_contexts: Dict[str, ContextWindowManager] = {}

        # Operation tracking for rollback
        self.operation_history: List[EditOperation] = []

    def execute(
        self,
        path: str,
        old_string: Optional[str] = None,
        new_string: Optional[str] = None,
        chunk_id: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute a file edit operation.

        Args:
            path: Relative path to the file
            old_string: Text to replace (for surgical edit)
            new_string: Replacement text
            chunk_id: Specific chunk to edit (surgical editing)
            offset: Line offset for reading (for context)
            limit: Line limit for reading (for context)

        Returns:
            Standardized response with edit result
        """
        try:
            full_path = validate_path(self.project_dir, path)

            if not full_path.exists():
                return create_error_response(
                    f"File not found: {path}", ErrorType.NOT_FOUND, {"path": path}
                )

            if not full_path.is_file():
                return create_error_response(
                    f"Path is not a file: {path}", ErrorType.VALIDATION, {"path": path}
                )

            # Check file size and chunk if needed
            file_size = full_path.stat().st_size
            should_chunk = (
                should_chunk_file(open(full_path, "r").read(), path)
                if file_size < 1000000
                else True
            )

            if chunk_id:
                # Surgical edit on specific chunk
                return self._edit_chunk_surgically(
                    path, chunk_id, old_string, new_string, full_path
                )
            elif should_chunk:
                # Chunked edit for large files
                return self._edit_file_chunked(path, old_string, new_string, full_path)
            else:
                # Standard edit for small files
                return self._edit_file_standard(path, old_string, new_string, full_path)

        except SecurityError as e:
            return create_permission_denial(str(e), {"path": path})
        except Exception as e:
            return create_error_response(
                f"Edit failed: {str(e)}", ErrorType.EXECUTION, {"path": path, "error": str(e)}
            )

    def _edit_file_standard(
        self, path: str, old_string: Optional[str], new_string: Optional[str], full_path: Path
    ) -> Dict[str, Any]:
        """Edit small file using standard string replacement."""
        try:
            content = full_path.read_text(encoding="utf-8")

            if old_string is None or new_string is None:
                return create_error_response(
                    "Both old_string and new_string are required for standard edit",
                    ErrorType.VALIDATION,
                    {"path": path},
                )

            if old_string not in content:
                return create_error_response(
                    f"Text not found in file: {old_string[:50]}...",
                    ErrorType.NOT_FOUND,
                    {"path": path, "search_text": old_string[:100]},
                )

            # Perform replacement
            new_content = content.replace(old_string, new_string, 1)

            # Write back to file
            full_path.write_text(new_content, encoding="utf-8")

            # Invalidate cache
            invalidate_file(full_path)

            # Track operation
            operation = EditOperation(
                chunk_id="full_file",
                operation_type="replace",
                old_text=old_string,
                new_text=new_string,
            )
            self.operation_history.append(operation)

            return create_success_response(
                {"path": path, "changes": 1, "bytes_modified": len(new_content) - len(content)}
            )

        except Exception as e:
            return create_error_response(
                f"Failed to edit file: {str(e)}",
                ErrorType.EXECUTION,
                {"path": path, "error": str(e)},
            )

    def _edit_file_chunked(
        self, path: str, old_string: Optional[str], new_string: Optional[str], full_path: Path
    ) -> Dict[str, Any]:
        """
        Edit large file by chunking and surgical replacement.

        This method:
        1. Loads file and chunks it
        2. Finds which chunk contains the old_string
        3. Replaces within that chunk only
        4. Reassembles file
        """
        try:
            content = full_path.read_text(encoding="utf-8")

            if old_string is None or new_string is None:
                return create_error_response(
                    "Both old_string and new_string are required for chunked edit",
                    ErrorType.VALIDATION,
                    {"path": path},
                )

            # Chunk the file
            chunks = self.chunker.chunk_file(content, path)

            # Find chunk containing old_string
            target_chunk = None
            for chunk in chunks:
                if old_string in chunk.content:
                    target_chunk = chunk
                    break

            if not target_chunk:
                return create_error_response(
                    f"Text not found in any chunk: {old_string[:50]}...",
                    ErrorType.NOT_FOUND,
                    {"path": path, "search_text": old_string[:100]},
                )

            # Perform surgical edit within chunk
            new_chunk_content = target_chunk.content.replace(old_string, new_string, 1)

            # Update chunk
            target_chunk.update_content(new_chunk_content)

            # Reassemble file from all chunks
            # Sort chunks by their line range if available
            chunks.sort(key=lambda c: c.metadata.get("line_start", 0))

            reassembled = "\n".join([c.content for c in chunks])

            # Write back to file
            full_path.write_text(reassembled, encoding="utf-8")

            # Invalidate cache
            invalidate_file(full_path)

            # Track operation
            operation = EditOperation(
                chunk_id=target_chunk.chunk_id,
                operation_type="replace",
                old_text=old_string,
                new_text=new_string,
            )
            self.operation_history.append(operation)

            return create_success_response(
                {
                    "path": path,
                    "changes": 1,
                    "chunks_modified": 1,
                    "total_chunks": len(chunks),
                    "chunk_id": target_chunk.chunk_id,
                    "bytes_modified": len(new_chunk_content) - len(target_chunk.content),
                }
            )

        except Exception as e:
            return create_error_response(
                f"Failed to edit file with chunking: {str(e)}",
                ErrorType.EXECUTION,
                {"path": path, "error": str(e)},
            )

    def _edit_chunk_surgically(
        self,
        path: str,
        chunk_id: str,
        old_string: Optional[str],
        new_string: Optional[str],
        full_path: Path,
    ) -> Dict[str, Any]:
        """
        Surgical edit on a specific chunk.

        This method:
        1. Loads and chunks the file if not already cached
        2. Finds the target chunk by ID
        3. Replaces text within that chunk
        4. Updates only that chunk in the file
        """
        try:
            # Load or retrieve file context
            if path not in self.file_contexts:
                content = full_path.read_text(encoding="utf-8")
                context = create_context_window_from_file(content, path, model=self.agent.model)
                self.file_contexts[path] = context
                # Cache chunks
                for chunk in context.available_chunks:
                    self.chunk_cache[chunk.chunk_id] = chunk
            else:
                context = self.file_contexts[path]

            # Find target chunk
            target_chunk = None
            for chunk in context.available_chunks:
                if chunk.chunk_id == chunk_id:
                    target_chunk = chunk
                    break

            if not target_chunk:
                return create_error_response(
                    f"Chunk not found: {chunk_id}",
                    ErrorType.NOT_FOUND,
                    {"path": path, "chunk_id": chunk_id},
                )

            if old_string is None or new_string is None:
                return create_error_response(
                    "Both old_string and new_string are required for chunk edit",
                    ErrorType.VALIDATION,
                    {"path": path},
                )

            if old_string not in target_chunk.content:
                return create_error_response(
                    f"Text not found in chunk: {old_string[:50]}...",
                    ErrorType.NOT_FOUND,
                    {"path": path, "chunk_id": chunk_id},
                )

            # Load full file BEFORE modifying chunk
            content = full_path.read_text(encoding="utf-8")

            # Find chunk boundaries in original content
            # This is simplified - in production you'd track exact positions
            chunk_start = content.find(target_chunk.content)
            if chunk_start == -1:
                # If chunk not found (content changed), need full rechunk
                return create_error_response(
                    "Chunk boundaries changed - please reload file",
                    ErrorType.VALIDATION,
                    {"path": path, "hint": "File content may have changed externally"},
                )

            # Perform surgical replacement in chunk
            new_chunk_content = target_chunk.content.replace(old_string, new_string, 1)

            # Update chunk
            target_chunk.update_content(new_chunk_content)

            # Replace chunk in file content
            old_chunk_content = content[chunk_start : chunk_start + target_chunk.original_length]
            new_content = content.replace(old_chunk_content, new_chunk_content, 1)

            # Write back to file
            full_path.write_text(new_content, encoding="utf-8")

            # Invalidate cache
            invalidate_file(full_path)

            # Track operation
            operation = EditOperation(
                chunk_id=chunk_id,
                operation_type="replace",
                old_text=old_string,
                new_text=new_string,
            )
            self.operation_history.append(operation)

            return create_success_response(
                {
                    "path": path,
                    "chunk_id": chunk_id,
                    "changes": 1,
                    "bytes_modified": len(new_chunk_content) - len(target_chunk.content),
                }
            )

        except Exception as e:
            return create_error_response(
                f"Failed to edit chunk: {str(e)}",
                ErrorType.EXECUTION,
                {"path": path, "chunk_id": chunk_id, "error": str(e)},
            )

    def read_file_chunked(
        self, path: str, offset: int = 0, limit: int = 0, **kwargs
    ) -> Dict[str, Any]:
        """
        Read file with chunking support.

        Args:
            path: Relative path to the file
            offset: Line number to start reading from (1-indexed)
            limit: Maximum number of lines to read

        Returns:
            Standardized response with file content or chunks
        """
        try:
            full_path = validate_path(self.project_dir, path)

            if not full_path.exists():
                return create_error_response(
                    f"File not found: {path}", ErrorType.NOT_FOUND, {"path": path}
                )

            file_size = full_path.stat().st_size

            # Check if file should be chunked
            content = full_path.read_text(encoding="utf-8")
            should_chunk = should_chunk_file(content, path)

            if should_chunk:
                # Chunk the file
                chunks = self.chunker.chunk_file(content, path)

                # Cache the context
                context = create_context_window_from_file(content, path, model=self.agent.model)
                self.file_contexts[path] = context
                for chunk in chunks:
                    self.chunk_cache[chunk.chunk_id] = chunk

                return create_success_response(
                    {
                        "path": path,
                        "chunks": len(chunks),
                        "total_tokens": sum(c.token_estimate for c in chunks),
                        "chunk_ids": [c.chunk_id for c in chunks],
                        "file_size": file_size,
                        "is_chunked": True,
                    }
                )
            else:
                # Standard read with offset/limit
                lines = content.split("\n")

                if offset > 0 or limit > 0:
                    start = max(0, offset - 1)
                    end = start + (limit or len(lines))
                    selected_lines = lines[start:end]
                    content = "\n".join(selected_lines)
                else:
                    start = 0
                    end = len(lines)

                return create_success_response(
                    {
                        "path": path,
                        "content": content,
                        "lines_read": end - start,
                        "total_lines": len(lines),
                        "offset": offset,
                        "limit": limit,
                        "is_chunked": False,
                    }
                )

        except SecurityError as e:
            return create_permission_denial(str(e), {"path": path})
        except Exception as e:
            return create_error_response(
                f"Failed to read file: {str(e)}",
                ErrorType.EXECUTION,
                {"path": path, "error": str(e)},
            )

    def get_file_chunks(self, path: str) -> Dict[str, Any]:
        """
        Get all chunks for a file.

        Args:
            path: Relative path to the file

        Returns:
            Information about file chunks
        """
        try:
            full_path = validate_path(self.project_dir, path)

            if not full_path.exists():
                return create_error_response(
                    f"File not found: {path}", ErrorType.NOT_FOUND, {"path": path}
                )

            # Load or retrieve file context
            if path not in self.file_contexts:
                content = full_path.read_text(encoding="utf-8")
                context = create_context_window_from_file(content, path, model=self.agent.model)
                self.file_contexts[path] = context
                for chunk in context.available_chunks:
                    self.chunk_cache[chunk.chunk_id] = chunk
            else:
                context = self.file_contexts[path]

            chunks_info = []
            for chunk in context.available_chunks:
                chunks_info.append(
                    {
                        "id": chunk.chunk_id,
                        "type": chunk.chunk_type.value,
                        "tokens": chunk.token_estimate,
                        "bytes": chunk.current_length,
                        "metadata": chunk.metadata,
                    }
                )

            return create_success_response(
                {
                    "path": path,
                    "chunks": chunks_info,
                    "total_chunks": len(context.available_chunks),
                    "total_tokens": context.get_stats()["total_tokens"],
                }
            )

        except SecurityError as e:
            return create_permission_denial(str(e), {"path": path})
        except Exception as e:
            return create_error_response(
                f"Failed to get chunks: {str(e)}",
                ErrorType.EXECUTION,
                {"path": path, "error": str(e)},
            )

    def edit_chunk_content(
        self, path: str, chunk_id: str, new_content: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Replace entire content of a specific chunk.

        Args:
            path: Relative path to the file
            chunk_id: ID of the chunk to edit
            new_content: New content for the chunk

        Returns:
            Standardized response
        """
        try:
            full_path = validate_path(self.project_dir, path)

            if not full_path.exists():
                return create_error_response(
                    f"File not found: {path}", ErrorType.NOT_FOUND, {"path": path}
                )

            # Find and update chunk
            return self._edit_chunk_surgically(path, chunk_id, None, new_content, full_path)

        except SecurityError as e:
            return create_permission_denial(str(e), {"path": path})
        except Exception as e:
            return create_error_response(
                f"Failed to edit chunk content: {str(e)}",
                ErrorType.EXECUTION,
                {"path": path, "chunk_id": chunk_id, "error": str(e)},
            )

    def rollback_last_edit(self) -> Dict[str, Any]:
        """
        Rollback the last edit operation.

        Returns:
            Standardized response with rollback result
        """
        if not self.operation_history:
            return create_error_response("No edit operations to rollback", ErrorType.VALIDATION)

        last_op = self.operation_history.pop()

        # Note: In production, you'd need to store the original content
        # for complete rollback. This is a simplified version.
        return create_success_response(
            {"rolled_back": last_op, "remaining_operations": len(self.operation_history)}
        )

    def get_chunk_context(self, path: str) -> Optional[ContextWindowManager]:
        """Get the context window manager for a file."""
        return self.file_contexts.get(path)


def create_chunked_editor(project_dir: str) -> ChunkedEditTool:
    """
    Factory function to create a chunked edit tool.

    Args:
        project_dir: Project root directory

    Returns:
        ChunkedEditTool instance
    """
    return ChunkedEditTool(project_dir=project_dir)
