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


class ReadFileTool(Tool):
    """Tool for reading files with optional offset and limit support."""

    # Maximum characters per line before truncation
    MAX_LINE_LENGTH = 2000
    # Default line limit
    DEFAULT_LIMIT = 2000

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
            if offset > 0 or limit > 0:
                self.console.print(
                    f"[cyan]Reading:[/cyan] {path} (lines {offset + 1}-{offset + (limit or self.DEFAULT_LIMIT)})"
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


class WriteFileTool(Tool):
    """Tool for writing files"""

    def execute(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to file"""

        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]⏸  PLAN MODE:[/yellow] Would write to {path}")
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
                    "hint": "This may indicate a JSON parsing error in the tool arguments. Please provide actual file content.",
                    "content_length": len(content) if content else 0,
                },
            )

        if self.console:
            self.console.print(f"[yellow]📝 Writing:[/yellow] {path}")

        try:
            full_path = validate_path(self.project_dir, path)

            # Show diff if file exists
            if full_path.exists():
                old_content = full_path.read_text(encoding="utf-8-sig")
                if self.console:
                    self.console.print(
                        Panel(
                            f"[red]- Old ({len(old_content)} bytes)[/red]\n"
                            f"[green]+ New ({len(content)} bytes)[/green]",
                            title="📊 Changes",
                        )
                    )

            # Show preview of new content
            if self.console:
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
                        self.console.print("[red]✗[/red] Cancelled by user")
                    return create_permission_denial(
                        "Cancelled by user", "write_file", {"path": path}
                    )

            # Backup before write
            self.backup_file(full_path, "write")

            # Write file
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

            # Verify written content matches (checksum validation to detect corruption)
            try:
                written_content = full_path.read_text(encoding="utf-8-sig")
                if written_content != content:
                    return create_error_response(
                        "Content verification failed - written content does not match intended content",
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
                self.console.print(f"[green]✓[/green] Wrote {len(content)} bytes to {path}")

            return create_success_response({"bytes_written": len(content)})

        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY, {"path": path})
        except Exception as e:
            return create_error_response(
                str(e), ErrorType.EXECUTION, {"path": path}, retryable=True
            )
