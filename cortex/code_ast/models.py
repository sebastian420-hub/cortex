"""
AST Models - Data classes for AST analysis results.

Defines structured data classes for representing parsed code elements.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class FunctionInfo:
    """Information about a function extracted from AST."""

    name: str
    start_line: int
    end_line: int
    parameters: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    return_type: Optional[str] = None


@dataclass
class ClassInfo:
    """Information about a class extracted from AST."""

    name: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)
    methods: List[FunctionInfo] = field(default_factory=list)


@dataclass
class ImportInfo:
    """Information about an import statement extracted from AST."""

    module: str
    line: int
    imports: List[str] = field(default_factory=list)
    alias: Optional[str] = None


@dataclass
class QueryResult:
    """Result of a tree-sitter query."""

    captures: List[Dict[str, Any]]
    text: str
    start_line: int
    end_line: int
    start_column: Optional[int] = None
    end_column: Optional[int] = None


@dataclass
class CodeBlock:
    """A block of code with context."""

    content: str
    start_line: int
    end_line: int
    language: str
    file_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)
