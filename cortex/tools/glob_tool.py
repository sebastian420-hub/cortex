"""Fast file pattern matching tool"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .base import Tool
from ..core.security import validate_path, SecurityError
from ..utils.errors import create_error_response, create_success_response, ErrorType


class GlobTool(Tool):
    """
    Fast file pattern matching tool.

    Features:
    - Supports glob patterns like "**/*.py" or "src/**/*.ts"
    - Returns matching file paths sorted by modification time
    - Cross-platform support
    - Efficient for any codebase size
    """

    timeout_category = "search"
    default_timeout = 30

    def execute(
        self,
        pattern: str,
        path: str = ".",
        sort_by_mtime: bool = True,
        include_hidden: bool = False,
        max_results: int = 200,
    ) -> Dict[str, Any]:
        """
        Find files matching glob pattern.

        Args:
            pattern: Glob pattern to match (e.g., "**/*.py", "src/*.ts")
            path: Base directory to search from (default: current directory)
            sort_by_mtime: Sort by modification time, newest first (default: True)
            include_hidden: Include hidden files/directories (default: False)
            max_results: Maximum number of results (default: 200, reduced to prevent context overflow)

        Returns:
            Standardized response with matching file paths
        """
        if self.console:
            self.console.print(f"[cyan]Finding files:[/cyan] {pattern}")

        # Validate path
        try:
            full_path = validate_path(self.project_dir, path)
        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY, {"path": path})

        if not full_path.exists():
            return create_error_response(
                f"Path not found: {path}", ErrorType.NOT_FOUND, {"path": path}
            )

        if not full_path.is_dir():
            return create_error_response(
                f"Path is not a directory: {path}", ErrorType.VALIDATION, {"path": path}
            )

        try:
            # Find matching files
            matches = list(full_path.glob(pattern))

            # Filter to files only (not directories)
            files = [f for f in matches if f.is_file()]

            # Filter hidden files if not included
            if not include_hidden:
                files = self._filter_hidden(files, full_path)

            # Sort by modification time if requested
            if sort_by_mtime:
                files = self._sort_by_mtime(files)

            # Convert to relative paths
            relative_paths = []
            for f in files:
                try:
                    rel_path = f.relative_to(self.project_dir)
                    relative_paths.append(str(rel_path))
                except ValueError:
                    # File is outside project directory, use absolute path
                    relative_paths.append(str(f))

            # Limit results
            total_count = len(relative_paths)
            truncated = total_count > max_results
            if truncated:
                relative_paths = relative_paths[:max_results]

            # Display results
            if self.console:
                self._display_results(relative_paths, total_count, truncated)

            return create_success_response(
                {
                    "files": relative_paths,
                    "count": len(relative_paths),
                    "total_count": total_count,
                    "truncated": truncated,
                    "pattern": pattern,
                }
            )

        except Exception as e:
            return create_error_response(
                str(e), ErrorType.EXECUTION, {"pattern": pattern, "path": path}
            )

    def _filter_hidden(self, files: List[Path], base_path: Path) -> List[Path]:
        """Filter out hidden files and common ignored directories."""
        ignored_dirs = {
            ".git",
            ".svn",
            ".hg",
            ".bzr",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "env",
            ".tox",
            ".eggs",
            "dist",
            "build",
            ".mypy_cache",
            ".pytest_cache",
            ".coverage",
            ".idea",
            ".vscode",
            ".vs",
            "vendor",
            "target",  # Rust/Java build output
            ".gradle",
            ".next",  # Next.js build
            ".nuxt",  # Nuxt.js build
            "__snapshots__",
            "coverage",
            ".turbo",
        }

        # Common binary/non-code extensions to skip
        skip_extensions = {
            ".pyc",
            ".pyo",
            ".pyd",
            ".so",
            ".dll",
            ".dylib",
            ".exe",
            ".bin",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".ico",
            ".svg",
            ".webp",
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
            ".lock",  # Lock files
        }

        filtered = []
        for f in files:
            try:
                rel_parts = f.relative_to(base_path).parts

                # Skip if any part is hidden or in ignored list
                if any(part.startswith(".") or part in ignored_dirs for part in rel_parts):
                    continue

                # Skip common non-project directories (user data, downloads, etc.)
                # These are often accidentally included in broad searches
                suspicious_keywords = [
                    "download",
                    "temp",
                    "tmp",
                    "cache",
                    "backup",
                    "archive",
                    "old",
                    "deprecated",
                    "legacy",
                ]
                if any(
                    keyword in part.lower() for part in rel_parts for keyword in suspicious_keywords
                ):
                    # Only skip if it looks like a data directory (not source code)
                    if not any(
                        src_indicator in part.lower()
                        for part in rel_parts
                        for src_indicator in ["src", "lib", "core", "app", "api"]
                    ):
                        continue

                # Skip binary/media files
                if f.suffix.lower() in skip_extensions:
                    continue

                filtered.append(f)
            except ValueError:
                # File outside base path, include it
                filtered.append(f)

        return filtered

    def _sort_by_mtime(self, files: List[Path]) -> List[Path]:
        """Sort files by modification time (newest first)."""

        def get_mtime(f: Path) -> float:
            try:
                return f.stat().st_mtime
            except OSError:
                return 0

        return sorted(files, key=get_mtime, reverse=True)

    def _display_results(self, files: List[str], total_count: int, truncated: bool) -> None:
        """Display results in console."""
        if not files:
            self.console.print("[dim]No matching files found[/dim]")
            return

        # Create table
        table = Table(title=f"Matching Files ({total_count})")
        table.add_column("File", style="cyan")

        # Show up to 30 files
        display_count = min(30, len(files))
        for f in files[:display_count]:
            table.add_row(f)

        if len(files) > display_count:
            table.add_row(f"[dim]... and {len(files) - display_count} more[/dim]")

        self.console.print(table)

        if truncated:
            self.console.print(
                f"[yellow]Results truncated. {total_count - len(files)} files not shown.[/yellow]"
            )
