"""Utilities for creating and managing chunks from file content."""

import re
from enum import Enum
from typing import List, Optional, Tuple
from pathlib import Path

from .chunk import EditChunk, ChunkType, create_file_chunk, create_source_code_chunk


class ChunkingStrategy(Enum):
    """Strategies for chunking file content."""

    FIXED_SIZE = "fixed_size"  # Fixed character/line size
    FUNCTION_BASED = "function_based"  # By function/class boundaries
    SECTION_BASED = "section_based"  # By sections/headings
    SMART = "smart"  # Intelligent chunking based on content


class FileChunker:
    """
    Utility class for chunking file content into manageable pieces.

    Supports multiple strategies and intelligent splitting based on
    file type and content structure.
    """

    def __init__(
        self,
        max_chunk_size: int = 2000,
        strategy: ChunkingStrategy = ChunkingStrategy.SMART,
        preserve_boundaries: bool = True,
    ):
        """
        Initialize chunker with configuration.

        Args:
            max_chunk_size: Maximum characters per chunk
            strategy: Chunking strategy to use
            preserve_boundaries: Whether to preserve logical boundaries (functions, etc.)
        """
        self.max_chunk_size = max_chunk_size
        self.strategy = strategy
        self.preserve_boundaries = preserve_boundaries

    def chunk_file(
        self, content: str, file_path: str, language: Optional[str] = None
    ) -> List[EditChunk]:
        """
        Split file content into chunks.

        Args:
            content: File content as string
            file_path: Path to the file
            language: Optional language hint for smart chunking

        Returns:
            List of EditChunk instances
        """
        file_path_obj = Path(file_path)
        extension = file_path_obj.suffix.lower()

        # Determine language if not provided
        if not language:
            language = self._infer_language(extension)

        if self.strategy == ChunkingStrategy.FIXED_SIZE:
            return self._chunk_fixed_size(content, file_path)
        elif self.strategy == ChunkingStrategy.FUNCTION_BASED:
            return self._chunk_by_function(content, file_path, language)
        elif self.strategy == ChunkingStrategy.SECTION_BASED:
            return self._chunk_by_section(content, file_path)
        elif self.strategy == ChunkingStrategy.SMART:
            return self._chunk_smart(content, file_path, language)
        else:
            return self._chunk_fixed_size(content, file_path)

    def _chunk_fixed_size(self, content: str, file_path: str) -> List[EditChunk]:
        """Split content into fixed-size chunks."""
        chunks = []

        for i in range(0, len(content), self.max_chunk_size):
            chunk_content = content[i : i + self.max_chunk_size]

            # Calculate line range
            lines_before = content[:i].count("\n") + 1
            lines_in_chunk = chunk_content.count("\n") + 1
            line_range = (lines_before, lines_before + lines_in_chunk - 1)

            chunk = create_file_chunk(
                content=chunk_content, file_path=file_path, line_range=line_range
            )
            chunks.append(chunk)

        return chunks

    def _chunk_by_function(self, content: str, file_path: str, language: str) -> List[EditChunk]:
        """Split content by function/class boundaries."""
        chunks = []

        if language == "python":
            chunks = self._chunk_python_by_function(content, file_path)
        elif language in ["javascript", "typescript"]:
            chunks = self._chunk_js_by_function(content, file_path)
        elif language == "go":
            chunks = self._chunk_go_by_function(content, file_path)
        else:
            # Fallback to smart chunking
            chunks = self._chunk_smart(content, file_path, language)

        return chunks

    def _chunk_python_by_function(self, content: str, file_path: str) -> List[EditChunk]:
        """Python-specific function-based chunking."""
        lines = content.split("\n")
        chunks = []
        current_chunk = []
        current_start = 1
        in_function = False
        function_name = None
        indent_level = 0

        for i, line in enumerate(lines, 1):
            # Check for function/class definition
            stripped = line.lstrip()

            # Function or class definition
            if (stripped.startswith("def ") or stripped.startswith("class ")) and ":" in stripped:
                current_indent = len(line) - len(stripped)

                # Check if this is a nested definition (inside current function/class)
                is_nested = in_function and current_indent > indent_level

                # Save previous chunk if this is a new top-level function/class
                if current_chunk and in_function and not is_nested:
                    chunk_content = "\n".join(current_chunk)
                    chunk = create_source_code_chunk(
                        content=chunk_content,
                        file_path=file_path,
                        language="python",
                        function_name=function_name,
                        line_range=(current_start, i - 1),
                    )
                    chunks.append(chunk)
                    current_chunk = []
                    current_start = i
                    in_function = False
                    indent_level = 0

                # Add line to current chunk (nested or not, it's part of the content)
                current_chunk.append(line)

                # If not nested, start/continue a top-level function/class
                if not is_nested:
                    in_function = True
                    indent_level = current_indent

                # Extract function/class name
                if stripped.startswith("def "):
                    match = re.match(r"def\s+(\w+)", stripped)
                    if match:
                        function_name = match.group(1)
                elif stripped.startswith("class "):
                    match = re.match(r"class\s+(\w+)", stripped)
                    if match:
                        function_name = match.group(1)

            # Check for dedent (end of function)
            elif in_function and stripped and (len(line) - len(stripped)) <= indent_level:
                # End of current function
                chunk_content = "\n".join(current_chunk)
                chunk = create_source_code_chunk(
                    content=chunk_content,
                    file_path=file_path,
                    language="python",
                    function_name=function_name,
                    line_range=(current_start, i - 1),
                )
                chunks.append(chunk)
                current_chunk = []
                current_start = i
                in_function = False
                function_name = None
                indent_level = 0
                current_chunk.append(line)

            else:
                current_chunk.append(line)

        # Add final chunk
        if current_chunk:
            chunk_content = "\n".join(current_chunk)
            chunk = create_source_code_chunk(
                content=chunk_content,
                file_path=file_path,
                language="python",
                function_name=function_name,
                line_range=(current_start, len(lines)),
            )
            chunks.append(chunk)

        return chunks

    def _chunk_js_by_function(self, content: str, file_path: str) -> List[EditChunk]:
        """JavaScript/TypeScript function-based chunking."""
        lines = content.split("\n")
        chunks = []
        current_chunk = []
        current_start = 1
        brace_count = 0
        in_function = False
        function_name = None
        waiting_for_brace = False

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Check for function definition
            if not in_function and (
                stripped.startswith("function ")
                or "=>" in stripped
                or stripped.startswith("async function ")
            ):
                current_chunk.append(line)
                in_function = True
                current_start = i
                waiting_for_brace = True

                # Extract function name
                if stripped.startswith("function "):
                    match = re.match(r"function\s+(\w+)", stripped)
                    if match:
                        function_name = match.group(1)
                elif stripped.startswith("async function "):
                    match = re.match(r"async\s+function\s+(\w+)", stripped)
                    if match:
                        function_name = match.group(1)
                else:
                    function_name = "anonymous"

            elif in_function:
                current_chunk.append(line)
                brace_count += line.count("{") - line.count("}")

                if brace_count == 0 and not waiting_for_brace:
                    # End of function
                    chunk_content = "\n".join(current_chunk)
                    chunk = create_source_code_chunk(
                        content=chunk_content,
                        file_path=file_path,
                        language="javascript",
                        function_name=function_name,
                        line_range=(current_start, i),
                    )
                    chunks.append(chunk)
                    current_chunk = []
                    in_function = False
                    function_name = None

                waiting_for_brace = False

            else:
                current_chunk.append(line)

        # Add final chunk
        if current_chunk:
            chunk_content = "\n".join(current_chunk)
            chunk = create_source_code_chunk(
                content=chunk_content,
                file_path=file_path,
                language="javascript",
                line_range=(current_start, len(lines)),
            )
            chunks.append(chunk)

        return chunks

    def _chunk_go_by_function(self, content: str, file_path: str) -> List[EditChunk]:
        """Go function-based chunking (simplistic)."""
        # Go uses 'func' keyword and braces
        # Simplified implementation
        lines = content.split("\n")
        chunks = []
        current_chunk = []
        current_start = 1
        brace_count = 0
        in_function = False
        function_name = None

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            if not in_function and stripped.startswith("func "):
                current_chunk.append(line)
                in_function = True
                current_start = i

                match = re.match(r"func\s+(\w+)", stripped)
                if match:
                    function_name = match.group(1)

            elif in_function:
                current_chunk.append(line)
                brace_count += line.count("{") - line.count("}")

                if brace_count == 0:
                    chunk_content = "\n".join(current_chunk)
                    chunk = create_source_code_chunk(
                        content=chunk_content,
                        file_path=file_path,
                        language="go",
                        function_name=function_name,
                        line_range=(current_start, i),
                    )
                    chunks.append(chunk)
                    current_chunk = []
                    in_function = False
                    function_name = None

            else:
                current_chunk.append(line)

        if current_chunk:
            chunk_content = "\n".join(current_chunk)
            chunk = create_source_code_chunk(
                content=chunk_content,
                file_path=file_path,
                language="go",
                line_range=(current_start, len(lines)),
            )
            chunks.append(chunk)

        return chunks

    def _chunk_by_section(self, content: str, file_path: str) -> List[EditChunk]:
        """Split content by markdown/section headers."""
        lines = content.split("\n")
        chunks = []
        current_chunk = []
        current_start = 1

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Section headers in markdown or configuration
            if (
                stripped.startswith("# ")
                or stripped.startswith("## ")
                or stripped.startswith("### ")
                or stripped.startswith("===")
                or stripped.startswith("---")
            ):

                if current_chunk:
                    chunk_content = "\n".join(current_chunk)
                    chunk = create_file_chunk(
                        content=chunk_content,
                        file_path=file_path,
                        line_range=(current_start, i - 1),
                    )
                    chunks.append(chunk)

                current_chunk = [line]
                current_start = i
            else:
                current_chunk.append(line)

        if current_chunk:
            chunk_content = "\n".join(current_chunk)
            chunk = create_file_chunk(
                content=chunk_content, file_path=file_path, line_range=(current_start, len(lines))
            )
            chunks.append(chunk)

        return chunks

    def _chunk_smart(self, content: str, file_path: str, language: str) -> List[EditChunk]:
        """Intelligent chunking based on content type."""
        # Try function-based first if it's code
        if language and language not in ["text", "markdown", "yaml", "json"]:
            chunks = self._chunk_by_function(content, file_path, language)
            if chunks and len(chunks) > 1:
                return chunks

        # Check if file is small enough for single chunk
        if len(content) <= self.max_chunk_size * 1.5:
            chunk = create_file_chunk(
                content=content, file_path=file_path, line_range=(1, content.count("\n") + 1)
            )
            return [chunk]

        # Fallback to section-based if it looks like markdown
        if language in ["markdown", "text", "md"]:
            chunks = self._chunk_by_section(content, file_path)
            if chunks and len(chunks) > 1:
                return chunks

        # Final fallback: fixed size
        return self._chunk_fixed_size(content, file_path)

    def _infer_language(self, extension: str) -> str:
        """Infer language from file extension."""
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".md": "markdown",
            ".txt": "text",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "bash",
            ".rb": "ruby",
            ".php": "php",
            ".go": "go",
        }
        return lang_map.get(extension, "text")


