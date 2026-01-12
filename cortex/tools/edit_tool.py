"""Surgical file editing tool"""

import difflib
from pathlib import Path
from typing import Dict, Any, Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm
from rich.text import Text

from .base import Tool
from ..core.security import validate_path, SecurityError
from ..models import PermissionMode
from ..utils.errors import (
    create_error_response,
    create_success_response,
    create_permission_denial,
    ErrorType,
)
from ..cache import invalidate_file


class EditTool(Tool):
    """
    Surgical string replacement tool for precise file editing.

    Features:
    - Exact string matching and replacement
    - Uniqueness validation (prevents ambiguous edits)
    - Replace all occurrences option
    - Diff preview before changes
    - Permission-aware (respects PLAN/NORMAL/AUTO_APPROVE modes)
    """

    timeout_category = "file"
    default_timeout = 30

    def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Replace exact string in file.

        Args:
            file_path: Path to the file to edit
            old_string: The exact text to replace
            new_string: The text to replace it with (must be different)
            replace_all: Replace all occurrences (default: False, requires unique match)

        Returns:
            Standardized response with edit results
        """
        # Check plan mode first
        if self.permission_mode == PermissionMode.PLAN:
            if self.console:
                self.console.print(f"[yellow]PLAN MODE:[/yellow] Would edit {file_path}")
            return create_permission_denial(
                "Plan mode - no edits allowed", "edit", {"file_path": file_path}
            )

        # Validate inputs
        if old_string == new_string:
            return create_error_response(
                "old_string and new_string must be different",
                ErrorType.VALIDATION,
                {"file_path": file_path},
            )

        if not old_string:
            return create_error_response(
                "old_string cannot be empty", ErrorType.VALIDATION, {"file_path": file_path}
            )

        # Validate path
        try:
            full_path = validate_path(self.project_dir, file_path)
        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY, {"file_path": file_path})

        if not full_path.exists():
            return create_error_response(
                f"File not found: {file_path}", ErrorType.NOT_FOUND, {"file_path": file_path}
            )

        if not full_path.is_file():
            return create_error_response(
                f"Path is not a file: {file_path}", ErrorType.VALIDATION, {"file_path": file_path}
            )

        # Read file content
        try:
            content = full_path.read_text(encoding="utf-8-sig")
        except Exception as e:
            return create_error_response(
                f"Failed to read file: {e}", ErrorType.EXECUTION, {"file_path": file_path}
            )

        # Check if old_string exists
        if old_string not in content:
            # Provide helpful hint about potential whitespace issues
            hint = self._get_match_hint(content, old_string)
            return create_error_response(
                f"String not found in file",
                ErrorType.VALIDATION,
                {"file_path": file_path, "hint": hint, "old_string_preview": old_string[:100]},
            )

        # Check uniqueness (unless replace_all)
        count = content.count(old_string)
        if not replace_all and count > 1:
            # Find the locations
            locations = self._find_occurrences(content, old_string)
            return create_error_response(
                f"String appears {count} times in file. Use replace_all=true or provide more context to make it unique.",
                ErrorType.VALIDATION,
                {
                    "file_path": file_path,
                    "occurrence_count": count,
                    "locations": locations[:5],  # Show first 5 locations
                    "hint": "Add more surrounding context to old_string to make it unique",
                },
            )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replacements = count
        else:
            new_content = content.replace(old_string, new_string, 1)
            replacements = 1

        # Verify replacement actually occurred (prevents silent failures)
        if old_string not in new_content and new_content == content:
            # The replacement didn't change anything - old_string must be gone
            # But if new_content == content, it means no replacement occurred
            return create_error_response(
                "Replacement verification failed - old_string not found or replacement had no effect",
                ErrorType.EXECUTION,
                {
                    "file_path": file_path,
                    "hint": "The old_string was not found in the file. Check for whitespace differences (tabs vs spaces) or line ending differences.",
                    "file_preview": content[:500],
                },
            )

        # Show diff preview
        if self.console:
            self._show_diff(file_path, content, new_content, old_string, new_string)

        # Ask for permission in NORMAL mode
        if self.permission_mode == PermissionMode.NORMAL and self.console:
            if not Confirm.ask(f"[bold]Apply edit to {file_path}?[/bold]"):
                if self.console:
                    self.console.print("[red]Cancelled by user[/red]")
                return create_permission_denial(
                    "Edit cancelled by user", "edit", {"file_path": file_path}
                )

        # Backup before edit
        self.backup_file(full_path, "edit")

        # Write file
        try:
            full_path.write_text(new_content)
            # Invalidate cache for this file
            invalidate_file(full_path)
        except Exception as e:
            return create_error_response(
                f"Failed to write file: {e}", ErrorType.EXECUTION, {"file_path": file_path}
            )

        if self.console:
            self.console.print(
                f"[green]Edited {file_path}[/green] ({replacements} replacement{'s' if replacements > 1 else ''})"
            )

        return create_success_response(
            {
                "file": file_path,
                "replacements": replacements,
                "old_string_length": len(old_string),
                "new_string_length": len(new_string),
            }
        )

    def _get_match_hint(self, content: str, search_string: str) -> str:
        """Generate helpful hint when string not found."""
        hints = []

        # Check for common issues
        if "\\n" in search_string:
            hints.append("Literal '\\n' found in search - use actual newlines instead")

        if "\\t" in search_string:
            hints.append("Literal '\\t' found in search - use actual tabs instead")

        # Check for similar strings
        lines = content.split("\n")
        search_lower = search_string.lower().strip()

        for i, line in enumerate(lines):
            if search_lower in line.lower():
                hints.append(f"Similar text found on line {i + 1} (case may differ)")
                break

        # Check for whitespace differences
        if search_string.strip() != search_string:
            hints.append("Search string has leading/trailing whitespace")

        if not hints:
            hints.append(
                "Make sure old_string matches exactly, including indentation and whitespace"
            )

        return "; ".join(hints)

    def _find_occurrences(self, content: str, search_string: str) -> List[Dict[str, Any]]:
        """Find all occurrences of search string with line numbers."""
        occurrences = []
        lines = content.split("\n")
        current_pos = 0

        for line_num, line in enumerate(lines, 1):
            while True:
                pos = line.find(
                    search_string.split("\n")[0] if "\n" in search_string else search_string
                )
                if pos == -1:
                    break
                occurrences.append(
                    {
                        "line": line_num,
                        "column": pos + 1,
                        "preview": line[max(0, pos - 20) : pos + 50].strip(),
                    }
                )
                # For multi-line strings, only find the first match per search
                break
            current_pos += len(line) + 1

        return occurrences

    def _show_diff(
        self, file_path: str, old_content: str, new_content: str, old_string: str, new_string: str
    ) -> None:
        """Show a diff preview of the changes."""
        # Generate unified diff
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
            )
        )

        if diff:
            # Limit diff output
            diff_text = "".join(diff[:50])
            if len(diff) > 50:
                diff_text += f"\n... ({len(diff) - 50} more lines)"

            # Use Syntax for diff highlighting
            syntax = Syntax(diff_text, "diff", theme="monokai")
            self.console.print(
                Panel(syntax, title=f"Changes to {file_path}", border_style="yellow")
            )
        else:
            # Fallback: show simple before/after
            text = Text()
            text.append("- ", style="red")
            text.append(old_string[:100] + ("..." if len(old_string) > 100 else ""), style="red")
            text.append("\n+ ", style="green")
            text.append(new_string[:100] + ("..." if len(new_string) > 100 else ""), style="green")
            self.console.print(Panel(text, title="Changes", border_style="yellow"))
