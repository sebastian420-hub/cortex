"""
AST Queries - Predefined tree-sitter queries for common code analysis tasks.

Provides query patterns for extracting functions, classes, imports,
and other code structures from ASTs.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from .models import FunctionInfo, ClassInfo, ImportInfo

logger = logging.getLogger(__name__)


class ASTQueries:
    """
    Collection of tree-sitter queries for code analysis.

    Provides predefined queries for common patterns:
    - Function definitions
    - Class definitions
    - Import statements
    - Variable declarations
    - Symbol usage
    """

    # Query patterns by language
    QUERY_PATTERNS = {
        "python": {
            "function": """
                (function_definition
                    name: (identifier) @name
                    parameters: (parameters) @params
                    body: (block) @body
                ) @function
            """,
            "class": """
                (class_definition
                    name: (identifier) @name
                    superclasses: (argument_list)? @bases
                    body: (block) @body
                ) @class
            """,
            "import": """
                (import_statement (dotted_name) @module) @import
                (import_statement (aliased_import (dotted_name) @module (identifier) @alias)) @import_with_alias  # noqa: E501
                (import_from_statement (dotted_name) @module_name (dotted_name) @imported_name) @import_from  # noqa: E501
            """,
            "decorator": """
                (decorator) @decorator
            """,
            "docstring": """
                (expression_statement
                    (string) @docstring
                )
            """,
            "method": """
                (function_definition
                    name: (identifier) @name
                    parameters: (parameters) @params
                    body: (block) @body
                ) @method
            """,
        },
        "javascript": {
            "function": """
                (function_declaration
                    name: (identifier) @name
                    parameters: (formal_parameters) @params
                    body: (statement_block) @body
                ) @function

                (arrow_function
                    parameters: (formal_parameters) @params
                    body: (_) @body
                ) @arrow_function
            """,
            "class": """
                (class_declaration
                    name: (identifier) @name
                    body: (class_body) @body
                ) @class
            """,
            "import": """
                (import_statement
                    source: (string) @source
                    (import_clause) @imports
                ) @import
            """,
            "method": """
                (method_definition
                    name: (property_identifier) @name
                    parameters: (formal_parameters) @params
                    body: (statement_block) @body
                ) @method
            """,
        },
        "typescript": {
            "function": """
                (function_declaration
                    name: (identifier) @name
                    parameters: (formal_parameters) @params
                    type_parameters: (type_parameters)? @type_params
                    return_type: (type_annotation)? @return_type
                    body: (statement_block) @body
                ) @function
            """,
            "class": """
                (class_declaration
                    name: (identifier) @name
                    type_parameters: (type_parameters)? @type_params
                    body: (class_body) @body
                ) @class
            """,
            "interface": """
                (interface_declaration
                    name: (identifier) @name
                    body: (object_type) @body
                ) @interface
            """,
            "import": """
                (import_statement
                    source: (string) @source
                    (import_clause) @imports
                ) @import
            """,
        },
        "java": {
            "method": """
                (method_declaration
                    name: (identifier) @name
                    parameters: (formal_parameters) @params
                    type: (type_identifier) @return_type
                    body: (block) @body
                ) @method
            """,
            "class": """
                (class_declaration
                    name: (identifier) @name
                    body: (class_body) @body
                ) @class
            """,
            "import": """
                (import_declaration
                    name: (scoped_identifier) @import
                ) @import_stmt
            """,
        },
        "go": {
            "function": """
                (function_declaration
                    name: (identifier) @name
                    parameters: (parameter_list) @params
                    result: (type_identifier)? @return_type
                    body: (block) @body
                ) @function
            """,
            "method": """
                (method_declaration
                    receiver: (parameter_list) @receiver
                    name: (field_identifier) @name
                    parameters: (parameter_list) @params
                    result: (type_identifier)? @return_type
                    body: (block) @body
                ) @method
            """,
            "import": """
                (import_declaration
                    (import_spec_list) @imports
                ) @import
            """,
        },
    }

    def __init__(self, parser: Optional[Any] = None):
        """Initialize AST queries.

        Args:
            parser: Optional ASTParser instance to get language objects from
        """
        self.compiled_queries = {}
        self.parser = parser

    def _compile_query(self, language: str, query_name: str) -> Optional[Any]:
        """
        Compile a query for a specific language.

        Args:
            language: Programming language
            query_name: Name of the query pattern

        Returns:
            Compiled query or None if not available
        """
        if language not in self.QUERY_PATTERNS:
            logger.warning(f"No query patterns for language: {language}")
            return None

        if query_name not in self.QUERY_PATTERNS[language]:
            logger.warning(f"No query pattern '{query_name}' for language: {language}")
            return None

        query_pattern = self.QUERY_PATTERNS[language][query_name]

        try:
            # Import tree-sitter if available
            import tree_sitter  # noqa: F401

            # Get language object (this would need to be passed in)
            # For now, we'll compile queries on demand
            return query_pattern

        except ImportError:
            logger.error("tree-sitter not available for query compilation")
            return None

    def _get_language_object(self, language: str) -> Optional[Any]:
        """
        Get tree-sitter Language object for a language.

        Returns:
            Language object or None if not available
        """
        if self.parser:
            # Use the parser's get_language method if available
            if hasattr(self.parser, "get_language"):
                return self.parser.get_language(language)
            # Fall back to direct access to languages dict
            elif hasattr(self.parser, "languages"):
                return self.parser.languages.get(language)
        return None

    def execute_query(self, ast: Any, language: str, query_pattern: str) -> List[Dict[str, Any]]:
        """
        Execute a tree-sitter query on an AST.

        Args:
            ast: Tree-sitter AST
            language: Programming language
            query_pattern: Query pattern string

        Returns:
            List of query matches
        """
        try:
            from tree_sitter import Query, QueryCursor

            # Get language from parser (this is a simplification)
            # In practice, we need the Language object
            language_obj = self._get_language_object(language)
            if language_obj is None:
                return []

            # Compile query
            query = Query(language_obj, query_pattern)

            # Execute query using QueryCursor (tree-sitter 0.25.2 API)
            cursor = QueryCursor(query)
            matches = cursor.matches(ast.root_node)

            # Format results
            results = []
            for pattern_index, captures_dict in matches:
                for capture_name, nodes in captures_dict.items():
                    for node in nodes:
                        result = {
                            "name": capture_name,
                            "text": node.text.decode("utf-8"),
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1,
                            "start_column": node.start_point[1] + 1,
                            "end_column": node.end_point[1] + 1,
                            "node_type": node.type,
                        }
                        results.append(result)

            return results

        except Exception as e:
            logger.error(f"Failed to execute query for {language}: {e}")
            return []

    def extract_functions(self, ast: Any, language: str) -> List[FunctionInfo]:
        """
        Extract function definitions from AST.

        Args:
            ast: Tree-sitter AST
            language: Programming language

        Returns:
            List of FunctionInfo objects
        """
        if language not in self.QUERY_PATTERNS or "function" not in self.QUERY_PATTERNS[language]:
            return []

        query_pattern = self.QUERY_PATTERNS[language]["function"]
        results = self.execute_query(ast, language, query_pattern)

        functions = []
        current_function = None

        for result in results:
            if result["name"] == "function" or result["name"] == "method":
                if current_function:
                    functions.append(current_function)

                current_function = FunctionInfo(
                    name=result.get("text", ""),
                    start_line=result["start_line"],
                    end_line=result["end_line"],
                    parameters=[],
                    return_type=None,
                    docstring=None,
                    decorators=[],
                )

        if current_function:
            functions.append(current_function)

        return functions

    def extract_classes(self, ast: Any, language: str) -> List[ClassInfo]:
        """
        Extract class definitions from AST.

        Args:
            ast: Tree-sitter AST
            language: Programming language

        Returns:
            List of ClassInfo objects
        """
        if language not in self.QUERY_PATTERNS or "class" not in self.QUERY_PATTERNS[language]:
            return []

        query_pattern = self.QUERY_PATTERNS[language]["class"]
        results = self.execute_query(ast, language, query_pattern)

        classes = []
        current_class = None

        for result in results:
            if result["name"] == "class":
                if current_class:
                    classes.append(current_class)

                current_class = ClassInfo(
                    name=result.get("text", ""),
                    start_line=result["start_line"],
                    end_line=result["end_line"],
                    methods=[],
                    bases=[],
                    docstring=None,
                    decorators=[],
                )

        if current_class:
            classes.append(current_class)

        return classes

    def extract_imports(self, ast: Any, language: str) -> List[ImportInfo]:
        """
        Extract import statements from AST.

        Args:
            ast: Tree-sitter AST
            language: Programming language

        Returns:
            List of ImportInfo objects
        """
        if language not in self.QUERY_PATTERNS or "import" not in self.QUERY_PATTERNS[language]:
            return []

        query_pattern = self.QUERY_PATTERNS[language]["import"]

        try:
            from tree_sitter import Query, QueryCursor

            language_obj = self._get_language_object(language)
            if language_obj is None:
                return []

            query = Query(language_obj, query_pattern)
            cursor = QueryCursor(query)

            imports = []

            for pattern_index, captures_dict in cursor.matches(ast.root_node):
                # Group captures by pattern
                module = None
                alias = None
                module_name = None
                imported_name = None
                line = 1

                for capture_name, nodes in captures_dict.items():
                    if nodes:
                        node = nodes[0]
                        text = node.text.decode("utf-8")

                        if capture_name == "module":
                            module = text
                            line = node.start_point[0] + 1
                        elif capture_name == "alias":
                            alias = text
                        elif capture_name == "module_name":
                            module_name = text
                            line = node.start_point[0] + 1
                        elif capture_name == "imported_name":
                            imported_name = text

                # Create ImportInfo based on pattern type
                if module is not None:
                    # Simple import or import with alias
                    imports.append(
                        ImportInfo(module=module, imports=[module], alias=alias, line=line)
                    )
                elif module_name is not None and imported_name is not None:
                    # From import
                    imports.append(
                        ImportInfo(
                            module=module_name, imports=[imported_name], alias=None, line=line
                        )
                    )

            return imports

        except Exception as e:
            logger.error(f"Failed to extract imports for {language}: {e}")
            return []

    def find_symbol(self, ast: Any, language: str, symbol: str) -> List[Tuple[int, int]]:
        """
        Find all occurrences of a symbol in AST.

        Args:
            ast: Tree-sitter AST
            language: Programming language
            symbol: Symbol name to find

        Returns:
            List of (line, column) positions
        """
        # This is a simplified implementation
        # A real implementation would use tree-sitter queries
        positions = []

        try:
            # Walk the tree and find identifier nodes matching the symbol
            from tree_sitter import Node

            def walk(node: Node):
                if node.type == "identifier" and node.text.decode("utf-8") == symbol:
                    positions.append((node.start_point[0] + 1, node.start_point[1] + 1))

                for child in node.children:
                    walk(child)

            walk(ast.root_node)

        except Exception as e:
            logger.error(f"Failed to find symbol {symbol}: {e}")

        return positions

    def get_function_at_position(
        self, ast: Any, language: str, line: int, column: int
    ) -> Optional[FunctionInfo]:
        """
        Get the function that contains the given position.

        Args:
            ast: Tree-sitter AST
            language: Programming language
            line: Line number (1-indexed)
            column: Column number (1-indexed)

        Returns:
            FunctionInfo if position is inside a function, None otherwise
        """
        functions = self.extract_functions(ast, language)

        for func in functions:
            if func.start_line <= line <= func.end_line:
                return func

        return None

    def get_available_queries(self, language: str) -> List[str]:
        """
        Get available query patterns for a language.

        Args:
            language: Programming language

        Returns:
            List of query pattern names
        """
        if language in self.QUERY_PATTERNS:
            return list(self.QUERY_PATTERNS[language].keys())
        return []