def chunk_file_by_function(
    content: str, file_path: str, language: Optional[str] = None
) -> List[EditChunk]:
    """
    Convenience function to chunk a file by function boundaries.

    Args:
        content: File content
        file_path: Path to the file
        language: Optional language hint

    Returns:
        List of EditChunk instances
    """
    chunker = FileChunker(strategy=ChunkingStrategy.FUNCTION_BASED)
    return chunker.chunk_file(content, file_path, language)


def chunk_file_by_size(content: str, file_path: str, max_size: int = 2000) -> List[EditChunk]:
    """
    Convenience function to chunk a file by size.

    Args:
        content: File content
        file_path: Path to the file
        max_size: Maximum chunk size in characters

    Returns:
        List of EditChunk instances
    """
    chunker = FileChunker(strategy=ChunkingStrategy.FIXED_SIZE, max_chunk_size=max_size)
    return chunker.chunk_file(content, file_path)


def should_chunk_file(content: str, file_path: str) -> bool:
    """
    Determine if a file should be chunked based on size and type.

    Args:
        content: File content
        file_path: Path to the file

    Returns:
        True if chunking is recommended
    """
    file_size = len(content)

    # Large files should be chunked
    if file_size > 10000:  # 10KB threshold
        return True

    # Code files with multiple functions should be chunked
    extension = Path(file_path).suffix.lower()
    if extension in [".py", ".js", ".ts", ".go", ".java"]:
        # Count function/class definitions
        func_count = len(re.findall(r"\b(def|function|func|class)\b", content))
        return func_count >= 3

    return False
