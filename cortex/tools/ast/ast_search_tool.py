"""
AST Search Tool - Enhanced search with AST understanding.

Provides smart code search that understands code structure,
enabling precise pattern matching and semantic search.
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

from ...tools.base import Tool
from ...core.security import validate_path, SecurityError
from ...utils.errors import create_error_response, create_success_response, ErrorType
from ...ast import ASTService, detect_language, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


class SearchType(Enum):
    """Types of search operations."""
    TEXT = "text"           # Traditional text search
    STRUCTURE = "structure" # AST pattern matching
    SMART = "smart"         # Auto-detect based on pattern
    FUNCTION = "function"   # Search function definitions
    CLASS = "class"         # Search class definitions
    IMPORT = "import"       # Search import statements


class ASTSearchTool(Tool):
    """
    Enhanced search tool with AST understanding.
    
    Combines traditional text search with AST-based structural search
    for smarter code understanding and more accurate results.
    """
    
    timeout_category = "search"
    default_timeout = 45  # Slightly longer for AST parsing
    
    def __init__(self, *args, **kwargs):
        """Initialize AST search tool."""
        super().__init__(*args, **kwargs)
        self.ast_service = ASTService(cache_size=50, enable_cache=True)
        
        # Patterns that indicate structural search
        self.structural_patterns = [
            r'^def\s+',           # Function definitions
            r'^class\s+',         # Class definitions
            r'^\s*@',             # Decorators
            r'^\s*import\s+',     # Imports
            r'^\s*from\s+',       # From imports
            r'^\s*export\s+',     # Exports
            r'^\s*function\s+',   # JS function
            r'^\s*const\s+',      # JS const
            r'^\s*let\s+',        # JS let
            r'^\s*var\s+',        # JS var
            r'^\s*public\s+',     # Java/C# public
            r'^\s*private\s+',    # Java/C# private
            r'^\s*protected\s+',  # Java/C# protected
            r'^\s*func\s+',       # Go func
            r'^\s*package\s+',    # Go package
            r'^\s*struct\s+',     # Go/Rust struct
            r'^\s*impl\s+',       # Rust impl
            r'^\s*trait\s+',      # Rust trait
            r'^\s*interface\s+',  # Java/Go interface
        ]
    
    def execute(
        self,
        pattern: str,
        path: str = ".",
        search_type: str = "smart",
        file_type: Optional[str] = None,
        output_mode: str = "files_with_matches",
        case_insensitive: bool = False,
        context: int = 0,
        multiline: bool = False,
        head_limit: int = 50,
        offset: int = 0,
        show_line_numbers: bool = True,
    ) -> Dict[str, Any]:
        """
        Search for pattern in files with optional AST understanding.
        
        Args:
            pattern: Pattern to search for
            path: Directory or file to search in
            search_type: "text", "structure", "smart", "function", "class", "import"
            file_type: File type to search (e.g., "py", "js")
            output_mode: "files_with_matches", "content", or "count"
            case_insensitive: Case insensitive search
            context: Lines to show before and after match
            multiline: Enable multiline matching
            head_limit: Limit results (0 for unlimited)
            offset: Skip first N results
            show_line_numbers: Show line numbers in content mode
            
        Returns:
            Standardized response with search results
        """
        if self.console:
            self.console.print(f"[cyan]Searching for:[/cyan] '{pattern}'")
            if search_type != "text":
                self.console.print(f"[dim]Search type: {search_type}[/dim]")
        
        # Validate path
        try:
            full_path = validate_path(self.project_dir, path)
        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY, {"path": path})
        
        if not full_path.exists():
            return create_error_response(
                f"Path not found: {path}", ErrorType.NOT_FOUND, {"path": path}
            )
        
        # Validate search type
        try:
            search_type_enum = SearchType(search_type)
        except ValueError:
            return create_error_response(
                f"Invalid search_type: {search_type}. Must be one of: {[t.value for t in SearchType]}",
                ErrorType.VALIDATION,
                {"search_type": search_type},
            )
        
        # Determine search strategy
        if search_type_enum == SearchType.SMART:
            if self._looks_like_structural_pattern(pattern):
                return self._ast_search(
                    pattern, full_path, file_type, output_mode,
                    context, head_limit, offset, show_line_numbers
                )
            else:
                return self._text_search(
                    pattern, full_path, file_type, output_mode,
                    case_insensitive, context, multiline,
                    head_limit, offset, show_line_numbers
                )
        elif search_type_enum == SearchType.STRUCTURE:
            return self._ast_search(
                pattern, full_path, file_type, output_mode,
                context, head_limit, offset, show_line_numbers
            )
        elif search_type_enum in [SearchType.FUNCTION, SearchType.CLASS, SearchType.IMPORT]:
            return self._structural_search(
                search_type_enum, pattern, full_path, file_type, output_mode,
                context, head_limit, offset, show_line_numbers
            )
        else:  # TEXT
            return self._text_search(
                pattern, full_path, file_type, output_mode,
                case_insensitive, context, multiline,
                head_limit, offset, show_line_numbers
            )
    
    def _looks_like_structural_pattern(self, pattern: str) -> bool:
        """
        Check if pattern looks like a structural code pattern.
        
        Args:
            pattern: Search pattern
            
        Returns:
            True if pattern looks structural
        """
        pattern_lower = pattern.lower()
        
        # Check against structural patterns
        for struct_pattern in self.structural_patterns:
            if re.match(struct_pattern, pattern_lower):
                return True
        
        # Check for common code constructs
        code_keywords = [
            'def ', 'class ', 'import ', 'from ', 'export ',
            'function ', 'const ', 'let ', 'var ', 'public ',
            'private ', 'protected ', 'func ', 'package ',
            'struct ', 'impl ', 'trait ', 'interface ',
            'async ', 'await ', 'throws ', 'extends ',
            'implements ', 'namespace ', 'module ', 'type ',
        ]
        
        for keyword in code_keywords:
            if keyword in pattern_lower:
                return True
        
        return False
    
    def _text_search(
        self,
        pattern: str,
        path: Path,
        file_type: Optional[str],
        output_mode: str,
        case_insensitive: bool,
        context: int,
        multiline: bool,
        head_limit: int,
        offset: int,
        show_line_numbers: bool,
    ) -> Dict[str, Any]:
        """
        Perform traditional text search (fallback).
        
        Uses the existing grep tool for text search.
        """
        # Import existing grep tool
        from ..grep_tool import GrepTool
        
        grep_tool = GrepTool(
            project_dir=self.project_dir,
            permission_mode=self.permission_mode,
            console=self.console
        )
        
        return grep_tool.execute(
            pattern=pattern,
            path=str(path),
            file_type=file_type,
            output_mode=output_mode,
            case_insensitive=case_insensitive,
            context=context,
            multiline=multiline,
            head_limit=head_limit,
            offset=offset,
            show_line_numbers=show_line_numbers,
        )
    
    def _ast_search(
        self,
        pattern: str,
        path: Path,
        file_type: Optional[str],
        output_mode: str,
        context: int,
        head_limit: int,
        offset: int,
        show_line_numbers: bool,
    ) -> Dict[str, Any]:
        """
        Perform AST-based structural search.
        
        Args:
            pattern: Search pattern (can be tree-sitter query or text)
            path: Path to search in
            file_type: File type filter
            output_mode: Output mode
            context: Context lines
            head_limit: Result limit
            offset: Result offset
            show_line_numbers: Show line numbers
            
        Returns:
            Search results
        """
        # Find files to search
        files = self._find_files(path, file_type)
        
        if not files:
            return create_success_response({
                "results": [],
                "match_count": 0,
                "message": "No files to search",
                "engine": "ast",
            })
        
        results = []
        match_count = 0
        
        for file_path in files:
            # Detect language
            language = detect_language(file_path)
            if not language or language not in SUPPORTED_LANGUAGES:
                continue
            
            # Parse file with AST
            ast = self.ast_service.parse_file(file_path, language)
            if ast is None:
                continue
            
            # Try to execute as tree-sitter query
            query_results = self._execute_ast_query(ast, language, pattern, file_path)
            
            if query_results:
                match_count += len(query_results)
                
                if output_mode == "files_with_matches":
                    rel_path = str(file_path.relative_to(self.project_dir))
                    if rel_path not in results:
                        results.append(rel_path)
                elif output_mode == "content":
                    results.extend(query_results)
        
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
            return create_success_response({
                "results": [],
                "match_count": 0,
                "message": "No matches found",
                "engine": "ast",
            })
        
        return create_success_response({
            "results": results,
            "match_count": len(results),
            "total_matches": total_results,
            "truncated": truncated,
            "engine": "ast",
        })
    
    def _structural_search(
        self,
        search_type: SearchType,
        pattern: str,
        path: Path,
        file_type: Optional[str],
        output_mode: str,
        context: int,
        head_limit: int,
        offset: int,
        show_line_numbers: bool,
    ) -> Dict[str, Any]:
        """
        Search for specific structural elements (functions, classes, imports).
        
        Args:
            search_type: Type of structural element to search
            pattern: Pattern to match (optional)
            path: Path to search in
            file_type: File type filter
            output_mode: Output mode
            context: Context lines
            head_limit: Result limit
            offset: Result offset
            show_line_numbers: Show line numbers
            
        Returns:
            Search results
        """
        # Find files to search
        files = self._find_files(path, file_type)
        
        if not files:
            return create_success_response({
                "results": [],
                "match_count": 0,
                "message": "No files to search",
                "engine": "ast",
            })
        
        results = []
        match_count = 0
        
        for file_path in files:
            # Detect language
            language = detect_language(file_path)
            if not language or language not in SUPPORTED_LANGUAGES:
                continue
            
            # Extract structural elements based on search type
            if search_type == SearchType.FUNCTION:
                elements = self.ast_service.extract_functions(file_path, language)
                element_type = "function"
            elif search_type == SearchType.CLASS:
                elements = self.ast_service.extract_classes(file_path, language)
                element_type = "class"
            elif search_type == SearchType.IMPORT:
                elements = self.ast_service.extract_imports(file_path, language)
                element_type = "import"
            else:
                continue
            
            # Filter elements by pattern if provided
            if pattern:
                elements = [e for e in elements if self._matches_pattern(e, pattern, element_type)]
            
            if elements:
                match_count += len(elements)
                rel_path = str(file_path.relative_to(self.project_dir))
                
                if output_mode == "files_with_matches":
                    if rel_path not in results:
                        results.append(rel_path)
                elif output_mode == "content":
                    for element in elements:
                        if element_type == "function":
                            result_text = f"{rel_path}:{element.start_line}: def {element.name}({', '.join(element.parameters)})"
                        elif element_type == "class":
                            result_text = f"{rel_path}:{element.start_line}: class {element.name}"
                        elif element_type == "import":
                            result_text = f"{rel_path}:{element.line}: import {element.module}"
                        
                        if show_line_numbers:
                            results.append(result_text)
                        else:
                            # Remove line number
                            results.append(result_text.split(':', 2)[-1])
        
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
            return create_success_response({
                "results": [],
                "match_count": 0,
                "message": f"No {search_type.value} matches found",
                "engine": "ast",
            })
        
        return create_success_response({
            "results": results,
            "match_count": len(results),
            "total_matches": total_results,
            "truncated": truncated,
            "engine": "ast",
            "search_type": search_type.value,
        })
    
    def _execute_ast_query(self, ast: Any, language: str, pattern: str, file_path: Path) -> List[str]:
        """
        Execute a tree-sitter query on AST.
        
        Args:
            ast: Parsed AST
            language: Programming language
            pattern: Query pattern
            file_path: Path to the file
            
        Returns:
            List of result strings
        """
        try:
            # Try to execute as tree-sitter query
            query_results = self.ast_service.query(file_path, pattern, language)
            
            results = []
            rel_path = str(file_path.relative_to(self.project_dir))
            
            for result in query_results:
                line_info = f"{rel_path}:{result['start_line']}"
                if result['start_column']:
                    line_info += f":{result['start_column']}"
                
                result_text = f"{line_info}: {result['text'][:200]}"
                if len(result['text']) > 200:
                    result_text += "..."
                
                results.append(result_text)
            
            return results
            
        except Exception as e:
            logger.warning(f"Failed to execute AST query: {e}")
            return []
    
    def _matches_pattern(self, element: Any, pattern: str, element_type: str) -> bool:
        """
        Check if element matches pattern.
        
        Args:
            element: Structural element
            pattern: Pattern to match
            element_type: Type of element
            
        Returns:
            True if element matches pattern
        """
        if element_type == "function":
            return pattern.lower() in element.name.lower()
        elif element_type == "class":
            return pattern.lower() in element.name.lower()
        elif element_type == "import":
            return pattern.lower() in element.module.lower()
        return False
    
    def _find_files(self, path: Path, file_type: Optional[str]) -> List[Path]:
        """
        Find files to search based on filters.
        
        Args:
            path: Base path
            file_type: File type filter
            
        Returns:
            List of file paths
        """
        if path.is_file():
            return [path]
        
        # File type to extension mapping (simplified)
        type_extensions = {
            "py": ["*.py"],
            "python": ["*.py"],
            "js": ["*.js", "*.jsx"],
            "javascript": ["*.js", "*.jsx"],
            "ts": ["*.ts", "*.tsx"],
            "typescript": ["*.ts", "*.tsx"],
            "java": ["*.java"],
            "go": ["*.go"],
            "rust": ["*.rs"],
            "c": ["*.c", "*.h"],
            "cpp": ["*.cpp", "*.hpp"],
            "ruby": ["*.rb"],
            "php": ["*.php"],
        }
        
        files = []
        
        # Determine patterns to use
        patterns = []
        if file_type and file_type.lower() in type_extensions:
            patterns.extend(type_extensions[file_type.lower()])
        else:
            # Search all supported code files
            for lang_config in SUPPORTED_LANGUAGES.values():
                patterns.extend([f"*{ext}" for ext in lang_config['extensions']])
        
        # Collect files
        for pat in patterns:
            if "**" in pat:
                files.extend(path.glob(pat))
            else:
                files.extend(path.rglob(pat))
        
        # Filter to actual files and skip hidden/binary
        filtered = []
        for f in files:
            if not f.is_file():
                continue
            
            # Skip hidden files and common binary/generated directories
            parts = f.relative_to(path).parts
            skip_dirs = {
                ".git", ".svn", ".hg", "node_modules", "__pycache__",
                ".pytest_cache", ".mypy_cache", ".coverage", "dist",
                "build", "target", "out", "bin", "obj", ".next",
            }
            
            if any(part.startswith('.') for part in parts):
                continue
            
            if any(part in skip_dirs for part in parts):
                continue
            
            filtered.append(f)
        
        return filtered