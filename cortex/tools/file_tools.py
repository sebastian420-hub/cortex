"""File I/O tools"""

from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm

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
from ..core.memory_chunked.chunking import should_chunk_file, FileChunker, ChunkingStrategy
from ..core.memory_chunked.chunk import create_file_chunk
from ..ui.modes import is_minimal_mode


class ReadFileTool(Tool):
    """Tool for reading files with optional offset and limit support."""

    # Maximum characters per line before truncation
    MAX_LINE_LENGTH = 2000
    # Default line limit
    DEFAULT_LIMIT = 2000
    # File size warning threshold (1MB)
    LARGE_FILE_WARNING_BYTES = 1_000_000
    # Maximum file size before requiring explicit confirmation (10MB)
    MAX_FILE_SIZE_BYTES = 10_000_000

    # Binary file signatures (magic numbers)
    BINARY_SIGNATURES = [
        b"\x89PNG",  # PNG
        b"\xff\xd8\xff",  # JPEG
        b"GIF87a",  # GIF
        b"GIF89a",  # GIF
        b"PK\x03\x04",  # ZIP/DOCX/XLSX
        b"%PDF",  # PDF
        b"\x7fELF",  # ELF executable
        b"MZ",  # Windows executable
        b"\x00\x00\x01\x00",  # ICO
        b"RIFF",  # RIFF (WAV, AVI)
        b"\x1f\x8b",  # GZIP
        b"BZh",  # BZIP2
        b"\xfd7zXZ",  # XZ
        b"SQLite",  # SQLite
    ]

    # Binary file extensions
    BINARY_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",
        ".tiff",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".zip",
        ".tar",
        ".gz",
        ".7z",
        ".rar",
        ".bz2",
        ".xz",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".o",
        ".a",
        ".pyc",
        ".pyo",
        ".class",
        ".jar",
        ".war",
        ".mp3",
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".wav",
        ".flac",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".db",
        ".sqlite",
        ".sqlite3",
    }

    def _is_binary_file(self, path: Path) -> tuple[bool, str]:
        """
        Check if a file is binary using magic numbers and extension.

        Returns:
            Tuple of (is_binary, reason)
        """
        # Check extension first (fast)
        if path.suffix.lower() in self.BINARY_EXTENSIONS:
            return True, f"Binary extension: {path.suffix}"

        # Check magic numbers (more reliable)
        try:
            with open(path, "rb") as f:
                header = f.read(16)
                for sig in self.BINARY_SIGNATURES:
                    if header.startswith(sig):
                        return True, f"Binary signature detected"

                # Check for null bytes (common in binaries)
                if b"\x00" in header:
                    return True, "Contains null bytes"
        except Exception:
            pass

        return False, ""

    def execute(
        self,
        path: str,
        offset: int = 0,
        limit: int = 0,
    ) -> Dict[str, Any]:
        """
        Read file contents with optional offset and limit.

        Args:
            path: Relative path to the file from project root
            offset: Line number to start reading from (1-indexed, default: 0 = start)
            limit: Maximum number of lines to read (default: 0 = up to DEFAULT_LIMIT)

        Returns:
            Standardized response with file content
        """
        if self.console:
            if is_minimal_mode():
                # Minimal mode: simpler message
                if offset > 0 or limit > 0:
                    self.console.print(
                        f"[dim][FILE] {path} (lines {offset + 1}-{offset + (limit or self.DEFAULT_LIMIT)})[/dim]"  # noqa: E501
                    )
                else:
                    self.console.print(f"[dim][FILE] {path}[/dim]")
            else:
                # Normal/debug mode: current display
                if offset > 0 or limit > 0:
                    self.console.print(
                        f"[cyan]Reading:[/cyan] {path} (lines {offset + 1}-{offset + (limit or self.DEFAULT_LIMIT)})"  # noqa: E501
                    )
                else:
                    self.console.print(f"[cyan]Reading:[/cyan] {path}")

        try:
            full_path = validate_path(self.project_dir, path)

            if not full_path.exists():
                return create_error_response(
                    f"File not found: {path}", ErrorType.NOT_FOUND, {"path": path}
                )

            if not full_path.is_file():
                return create_error_response(
                    f"Path is not a file: {path}",
                    ErrorType.VALIDATION,
                    {"path": path},
                    retryable=True,
                )

            # Check file size and warn if large
            file_size = full_path.stat().st_size
            if file_size > self.MAX_FILE_SIZE_BYTES:
                size_mb = file_size / 1_000_000
                return create_error_response(
                    f"File is very large ({size_mb:.1f} MB). Use offset and limit parameters to read specific portions.",  # noqa: E501
                    ErrorType.VALIDATION,
                    {
                        "path": path,
                        "size_bytes": file_size,
                        "size_mb": round(size_mb, 2),
                        "hint": f"Try: read_file(path='{path}', offset=0, limit=500) to read first 500 lines",  # noqa: E501
                    },
                )

            if file_size > self.LARGE_FILE_WARNING_BYTES and self.console:
                size_mb = file_size / 1_000_000
                self.console.print(
                    f"[yellow]Warning:[/yellow] Large file ({size_mb:.1f} MB). "
                    f"Consider using offset/limit for better performance."
                )

            # Check for binary file
            is_binary, binary_reason = self._is_binary_file(full_path)
            if is_binary:
                return create_error_response(
                    f"Cannot read binary file: {path}",
                    ErrorType.VALIDATION,
                    {
                        "path": path,
                        "reason": binary_reason,
                        "hint": "Binary files cannot be displayed as text. Use appropriate tools for this file type.",  # noqa: E501
                    },
                )

            # Try to get from cache first
            cache = get_file_cache()
            raw_content = cache.get(full_path)
            from_cache = raw_content is not None

            if raw_content is None:
                # Cache miss - read from disk with encoding fallback
                encoding_errors = []

                # Try different encodings
                encodings_to_try = ["utf-8", "utf-8-sig", "latin-1"]
                for encoding in encodings_to_try:
                    try:
                        raw_content = full_path.read_text(encoding=encoding)
                        break  # Success!
                    except UnicodeDecodeError as e:
                        encoding_errors.append(f"{encoding}: {e}")

                if raw_content is None:
                    # All encodings failed
                    return create_error_response(
                        f"File encoding issue: could not decode {path} with any encoding",
                        ErrorType.VALIDATION,
                        {
                            "path": path,
                            "errors": encoding_errors,
                            "hint": "This may be a binary file",
                        },
                    )

                # Cache the content for future reads
                cache.set(full_path, raw_content)
            all_lines = raw_content.split("\n")
            total_lines = len(all_lines)

            # Apply offset and limit
            effective_limit = limit if limit > 0 else self.DEFAULT_LIMIT
            start_line = max(0, offset)
            end_line = min(total_lines, start_line + effective_limit)

            # Get requested lines
            selected_lines = all_lines[start_line:end_line]

            # Truncate long lines
            truncated_lines = []
            for line in selected_lines:
                if len(line) > self.MAX_LINE_LENGTH:
                    truncated_lines.append(line[: self.MAX_LINE_LENGTH] + "... (truncated)")
                else:
                    truncated_lines.append(line)

            # Format with line numbers (cat -n style, 1-indexed)
            numbered_content = ""
            for i, line in enumerate(truncated_lines, start=start_line + 1):
                # Format: "     1\tline content"
                numbered_content += f"{i:6}\t{line}\n"

            # Track if content was truncated
            was_truncated = end_line < total_lines

            # Show preview in console
            if self.console:
                if is_minimal_mode():
                    # Minimal mode: clean display without panel
                    line_count = len(truncated_lines)
                    total_display = f" of {total_lines}" if was_truncated else ""
                    cache_indicator = " [dim](cached)[/dim]" if from_cache else ""
                    self.console.print(
                        f"[cyan][FILE] {path}{cache_indicator} ({line_count} lines{total_display})[/cyan]"  # noqa: E501
                    )
                    if truncated_lines:
                        # Show first few lines
                        preview_lines = truncated_lines[: min(3, len(truncated_lines))]
                        for i, line in enumerate(preview_lines, start=start_line + 1):
                            self.console.print(f"  {i:3d}: {line}")
                        if len(truncated_lines) > 3:
                            self.console.print(
                                f"[dim]  ... ({len(truncated_lines) - 3} more lines)[/dim]"
                            )
                else:
                    # Normal/debug mode: panel display with syntax highlighting
                    ext = full_path.suffix.lstrip(".") or "txt"
                    preview_lines = truncated_lines[:15]
                    preview = "\n".join(preview_lines)
                    if len(truncated_lines) > 15:
                        preview += f"\n... ({len(truncated_lines) - 15} more lines shown)"

                    syntax = Syntax(
                        preview, ext, theme="monokai", line_numbers=True, start_line=start_line + 1
                    )
                    cache_indicator = " [dim](cached)[/dim]" if from_cache else ""
                    self.console.print(
                        Panel(syntax, title=f"{path}{cache_indicator}", border_style="cyan")
                    )

                if was_truncated:
                    self.console.print(
                        f"[dim]Showing lines {start_line + 1}-{end_line} of {total_lines}. "
                        f"Use offset/limit for more.[/dim]"
                    )

            return create_success_response(
                {
                    "content": numbered_content,
                    "lines_returned": len(truncated_lines),
                    "total_lines": total_lines,
                    "offset": start_line,
                    "truncated": was_truncated,
                    "size": len(raw_content),
                }
            )

        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY, {"path": path})
        except UnicodeDecodeError:
            return create_error_response(
                f"File appears to be binary or has encoding issues: {path}",
                ErrorType.VALIDATION,
                {"path": path, "hint": "This may be a binary file"},
            )
        except Exception as e:
            return create_error_response(
                str(e), ErrorType.EXECUTION, {"path": path}, retryable=True
            )

    def read_file_chunked(self, path: str, chunk_strategy: str = "smart") -> Dict[str, Any]:
        """
        Read and chunk a file for memory-efficient editing.

        Args:
            path: Relative path to the file
            chunk_strategy: Strategy for chunking ('smart', 'fixed_size', 'function_based')

        Returns:
            Standardized response with chunk information
        """
        try:
            full_path = validate_path(self.project_dir, path)

            if not full_path.exists():
                return create_error_response(
                    f"File not found: {path}", ErrorType.NOT_FOUND, {"path": path}
                )

            if self.console:
                self.console.print(f"[cyan]Chunking:[/cyan] {path}")

            # Read file content
            raw_content = full_path.read_text(encoding="utf-8")

            # Check if chunking is needed
            if not should_chunk_file(raw_content, path):
                if self.console:
                    self.console.print(f"[dim]File is small, chunking not needed[/dim]")
                return create_success_response(
                    {
                        "path": path,
                        "chunked": False,
                        "reason": "File is too small for chunking",
                        "size": len(raw_content),
                    }
                )

            # Determine chunking strategy
            strategy_map = {
                "smart": ChunkingStrategy.SMART,
                "fixed_size": ChunkingStrategy.FIXED_SIZE,
                "function_based": ChunkingStrategy.FUNCTION_BASED,
                "section": ChunkingStrategy.SECTION_BASED,
            }
            strategy = strategy_map.get(chunk_strategy, ChunkingStrategy.SMART)

            # Create chunker and chunk the file
            chunker = FileChunker(max_chunk_size=2000, strategy=strategy)
            chunks = chunker.chunk_file(raw_content, path)

            # Prepare chunk information
            chunk_info = []
            for chunk in chunks:
                chunk_info.append(
                    {
                        "id": chunk.chunk_id,
                        "type": chunk.chunk_type.value,
                        "tokens": chunk.token_estimate,
                        "bytes": chunk.current_length,
                        "metadata": chunk.metadata,
                    }
                )

            # Show chunk info in console
            if self.console:
                self.console.print(
                    f"[green][OK][/green] Created {len(chunks)} chunks "
                    f"({sum(c.token_estimate for c in chunks)} tokens total)"
                )
                for i, chunk in enumerate(chunks[:10], 1):
                    self.console.print(
                        f"  [dim]{i}. {chunk.chunk_id} - {chunk.chunk_type.value} "
                        f"({chunk.token_estimate} tokens)[/dim]"
                    )
                if len(chunks) > 10:
                    self.console.print(f"[dim]  ... and {len(chunks) - 10} more[/dim]")

            return create_success_response(
                {
                    "path": path,
                    "chunked": True,
                    "total_chunks": len(chunks),
                    "total_tokens": sum(c.token_estimate for c in chunks),
                    "strategy": chunk_strategy,
                    "chunks": chunk_info,
                    "size": len(raw_content),
                }
            )

        except SecurityError as e:
            return create_permission_denial(str(e), {"path": path})
        except Exception as e:
            return create_error_response(
                f"Failed to chunk file: {str(e)}",
                ErrorType.EXECUTION,
                {"path": path, "error": str(e)},
                retryable=True,
            )


