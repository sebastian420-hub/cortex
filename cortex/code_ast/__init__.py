"""
AST (Abstract Syntax Tree) parsing and analysis module for Cortex.

This module provides tree-sitter based code analysis capabilities for
smart code understanding, structural search, and semantic operations.
"""

from .service import ASTService
from .parser import ASTParser
from .cache import ASTCache
from .queries import ASTQueries
from .languages import LanguageManager, detect_language, SUPPORTED_LANGUAGES

__all__ = [
    "ASTService",
    "ASTParser",
    "ASTCache",
    "ASTQueries",
    "LanguageManager",
    "detect_language",
    "SUPPORTED_LANGUAGES",
]
