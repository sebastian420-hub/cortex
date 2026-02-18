"""Cross-platform Grep tool with ripgrep and Python fallback"""

import re
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any, Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from .base import Tool
from ..core.security import validate_path, SecurityError
from ..utils.errors import create_error_response, create_success_response, ErrorType


class GrepTool(Tool):
    """
    Powerful search tool built on ripgrep with Python fallback.

    Features:
    - Cross-platform (Windows, macOS, Linux)
    - Regex pattern support
    - Multiple output modes (files_with_matches, content, count)
    - File filtering by glob pattern or file type
    - Context lines (before/after)
    - Case sensitivity options
    - Multiline matching
    - Pure Python fallback when ripgrep unavailable
    """

    timeout_category = "search"
    default_timeout = 30

    # Cache ripgrep availability
    _ripgrep_available: Optional[bool] = None

    def execute(
        self,
        pattern: str,
        path: str = ".",
        glob: Optional[str] = None,
        file_type: Optional[str] = None,
        output_mode: str = "files_with_matches",
        case_insensitive: bool = False,
        context_before: int = 0,
        context_after: int = 0,
        context: int = 0,
        multiline: bool = False,
        head_limit: int = 100,
        offset: int = 0,
        show_line_numbers: bool = True,
    ) -> Dict[str, Any]:
        """
        Search for pattern in files.

        Args:
            pattern: Regex pattern to search for
            path: Directory or file to search in (default: current directory)
            glob: Glob pattern to filter files (e.g., "*.py", "*.{ts,tsx}")
            file_type: File type to search (e.g., "py", "js", "rust")
            output_mode: "files_with_matches", "content", or "count"
            case_insensitive: Case insensitive search (default: False)
            context_before: Lines to show before match (-B)
            context_after: Lines to show after match (-A)
            context: Lines to show before and after match (-C)
            multiline: Enable multiline matching (default: False)
            head_limit: Limit results (default: 100 to prevent context overflow, 0 for unlimited)
            offset: Skip first N results (default: 0)
            show_line_numbers: Show line numbers in content mode (default: True)

        Returns:
            Standardized response with search results
        """
        if self.console:
            self.console.print(f"[cyan]Searching for:[/cyan] '{pattern}'")

        # Validate path
        try:
            full_path = validate_path(self.project_dir, path)
        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY, {"path": path})

        if not full_path.exists():
            return create_error_response(
                f"Path not found: {path}", ErrorType.NOT_FOUND, {"path": path}
            )

        # Validate output mode
        valid_modes = ["files_with_matches", "content", "count"]
        if output_mode not in valid_modes:
            return create_error_response(
                f"Invalid output_mode: {output_mode}. Must be one of: {valid_modes}",
                ErrorType.VALIDATION,
                {"output_mode": output_mode},
            )

        # Use context if specified (overrides context_before/after)
        if context > 0:
            context_before = context
            context_after = context

        # Try native Rust search first, then ripgrep, then Python fallback
        result = None

        # Phase 2: Rust native search via feature flag
        rust_failed = False
        try:
            from ..core.feature_flags import FeatureFlag, FeatureManager

            fm = FeatureManager.get_instance()
            if fm.is_enabled(FeatureFlag.RUST_SEARCH):
                result = self._search_with_rust(
                    pattern, full_path, glob, file_type, output_mode,
                    case_insensitive, context_before, context_after,
                    multiline, head_limit, offset,
                )
                if result and not result.get("success"):
                    rust_failed = True
                    if self.console:
                        self.console.print("[dim]Rust search failed, falling back...[/dim]")
                    result = None # Reset result to trigger fallback
        except (ImportError, Exception):
            pass

        if result is None:
            if self._has_ripgrep():
                result = self._search_with_ripgrep(
                    pattern,
                    full_path,
                    glob,
                    file_type,
                    output_mode,
                    case_insensitive,
                    context_before,
                    context_after,
                    multiline,
                    head_limit,
                    offset,
                    show_line_numbers,
                )
            else:
                result = self._search_with_python(
                    pattern,
                    full_path,
                    glob,
                    file_type,
                    output_mode,
                    case_insensitive,
                    multiline,
                    head_limit,
                    offset,
                    show_line_numbers,
                    context_before,
                    context_after,
                )

        # Display results
        if result.get("success") and self.console:
            self._display_results(result, output_mode)

        return result

    def _search_with_rust(
        self, pattern, path, glob_filter, file_type, output_mode,
        case_insensitive, context_before, context_after, multiline,
        head_limit, offset,
    ) -> Optional[Dict[str, Any]]:
        """Search using native Rust extension (cortex_native)."""
        try:
            from ..native import native_search, NATIVE_AVAILABLE

            if not NATIVE_AVAILABLE or native_search is None:
                return None

            result = native_search(
                pattern=pattern,
                path=str(path),
                glob_filter=glob_filter,
                file_type=file_type,
                case_insensitive=case_insensitive,
                multiline=multiline,
                context_before=context_before,
                context_after=context_after,
                output_mode=output_mode,
                head_limit=head_limit,
                offset=offset,
            )

            # Convert native SearchResult to standard tool result format
            if output_mode == "files_with_matches":
                content = "\n".join(m.path for m in result.matches)
            elif output_mode == "content":
                lines = []
                for m in result.matches:
                    prefix = f"{m.path}:{m.line_number}:" if m.line_number else f"{m.path}:"
                    lines.append(f"{prefix}{m.content or ''}")
                content = "\n".join(lines)
            elif output_mode == "count":
                lines = [f"{m.path}:{m.count}" for m in result.matches]
                content = "\n".join(lines)
            else:
                content = str(result)

            return create_success_response(
                content,
                {
                    "total_matches": result.total_matches,
                    "files_searched": result.files_searched,
                    "files_matched": result.files_matched,
                    "duration_ms": result.duration_ms,
                    "engine": "rust_native",
                },
            )
        except Exception as e:
            return {"success": False, "error": "Rust search failed", "details": str(e)}

    def _has_ripgrep(self) -> bool:
        """Check if ripgrep is available on this system."""
        if GrepTool._ripgrep_available is not None:
            return GrepTool._ripgrep_available

        try:
            subprocess.run(["rg", "--version"], capture_output=True, timeout=5)
            GrepTool._ripgrep_available = True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            GrepTool._ripgrep_available = False

        return GrepTool._ripgrep_available

    def _search_with_ripgrep(
        self,
        pattern: str,
        path: Path,
        glob: Optional[str],
        file_type: Optional[str],
        output_mode: str,
        case_insensitive: bool,
        context_before: int,
        context_after: int,
        multiline: bool,
        head_limit: int,
        offset: int,
        show_line_numbers: bool,
    ) -> Dict[str, Any]:
        """Use ripgrep for fast searching."""
        args = ["rg", "--no-heading", "--with-filename"]

        # Output mode
        if output_mode == "files_with_matches":
            args.append("-l")
        elif output_mode == "count":
            args.append("-c")
        # else: content mode (default behavior)

        # Line numbers
        if show_line_numbers and output_mode == "content":
            args.append("-n")

        # Options
        if case_insensitive:
            args.append("-i")

        if multiline:
            args.extend(["-U", "--multiline-dotall"])

        if context_before > 0 and output_mode == "content":
            args.extend(["-B", str(context_before)])

        if context_after > 0 and output_mode == "content":
            args.extend(["-A", str(context_after)])

        if glob:
            args.extend(["-g", glob])

        if file_type:
            args.extend(["-t", file_type])

        # Add pattern and path
        args.append(pattern)
        args.append(str(path))

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.get_timeout(),
                cwd=str(self.project_dir),
            )

            output = result.stdout

            if not output.strip():
                return create_success_response(
                    {"results": [], "match_count": 0, "message": "[ripgrep] No matches found"}
                )

            # Parse output
            lines = output.strip().split("\n")

            # Apply offset and limit
            if offset > 0:
                lines = lines[offset:]
            if head_limit > 0:
                total = len(lines)
                lines = lines[:head_limit]
                truncated = total > head_limit
            else:
                truncated = False

            return create_success_response(
                {
                    "results": lines,
                    "match_count": len(lines),
                    "truncated": truncated,
                    "engine": "ripgrep",
                }
            )

        except subprocess.TimeoutExpired:
            return create_error_response(
                f"Search timed out after {self.get_timeout()} seconds",
                ErrorType.TIMEOUT,
                {"pattern": pattern, "path": str(path)},
            )
        except Exception as e:
            # Fall back to Python on any ripgrep error
            return self._search_with_python(
                pattern,
                path,
                glob,
                file_type,
                output_mode,
                case_insensitive,
                multiline,
                head_limit,
                offset,
                show_line_numbers,
                context_before,
                context_after,
            )

    def _search_with_python(
        self,
        pattern: str,
        path: Path,
        glob_pattern: Optional[str],
        file_type: Optional[str],
        output_mode: str,
        case_insensitive: bool,
        multiline: bool,
        head_limit: int,
        offset: int,
        show_line_numbers: bool,
        context_before: int = 0,
        context_after: int = 0,
    ) -> Dict[str, Any]:
        """Pure Python fallback for systems without ripgrep."""

        # Compile regex
        flags = 0
        if case_insensitive:
            flags |= re.IGNORECASE
        if multiline:
            flags |= re.MULTILINE | re.DOTALL

        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return create_error_response(
                f"Invalid regex pattern: {e}", ErrorType.VALIDATION, {"pattern": pattern}
            )

        # Find files to search
        files = self._find_files(path, glob_pattern, file_type)

        results: List[str] = []
        file_match_counts: Dict[str, int] = {}

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8-sig", errors="ignore")
                lines = content.split("\n")

                if multiline:
                    # Multiline search - match across lines
                    matches = list(regex.finditer(content))
                    if matches:
                        rel_path = str(file_path.relative_to(self.project_dir))
                        file_match_counts[rel_path] = len(matches)

                        if output_mode == "files_with_matches":
                            results.append(rel_path)
                        elif output_mode == "content":
                            for match in matches:
                                # Find line number
                                line_num = content[: match.start()].count("\n") + 1
                                matched_text = match.group()
                                # Truncate long matches
                                if len(matched_text) > 200:
                                    matched_text = matched_text[:200] + "..."
                                if show_line_numbers:
                                    results.append(f"{rel_path}:{line_num}: {matched_text}")
                                else:
                                    results.append(f"{rel_path}: {matched_text}")
                else:
                    # Line-by-line search
                    matched_lines = []
                    for i, line in enumerate(lines, 1):
                        if regex.search(line):
                            matched_lines.append((i, line))

                    if matched_lines:
                        rel_path = str(file_path.relative_to(self.project_dir))
                        file_match_counts[rel_path] = len(matched_lines)

                        if output_mode == "files_with_matches":
                            results.append(rel_path)
                        elif output_mode == "content":
                            for line_num, line_content in matched_lines:
                                # Add context if requested
                                if context_before > 0 or context_after > 0:
                                    start = max(0, line_num - 1 - context_before)
                                    end = min(len(lines), line_num + context_after)
                                    for ctx_line_num in range(start, end):
                                        prefix = "--" if ctx_line_num != line_num - 1 else ""
                                        if show_line_numbers:
                                            results.append(
                                                f"{rel_path}:{ctx_line_num + 1}{prefix}: {lines[ctx_line_num]}"
                                            )
                                        else:
                                            results.append(
                                                f"{rel_path}{prefix}: {lines[ctx_line_num]}"
                                            )
                                else:
                                    if show_line_numbers:
                                        results.append(f"{rel_path}:{line_num}: {line_content}")
                                    else:
                                        results.append(f"{rel_path}: {line_content}")

            except (PermissionError, OSError, UnicodeDecodeError):
                # Skip files we can't read
                continue

        # Handle count mode
        if output_mode == "count":
            results = [f"{path}: {count}" for path, count in file_match_counts.items()]

        # Apply offset and limit
        total_results = len(results)
        if offset > 0:
            results = results[offset:]
        if head_limit > 0:
            results = results[:head_limit]
            truncated = total_results > offset + head_limit
        else:
            truncated = False

        if not results:
            return create_success_response(
                {"results": [], "match_count": 0, "message": "[python] No matches found"}
            )

        return create_success_response(
            {
                "results": results,
                "match_count": len(results),
                "total_matches": total_results,
                "truncated": truncated,
                "engine": "python",
            }
        )

    def _find_files(
        self, path: Path, glob_pattern: Optional[str], file_type: Optional[str]
    ) -> List[Path]:
        """Find files to search based on filters."""

        # File type to extension mapping
        type_extensions = {
            "py": ["*.py"],
            "python": ["*.py"],
            "js": ["*.js", "*.jsx"],
            "javascript": ["*.js", "*.jsx"],
            "ts": ["*.ts", "*.tsx"],
            "typescript": ["*.ts", "*.tsx"],
            "rust": ["*.rs"],
            "go": ["*.go"],
            "java": ["*.java"],
            "c": ["*.c", "*.h"],
            "cpp": ["*.cpp", "*.hpp", "*.cc", "*.hh", "*.cxx"],
            "cs": ["*.cs"],
            "rb": ["*.rb"],
            "ruby": ["*.rb"],
            "php": ["*.php"],
            "swift": ["*.swift"],
            "kotlin": ["*.kt", "*.kts"],
            "scala": ["*.scala"],
            "md": ["*.md", "*.markdown"],
            "json": ["*.json"],
            "yaml": ["*.yaml", "*.yml"],
            "xml": ["*.xml"],
            "html": ["*.html", "*.htm"],
            "css": ["*.css", "*.scss", "*.sass", "*.less"],
            "sql": ["*.sql"],
            "sh": ["*.sh", "*.bash"],
            "ps1": ["*.ps1"],
        }

        if path.is_file():
            return [path]

        files: List[Path] = []

        # Determine patterns to use
        patterns = []
        if glob_pattern:
            patterns.append(glob_pattern)
        elif file_type and file_type.lower() in type_extensions:
            patterns.extend(type_extensions[file_type.lower()])
        else:
            # Search all text-like files
            patterns = ["*"]

        # Collect files
        for pat in patterns:
            if "**" in pat:
                files.extend(path.glob(pat))
            else:
                files.extend(path.rglob(pat))

        # Filter to actual files (not directories) and skip hidden/binary
        filtered = []
        for f in files:
            if not f.is_file():
                continue
            # Skip hidden files and common binary/generated directories
            parts = f.relative_to(path).parts
            skip_dirs = {
                ".git",
                ".svn",
                ".hg",
                "node_modules",
                "__pycache__",
                ".venv",
                "venv",
                ".tox",
                ".eggs",
                "dist",
                "build",
                ".mypy_cache",
                ".pytest_cache",
                ".coverage",
            }
            if any(part.startswith(".") or part in skip_dirs for part in parts):
                continue
            # Skip likely binary files
            binary_extensions = {
                ".pyc",
                ".pyo",
                ".so",
                ".dll",
                ".exe",
                ".bin",
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".ico",
                ".pdf",
                ".zip",
                ".tar",
                ".gz",
                ".7z",
                ".whl",
                ".egg",
            }
            if f.suffix.lower() in binary_extensions:
                continue
            filtered.append(f)

        return filtered

    def _display_results(self, result: Dict[str, Any], output_mode: str) -> None:
        """Display search results in console."""
        # Handle both wrapped (data key) and unwrapped result formats
        data = result.get("data", result)
        results = data.get("results", [])

        if not results:
            self.console.print("[dim]No matches found[/dim]")
            return

        # Format output based on mode
        if output_mode == "files_with_matches":
            output = "\n".join(results)
            self.console.print(
                Panel(output, title=f"Matching Files ({len(results)})", border_style="cyan")
            )
        elif output_mode == "count":
            output = "\n".join(results)
            self.console.print(Panel(output, title="Match Counts", border_style="cyan"))
        else:
            # Content mode - show with syntax highlighting hints
            output = "\n".join(results[:30])  # Limit display
            if len(results) > 30:
                output += f"\n... and {len(results) - 30} more matches"
            self.console.print(
                Panel(
                    output,
                    title=f"Search Results ({result.get('match_count', 0)} matches)",
                    border_style="cyan",
                )
            )

        # Show if truncated
        if result.get("truncated"):
            self.console.print("[dim]Results truncated. Use offset/head_limit to paginate.[/dim]")

        # Show engine used
        engine = result.get("engine", "unknown")
        self.console.print(f"[dim]Search engine: {engine}[/dim]")
