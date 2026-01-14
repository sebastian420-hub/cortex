"""
AST Extract Tool - Extract code structures using AST parsing.

Provides tools to extract functions, classes, imports, and other
code structures with semantic understanding.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

from ...tools.base import Tool
from ...core.security import validate_path, SecurityError
from ...utils.errors import create_error_response, create_success_response, ErrorType
from ...ast import ASTService, detect_language, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


class ExtractType(Enum):
    """Types of extraction operations."""
    FUNCTION = "function"
    CLASS = "class"
    IMPORT = "import"
    ALL = "all"


class ASTExtractTool(Tool):
    """
    Extract code structures using AST parsing.
    
    Provides semantic extraction of functions, classes, imports,
    and other code structures with proper context.
    """
    
    timeout_category = "extract"
    default_timeout = 30
    
    def __init__(self, *args, **kwargs):
        """Initialize AST extract tool."""
        super().__init__(*args, **kwargs)
        self.ast_service = ASTService(cache_size=50, enable_cache=True)
    
    def execute(
        self,
        path: str,
        extract_type: str = "all",
        pattern: Optional[str] = None,
        include_docstrings: bool = True,
        include_decorators: bool = True,
        include_parameters: bool = True,
        include_return_types: bool = True,
        include_bases: bool = True,
        include_methods: bool = True,
        include_aliases: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract code structures from files.
        
        Args:
            path: Directory or file to extract from
            extract_type: "function", "class", "import", or "all"
            pattern: Optional pattern to filter results
            include_docstrings: Include docstrings in results
            include_decorators: Include decorators in results
            include_parameters: Include function parameters
            include_return_types: Include return types
            include_bases: Include class bases
            include_methods: Include class methods
            include_aliases: Include import aliases
            
        Returns:
            Standardized response with extracted structures
        """
        if self.console:
            self.console.print(f"[cyan]Extracting {extract_type} from:[/cyan] {path}")
        
        # Validate path
        try:
            full_path = validate_path(self.project_dir, path)
        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY, {"path": path})
        
        if not full_path.exists():
            return create_error_response(
                f"Path not found: {path}", ErrorType.NOT_FOUND, {"path": path}
            )
        
        # Validate extract type
        try:
            extract_type_enum = ExtractType(extract_type)
        except ValueError:
            return create_error_response(
                f"Invalid extract_type: {extract_type}. Must be one of: {[t.value for t in ExtractType]}",
                ErrorType.VALIDATION,
                {"extract_type": extract_type},
            )
        
        # Find files to process
        files = self._find_files(full_path)
        
        if not files:
            return create_success_response({
                "extracted": [],
                "file_count": 0,
                "structure_count": 0,
                "message": "No files to process",
            })
        
        results = []
        structure_count = 0
        
        for file_path in files:
            # Detect language
            language = detect_language(file_path)
            if not language or language not in SUPPORTED_LANGUAGES:
                continue
            
            # Extract based on type
            file_results = self._extract_from_file(
                file_path, language, extract_type_enum, pattern,
                include_docstrings, include_decorators, include_parameters,
                include_return_types, include_bases, include_methods, include_aliases
            )
            
            if file_results:
                results.extend(file_results)
                structure_count += len(file_results)
        
        return create_success_response({
            "extracted": results,
            "file_count": len(files),
            "structure_count": structure_count,
            "extract_type": extract_type,
            "pattern": pattern,
        })
    
    def _extract_from_file(
        self,
        file_path: Path,
        language: str,
        extract_type: ExtractType,
        pattern: Optional[str],
        include_docstrings: bool,
        include_decorators: bool,
        include_parameters: bool,
        include_return_types: bool,
        include_bases: bool,
        include_methods: bool,
        include_aliases: bool,
    ) -> List[Dict[str, Any]]:
        """
        Extract structures from a single file.
        
        Args:
            file_path: Path to the file
            language: Programming language
            extract_type: Type of extraction
            pattern: Optional filter pattern
            include_docstrings: Include docstrings
            include_decorators: Include decorators
            include_parameters: Include parameters
            include_return_types: Include return types
            include_bases: Include class bases
            include_methods: Include class methods
            include_aliases: Include import aliases
            
        Returns:
            List of extracted structures
        """
        results = []
        rel_path = str(file_path.relative_to(self.project_dir))
        
        if extract_type in [ExtractType.FUNCTION, ExtractType.ALL]:
            functions = self.ast_service.extract_functions(file_path, language)
            
            for func in functions:
                if pattern and pattern.lower() not in func.name.lower():
                    continue
                
                func_data = {
                    "type": "function",
                    "name": func.name,
                    "file": rel_path,
                    "start_line": func.start_line,
                    "end_line": func.end_line,
                    "parameters": func.parameters if include_parameters else [],
                }
                
                if include_docstrings and func.docstring:
                    func_data["docstring"] = func.docstring
                
                if include_decorators and func.decorators:
                    func_data["decorators"] = func.decorators
                
                if include_return_types and func.return_type:
                    func_data["return_type"] = func.return_type
                
                results.append(func_data)
        
        if extract_type in [ExtractType.CLASS, ExtractType.ALL]:
            classes = self.ast_service.extract_classes(file_path, language)
            
            for cls in classes:
                if pattern and pattern.lower() not in cls.name.lower():
                    continue
                
                class_data = {
                    "type": "class",
                    "name": cls.name,
                    "file": rel_path,
                    "start_line": cls.start_line,
                    "end_line": cls.end_line,
                }
                
                if include_docstrings and cls.docstring:
                    class_data["docstring"] = cls.docstring
                
                if include_decorators and cls.decorators:
                    class_data["decorators"] = cls.decorators
                
                if include_bases and cls.bases:
                    class_data["bases"] = cls.bases
                
                if include_methods and cls.methods:
                    class_data["method_count"] = len(cls.methods)
                    if include_parameters:
                        class_data["methods"] = [
                            {
                                "name": method.name,
                                "parameters": method.parameters,
                                "start_line": method.start_line,
                                "end_line": method.end_line,
                            }
                            for method in cls.methods
                        ]
                
                results.append(class_data)
        
        if extract_type in [ExtractType.IMPORT, ExtractType.ALL]:
            imports = self.ast_service.extract_imports(file_path, language)
            
            for imp in imports:
                if pattern and pattern.lower() not in imp.module.lower():
                    continue
                
                import_data = {
                    "type": "import",
                    "module": imp.module,
                    "file": rel_path,
                    "line": imp.line,
                    "imports": imp.imports,
                }
                
                if include_aliases and imp.alias:
                    import_data["alias"] = imp.alias
                
                results.append(import_data)
        
        return results
    
    def _find_files(self, path: Path) -> List[Path]:
        """
        Find files to process.
        
        Args:
            path: Base path
            
        Returns:
            List of file paths
        """
        if path.is_file():
            return [path]
        
        # Collect all supported code files
        files = []
        
        for lang_config in SUPPORTED_LANGUAGES.values():
            for ext in lang_config['extensions']:
                pattern = f"**/*{ext}"
                files.extend(path.glob(pattern))
        
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
    
    def extract_function(
        self,
        file_path: str,
        function_name: str,
        include_body: bool = False,
        include_context: int = 0,
    ) -> Dict[str, Any]:
        """
        Extract a specific function from a file.
        
        Args:
            file_path: Path to the file
            function_name: Name of function to extract
            include_body: Include function body
            include_context: Lines of context to include
            
        Returns:
            Function information
        """
        full_path = validate_path(self.project_dir, file_path)
        
        if not full_path.exists():
            return create_error_response(
                f"File not found: {file_path}", ErrorType.NOT_FOUND, {"file_path": file_path}
            )
        
        language = detect_language(full_path)
        if not language or language not in SUPPORTED_LANGUAGES:
            return create_error_response(
                f"Unsupported language for file: {file_path}", 
                ErrorType.VALIDATION, 
                {"file_path": file_path}
            )
        
        functions = self.ast_service.extract_functions(full_path, language)
        
        for func in functions:
            if func.name == function_name:
                result = {
                    "name": func.name,
                    "file": file_path,
                    "start_line": func.start_line,
                    "end_line": func.end_line,
                    "parameters": func.parameters,
                    "docstring": func.docstring,
                    "decorators": func.decorators,
                    "return_type": func.return_type,
                }
                
                if include_body:
                    code_block = self.ast_service.get_code_block(
                        full_path, func.start_line, func.end_line, language
                    )
                    if code_block:
                        result["body"] = code_block
                
                return create_success_response(result)
        
        return create_error_response(
            f"Function '{function_name}' not found in {file_path}",
            ErrorType.NOT_FOUND,
            {"function_name": function_name, "file_path": file_path}
        )