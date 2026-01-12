"""File search and listing tools"""

import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .base import Tool
from ..core.security import validate_path, SecurityError
from ..utils.errors import create_error_response, create_success_response, ErrorType


class ListFilesTool(Tool):
    """Tool for listing files in directories"""

    def execute(self, path: str = ".", pattern: Optional[str] = None) -> Dict[str, Any]:
        """List files in directory"""
        try:
            full_path = validate_path(self.project_dir, path)

            if not full_path.exists():
                return create_error_response(
                    f"Path not found: {path}", ErrorType.NOT_FOUND, {"path": path}
                )

            if not full_path.is_dir():
                return create_error_response(
                    f"Path is not a directory: {path}", ErrorType.VALIDATION, {"path": path}
                )

            if pattern:
                files = [str(f.relative_to(full_path)) for f in full_path.rglob(pattern)]
            else:
                files = [f.name for f in full_path.iterdir() if not f.name.startswith(".")]

            # Display as table
            if self.console:
                table = Table(title=f"📁 {path}")
                table.add_column("Files", style="cyan")

                for f in sorted(files)[:30]:
                    table.add_row(f)

                if len(files) > 30:
                    table.add_row(f"[dim]... and {len(files) - 30} more[/dim]")

                self.console.print(table)

            return create_success_response({"files": files, "count": len(files)})

        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY, {"path": path})
        except Exception as e:
            return create_error_response(str(e), ErrorType.EXECUTION, {"path": path})


class SearchFilesTool(Tool):
    """Tool for searching text in files"""

    def execute(self, query: str, file_pattern: Optional[str] = None) -> Dict[str, Any]:
        """Search for text in files"""
        if self.console:
            self.console.print(f"[cyan]🔍 Searching for:[/cyan] '{query}'")

        try:
            # Use ripgrep if available, otherwise fallback to grep
            pattern_arg = f"-g '{file_pattern}'" if file_pattern else ""

            # Try ripgrep first
            try:
                result = subprocess.run(
                    f"rg -n -C 2 {pattern_arg} '{query}'",
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=self.project_dir,
                    timeout=10,
                )
            except:
                # Fallback to grep
                result = subprocess.run(
                    f"grep -rn '{query}' .",
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=self.project_dir,
                    timeout=10,
                )

            output = result.stdout

            if output:
                # Limit output
                output_lines = output.split("\n")
                lines = output_lines[:50]
                preview = "\n".join(lines)
                if len(output_lines) > 50:
                    more_matches = len(output_lines) - 50
                    preview += f"\n... ({more_matches} more matches)"

                if self.console:
                    self.console.print(Panel(preview, title="Search Results", border_style="cyan"))

                return create_success_response(
                    {
                        "results": output,
                        "match_count": len([l for l in output.split("\n") if l.strip()]),
                    }
                )
            else:
                if self.console:
                    self.console.print("[dim]No matches found[/dim]")
                return create_success_response({"results": "", "match_count": 0})

        except subprocess.TimeoutExpired:
            return create_error_response(
                "Search timed out after 10 seconds",
                ErrorType.TIMEOUT,
                {"query": query, "file_pattern": file_pattern},
            )
        except Exception as e:
            return create_error_response(
                str(e), ErrorType.EXECUTION, {"query": query, "file_pattern": file_pattern}
            )
