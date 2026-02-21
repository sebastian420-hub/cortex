"""
AST Service - Central service for AST parsing and analysis.

Provides cached AST parsing, query execution, and code analysis
with tree-sitter integration.
"""

import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from functools import lru_cache

from .parser import ASTParser
from .cache import ASTCache
from .queries import ASTQueries
from .languages import LanguageManager, detect_language, SUPPORTED_LANGUAGES
from .models import FunctionInfo, ClassInfo, ImportInfo, CodeBlock

logger = logging.getLogger(__name__)


# Data classes are now defined in models.py


class ASTService:
    """
    Central AST parsing and analysis service with caching.

    Provides:
    - Cached AST parsing with file change detection
    - Multi-language support
    - Common code analysis operations
    - Query execution on ASTs
    """

    def __init__(self, cache_size: int = 100, enable_cache: bool = True):
        """
        Initialize AST service.

        Args:
            cache_size: Maximum number of ASTs to cache
            enable_cache: Whether to enable caching
        """
        self.parser = ASTParser()
        self.language_manager = LanguageManager()
        self.enable_cache = enable_cache

        if enable_cache:
            self.cache = ASTCache(max_size=cache_size)
        else:
            self.cache = None

        self.queries = ASTQueries(self.parser)

        logger.info(
            f"AST Service initialized with cache_size={cache_size}, enable_cache={enable_cache}"
        )

    def parse_file(
        self, file_path: Union[str, Path], language: Optional[str] = None
    ) -> Optional[Any]:
        """
        Parse file into AST with caching.

        Args:
            file_path: Path to the file
            language: Programming language (auto-detected if None)

        Returns:
            Parsed AST or None if parsing fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return None

        # Auto-detect language if not specified
        if language is None:
            language = detect_language(file_path)
            if language not in SUPPORTED_LANGUAGES:
                logger.warning(f"Unsupported language for {file_path}: {language}")
                return None

        # Check cache if enabled
        if self.enable_cache and self.cache:
            cached_ast = self.cache.get(file_path, language)
            if cached_ast is not None:
                logger.debug(f"Using cached AST for {file_path}")
                return cached_ast

        # Parse file
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            ast = self.parser.parse(content, language)

            # Cache if enabled
            if self.enable_cache and self.cache and ast is not None:
                self.cache.put(file_path, language, ast)
                logger.debug(f"Cached AST for {file_path}")

            return ast

        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return None

    def get_file_hash(self, file_path: Path) -> str:
        """Get hash of file contents for change detection."""
        try:
            content = file_path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash {file_path}: {e}")
            return ""

    def extract_functions(
        self, file_path: Union[str, Path], language: Optional[str] = None
    ) -> List[FunctionInfo]:
        """
        Extract all function definitions from a file.

        Args:
            file_path: Path to the file
            language: Programming language

        Returns:
            List of FunctionInfo objects
        """
        ast = self.parse_file(file_path, language)
        if ast is None:
            return []

        return self.queries.extract_functions(ast, language)

    def extract_classes(
        self, file_path: Union[str, Path], language: Optional[str] = None
    ) -> List[ClassInfo]:
        """
        Extract all class definitions from a file.

        Args:
            file_path: Path to the file
            language: Programming language

        Returns:
            List of ClassInfo objects
        """
        ast = self.parse_file(file_path, language)
        if ast is None:
            return []

        return self.queries.extract_classes(ast, language)

    def extract_imports(
        self, file_path: Union[str, Path], language: Optional[str] = None
    ) -> List[ImportInfo]:
        """
        Extract all import statements from a file.

        Args:
            file_path: Path to the file
            language: Programming language

        Returns:
            List of ImportInfo objects
        """
        ast = self.parse_file(file_path, language)
        if ast is None:
            return []

        return self.queries.extract_imports(ast, language)

    def find_symbol(
        self, file_path: Union[str, Path], symbol: str, language: Optional[str] = None
    ) -> List[Tuple[int, int]]:
        """
        Find all occurrences of a symbol in a file.

        Args:
            file_path: Path to the file
            symbol: Symbol name to find
            language: Programming language

        Returns:
            List of (line, column) positions
        """
        ast = self.parse_file(file_path, language)
        if ast is None:
            return []

        return self.queries.find_symbol(ast, language, symbol)

    def query(
        self, file_path: Union[str, Path], query_pattern: str, language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a tree-sitter query on a file.

        Args:
            file_path: Path to the file
            query_pattern: Tree-sitter query pattern
            language: Programming language

        Returns:
            List of query matches
        """
        ast = self.parse_file(file_path, language)
        if ast is None:
            return []

        return self.queries.execute_query(ast, language, query_pattern)

    def get_function_at_position(
        self, file_path: Union[str, Path], line: int, column: int, language: Optional[str] = None
    ) -> Optional[FunctionInfo]:
        """
        Get the function that contains the given position.

        Args:
            file_path: Path to the file
            line: Line number (1-indexed)
            column: Column number (1-indexed)
            language: Programming language

        Returns:
            FunctionInfo if position is inside a function, None otherwise
        """
        ast = self.parse_file(file_path, language)
        if ast is None:
            return None

        return self.queries.get_function_at_position(ast, language, line, column)

    def get_code_block(
        self,
        file_path: Union[str, Path],
        start_line: int,
        end_line: int,
        language: Optional[str] = None,
    ) -> Optional[str]:
        """
        Extract a code block with proper indentation.

        Args:
            file_path: Path to the file
            start_line: Start line (1-indexed)
            end_line: End line (1-indexed)
            language: Programming language

        Returns:
            Code block as string or None if extraction fails
        """
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")

            if start_line < 1 or end_line > len(lines) or start_line > end_line:
                return None

            # Extract the block
            block_lines = lines[start_line - 1 : end_line]

            # Find minimum indentation
            min_indent = float("inf")
            for line in block_lines:
                if line.strip():  # Skip empty lines
                    indent = len(line) - len(line.lstrip())
                    min_indent = min(min_indent, indent)

            # Remove common indentation
            if min_indent < float("inf"):
                block_lines = [
                    line[min_indent:] if len(line) >= min_indent else line for line in block_lines
                ]

            return "\n".join(block_lines)

        except Exception as e:
            logger.error(f"Failed to extract code block from {file_path}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the AST cache."""
        if self.cache is not None:
            self.cache.clear()
            logger.info("AST cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self.cache is not None:
            return self.cache.get_stats()
        return {"enabled": False, "size": 0, "hits": 0, "misses": 0}

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        return list(SUPPORTED_LANGUAGES.keys())
