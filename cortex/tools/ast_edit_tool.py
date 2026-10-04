"""AST-driven refactoring tool"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from .base import Tool
from ..core.security import validate_path, SecurityError
from ..models import PermissionMode
from ..utils.errors import (
    create_error_response,
    create_success_response,
    create_permission_denial,
    ErrorType,
)
from ..code_ast.service import ASTService
from ..code_ast.models import FunctionInfo, ClassInfo, QueryResult
from ..cache import invalidate_file

logger = logging.getLogger(__name__)

# Directories that are never searched for other uses of a renamed symbol
_SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env", "site-packages",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea", ".vscode",
    "target",
}  # fmt: skip
_MAX_FILES_SCANNED = 5000
_MAX_FILE_BYTES = 1_000_000
_MAX_FILES_LISTED = 20
# A rename in .py also matters to other .py files, and so on for the JS/TS family
_EXTENSION_GROUPS = (
    {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"},
    {".c", ".h"},
    {".cc", ".cpp", ".cxx", ".hpp", ".hh", ".h"},
)
_RENAME_SCOPES = ("file",)


class ASTEditTool(Tool):
    """
    AST-driven refactoring tool for precise code modifications.

    Capabilities:
    - Rename symbols (functions, classes, variables) across a file
    - Replace function/class bodies while preserving signatures
    - Verifies syntax after every edit to prevent "broken builds"
    """

    timeout_category = "file"
    default_timeout = 45

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ast_service = ASTService(enable_cache=False)

    def execute(
        self,
        file_path: str,
        action: str,
        symbol_name: str,
        new_name: Optional[str] = None,
        new_content: Optional[str] = None,
        scope: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute AST-driven refactoring.

        Args:
            file_path: Path to the file
            action: Refactoring action ('rename_symbol', 'replace_block')
            symbol_name: Name of the symbol to refactor
            new_name: New name for renaming
            new_content: New content for block replacement
            scope: 'file' renames only in this file even if other files use the symbol. Without
                it, a rename is refused when other files mention the symbol.

        Returns:
            Standardized response
        """
        # Validate path
        try:
            full_path = validate_path(self.project_dir, file_path)
        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY, {"file_path": file_path})

        if not full_path.exists():
            return create_error_response(
                f"File not found: {file_path}", ErrorType.NOT_FOUND, {"file_path": file_path}
            )

        # Check permissions
        if not self.check_permission(f"Refactor {symbol_name} in {file_path}"):
            return create_permission_denial(
                "Plan mode - no refactoring allowed", action, {"file_path": file_path}
            )

        # Dispatch action
        if action == "rename_symbol":
            if not new_name:
                return create_error_response(
                    "new_name is required for rename_symbol", ErrorType.VALIDATION
                )
            if scope is not None and scope not in _RENAME_SCOPES:
                return create_error_response(
                    f"Unsupported scope '{scope}'. The only supported scope is 'file'.",
                    ErrorType.VALIDATION,
                    {"scope": scope},
                )
            return self._rename_symbol(full_path, symbol_name, new_name, scope)
        elif action == "replace_block":
            if not new_content:
                return create_error_response(
                    "new_content is required for replace_block", ErrorType.VALIDATION
                )
            return self._replace_block(full_path, symbol_name, new_content)
        else:
            return create_error_response(f"Unsupported action: {action}", ErrorType.VALIDATION)

    def _other_files_mentioning(self, file_path: Path, symbol: str) -> List[str]:
        """Project files, other than ``file_path``, that mention ``symbol`` as a whole word.

        Only files of the same language family are searched, and vendored/cache directories are
        skipped. A whole-word text match is deliberately broader than an AST reference (it also
        finds comments and strings): a rename that is refused too often costs one extra argument,
        a rename that breaks an import costs a debugging session.
        """
        suffix = file_path.suffix.lower()
        family = next((group for group in _EXTENSION_GROUPS if suffix in group), {suffix})
        pattern = re.compile(r"(?<![\w$])" + re.escape(symbol) + r"(?![\w$])")
        root = self.project_dir.resolve()
        target = file_path.resolve()

        found: List[str] = []
        scanned = 0
        for current, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not d.startswith("."))
            for name in sorted(files):
                path = Path(current) / name
                if path.suffix.lower() not in family or path.resolve() == target:
                    continue
                scanned += 1
                if scanned > _MAX_FILES_SCANNED:
                    return found
                try:
                    if path.stat().st_size > _MAX_FILE_BYTES:
                        continue
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if pattern.search(text):
                    found.append(path.relative_to(root).as_posix())
        return found

    def _rename_symbol(
        self, file_path: Path, old_name: str, new_name: str, scope: Optional[str] = None
    ) -> Dict[str, Any]:
        """Rename all occurrences of a symbol in a file."""
        try:
            # Parse AST
            ast = self.ast_service.parse_file(file_path)
            if ast is None:
                return create_error_response("Failed to parse file", ErrorType.EXECUTION)

            language = self.ast_service.parser.detect_language(
                file_path
            )  # Needs update in parser too?
            # Actually detect_language is in .languages
            from ..code_ast.languages import detect_language

            language = detect_language(file_path)

            # Find all nodes for this symbol
            nodes = self.ast_service.queries.find_symbol_nodes(ast, language, old_name)
            if not nodes:
                return create_error_response(
                    f"Symbol '{old_name}' not found in {file_path}", ErrorType.NOT_FOUND
                )

            # A rename that leaves other files pointing at the old name breaks them. Refuse,
            # unless the caller said they want this file only.
            if scope != "file":
                others = self._other_files_mentioning(file_path, old_name)
                if others:
                    listed = ", ".join(others[:_MAX_FILES_LISTED])
                    more = (
                        f" (and {len(others) - _MAX_FILES_LISTED} more)"
                        if len(others) > _MAX_FILES_LISTED
                        else ""
                    )
                    return create_error_response(
                        f"Refusing to rename '{old_name}': it is also mentioned in "
                        f"{len(others)} other file(s): {listed}{more}. Renaming only "
                        f"{file_path.name} would leave them using the old name. Update those "
                        f"files as well, or pass scope='file' to rename just this file.",
                        ErrorType.VALIDATION,
                        {
                            "symbol": old_name,
                            "other_files": others[:_MAX_FILES_LISTED],
                            "other_file_count": len(others),
                            "scope_hint": "file",
                        },
                    )

            # Read content
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)

            # Apply replacements from bottom to top to preserve offsets
            # Need to convert (line, col) to byte offsets or work line by line
            # Working line by line is safer for simple renames

            # Sort nodes by line and column descending
            nodes.sort(key=lambda x: (x.start_line, x.start_column), reverse=True)

            modified_lines = list(lines)
            for node in nodes:
                l_idx = node.start_line - 1
                start_c = node.start_column - 1
                end_c = node.end_column - 1

                line = modified_lines[l_idx]
                modified_line = line[:start_c] + new_name + line[end_c:]
                modified_lines[l_idx] = modified_line

            new_content = "".join(modified_lines)

            # Verify syntax
            if not self._verify_syntax(new_content, language):
                return create_error_response(
                    "Refactoring would introduce syntax errors. Aborting.", ErrorType.EXECUTION
                )

            # Save file
            self.backup_file(file_path, "edit")
            file_path.write_text(new_content, encoding="utf-8")
            invalidate_file(file_path)

            return create_success_response(
                {
                    "file_path": str(file_path),
                    "action": "rename_symbol",
                    "symbol": old_name,
                    "new_name": new_name,
                    "occurrences": len(nodes),
                }
            )

        except Exception as e:
            logger.error(f"Rename failed: {e}")
            return create_error_response(str(e), ErrorType.EXECUTION)

    def _replace_block(self, file_path: Path, symbol_name: str, new_content: str) -> Dict[str, Any]:
        """Replace the body of a function or class."""
        try:
            ast = self.ast_service.parse_file(file_path)
            language = self.ast_service.parser.detect_language(file_path)

            # Find the symbol (function or class)
            target = self._find_target_info(ast, language, symbol_name)
            if not target:
                return create_error_response(
                    f"Function or Class '{symbol_name}' not found", ErrorType.NOT_FOUND
                )

            # Read content
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)

            # Replace the block
            start_l = target.start_line - 1
            end_l = target.end_line - 1
            start_c = target.start_column - 1
            end_c = target.end_column - 1

            # Build the new content
            # Everything before the block start
            prefix = "".join(lines[:start_l])
            if start_l < len(lines):
                prefix += lines[start_l][:start_c]

            # Everything after the block end
            suffix = ""
            if end_l < len(lines):
                suffix += lines[end_l][end_c:]
            suffix += "".join(lines[end_l + 1 :])

            final_content = prefix + new_content + suffix

            # Verify syntax
            if not self._verify_syntax(final_content, language):
                # For debugging: print the content that failed
                logger.error(f"Syntax verification failed for {file_path}")
                return create_error_response(
                    "Block replacement would introduce syntax errors. Aborting.",
                    ErrorType.EXECUTION,
                )

            # Save file
            self.backup_file(file_path, "edit")
            file_path.write_text(final_content, encoding="utf-8")
            invalidate_file(file_path)

            return create_success_response(
                {
                    "file_path": str(file_path),
                    "action": "replace_block",
                    "symbol": symbol_name,
                }
            )

        except Exception as e:
            logger.error(f"Replace block failed: {e}")
            return create_error_response(str(e), ErrorType.EXECUTION)

    def _find_target_info(
        self, ast: Any, language: str, name: str
    ) -> Optional[Union[FunctionInfo, ClassInfo]]:
        """Find FunctionInfo or ClassInfo by name."""
        # Check functions
        functions = self.ast_service.queries.extract_functions(ast, language)
        for f in functions:
            if f.name == name:
                return f

        # Check classes
        classes = self.ast_service.queries.extract_classes(ast, language)
        for c in classes:
            if c.name == name:
                return c

        return None

    def _verify_syntax(self, content: str, language: str) -> bool:
        """Verify that content is syntactically correct."""
        try:
            tree = self.ast_service.parser.parse(content, language)
            if tree is None:
                logger.error("Parser returned None for content")
                return False
            if tree.root_node.has_error:
                logger.error(f"AST has errors: {tree.root_node.to_sexp()}")
                return False
            return True
        except Exception as e:
            logger.error(f"Syntax verification exception: {e}")
            return False