class WriteFileTool(Tool):
    """Tool for writing files"""

    def execute(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to file"""

        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]PLAN MODE:[/yellow] Would write to {path}")
            return create_permission_denial(
                "Plan mode - no writes allowed",
                "write_file",
                {"path": path, "permission_mode": "plan"},
            )

        # Validate content is not empty (prevents accidental file erasure)
        if not content or not content.strip():
            return create_error_response(
                "Content is empty or whitespace-only. Cannot write empty content to file.",
                ErrorType.VALIDATION,
                {
                    "path": path,
                    "hint": "This may indicate a JSON parsing error in the tool arguments. Please provide actual file content.",  # noqa: E501
                    "content_length": len(content) if content else 0,
                },
            )

        if self.console:
            if is_minimal_mode():
                self.console.print(f"[yellow][FILE] {path}[/yellow]")
            else:
                self.console.print(f"[yellow]?? Writing:[/yellow] {path}")

        try:
            full_path = validate_path(self.project_dir, path)

            # Show diff if file exists
            if full_path.exists():
                old_content = full_path.read_text(encoding="utf-8")
                if self.console:
                    if is_minimal_mode():
                        self.console.print(
                            f"[yellow][DIFF] {path} ({len(old_content)} ? {len(content)} bytes)[/yellow]"  # noqa: E501
                        )
                    else:
                        self.console.print(
                            Panel(
                                f"[red]- Old ({len(old_content)} bytes)[/red]\n"
                                f"[green]+ New ({len(content)} bytes)[/green]",
                                title="[DIFF] Changes",
                            )
                        )

            # Show preview of new content
            if self.console:
                if is_minimal_mode():
                    # Minimal mode: simple preview
                    content_lines = content.split("\n")
                    line_count = len(content_lines)
                    self.console.print(f"[cyan][FILE] {path} ({line_count} lines)[/cyan]")
                    if content_lines:
                        # Show first few lines
                        preview_lines = content_lines[: min(3, len(content_lines))]
                        for i, line in enumerate(preview_lines, 1):
                            self.console.print(f"  {i:3d}: {line}")
                        if line_count > 3:
                            self.console.print(f"[dim]  ... ({line_count - 3} more lines)[/dim]")
                else:
                    # Normal/debug mode: panel display
                    ext = full_path.suffix.lstrip(".") or "txt"
                    content_lines = content.split("\n")
                    preview_lines = content_lines[:20]
                    preview = "\n".join(preview_lines)
                    if len(content_lines) > 20:
                        more_lines = len(content_lines) - 20
                        preview += f"\n... ({more_lines} more lines)"

                    syntax = Syntax(preview, ext, theme="monokai", line_numbers=True)
                    self.console.print(
                        Panel(syntax, title=f"New content: {path}", border_style="yellow")
                    )

            # Ask for approval
            if self.permission_mode == PermissionMode.NORMAL and self.console:
                if not Confirm.ask(f"[bold]Write to {path}?[/bold]"):
                    if self.console:
                        if is_minimal_mode():
                            self.console.print("[red][X] Cancelled by user[/red]")
                        else:
                            self.console.print("[red]?[/red] Cancelled by user")
                    return create_permission_denial(
                        "Cancelled by user", "write_file", {"path": path}
                    )

            # Backup before write
            self.backup_file(full_path, "write")

            # Write file
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

            # Verify written content matches (checksum validation to detect corruption)
            try:
                written_content = full_path.read_text(encoding="utf-8")
                if written_content != content:
                    return create_error_response(
                        "Content verification failed - written content does not match intended content",  # noqa: E501
                        ErrorType.EXECUTION,
                        {
                            "path": path,
                            "intended_size": len(content),
                            "written_size": len(written_content),
                            "hint": "File may have been corrupted during write operation",
                        },
                    )
            except Exception as verify_error:
                return create_error_response(
                    f"Failed to verify written content: {verify_error}",
                    ErrorType.EXECUTION,
                    {"path": path},
                )

            # Invalidate cache for this file
            invalidate_file(full_path)

            if self.console:
                if is_minimal_mode():
                    self.console.print(f"[green][OK] Wrote {len(content)} bytes to {path}[/green]")
                else:
                    self.console.print(f"[green]?[/green] Wrote {len(content)} bytes to {path}")

            return create_success_response({"bytes_written": len(content)})

        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY, {"path": path})
        except Exception as e:
            return create_error_response(
                str(e), ErrorType.EXECUTION, {"path": path}, retryable=True
            )
