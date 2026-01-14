"""
AST Tools Integration - Register AST tools with Cortex.

This module integrates AST-aware tools into the Cortex tool registry,
making them available for use in the agent.
"""

import logging
from typing import Dict, Any, List

from ..registry import ToolRegistry
from .ast_search_tool import ASTSearchTool
from .ast_extract_tool import ASTExtractTool
from .ast_analyze_tool import ASTAnalyzeTool

logger = logging.getLogger(__name__)


def register_ast_tools(registry: ToolRegistry) -> None:
    """
    Register AST-aware tools with the tool registry.
    
    Args:
        registry: ToolRegistry instance
    """
    logger.info("Registering AST tools...")
    
    # Helper function to convert parameter list to schema
    def build_schema(tool_name: str, description: str, parameters: list) -> dict:
        properties = {}
        required = []
        for param in parameters:
            param_name = param["name"]
            param_type = param["type"]
            param_desc = param.get("description", "")
            param_required = param.get("required", False)
            param_default = param.get("default")
            param_enum = param.get("enum")
            
            # Build property schema
            prop_schema = {"type": param_type, "description": param_desc}
            if param_enum is not None:
                prop_schema["enum"] = param_enum
            if param_default is not None:
                prop_schema["default"] = param_default
            
            properties[param_name] = prop_schema
            
            if param_required:
                required.append(param_name)
        
        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
    
    # Register AST Search Tool
    registry.register(
        name="ast_search",
        tool_class=ASTSearchTool,
        schema=build_schema(
            tool_name="ast_search",
            description="Enhanced search with AST understanding. Combines traditional text search with AST-based structural search for smarter code understanding.",
            parameters=[
                {
                    "name": "pattern",
                    "type": "string",
                    "description": "Pattern to search for",
                    "required": True,
                },
                {
                    "name": "path",
                    "type": "string",
                    "description": "Directory or file to search in",
                    "default": ".",
                },
                {
                    "name": "search_type",
                    "type": "string",
                    "description": "Search type: 'text', 'structure', 'smart', 'function', 'class', 'import'",
                    "default": "smart",
                    "enum": ["text", "structure", "smart", "function", "class", "import"],
                },
                {
                    "name": "file_type",
                    "type": "string",
                    "description": "File type to search (e.g., 'py', 'js')",
                },
                {
                    "name": "output_mode",
                    "type": "string",
                    "description": "Output mode: 'files_with_matches', 'content', or 'count'",
                    "default": "files_with_matches",
                    "enum": ["files_with_matches", "content", "count"],
                },
                {
                    "name": "case_insensitive",
                    "type": "boolean",
                    "description": "Case insensitive search",
                    "default": False,
                },
                {
                    "name": "context",
                    "type": "integer",
                    "description": "Lines to show before and after match",
                    "default": 0,
                },
                {
                    "name": "multiline",
                    "type": "boolean",
                    "description": "Enable multiline matching",
                    "default": False,
                },
                {
                    "name": "head_limit",
                    "type": "integer",
                    "description": "Limit results (0 for unlimited)",
                    "default": 50,
                },
                {
                    "name": "offset",
                    "type": "integer",
                    "description": "Skip first N results",
                    "default": 0,
                },
                {
                    "name": "show_line_numbers",
                    "type": "boolean",
                    "description": "Show line numbers in content mode",
                    "default": True,
                },
            ],
        ),
        namespace="builtin",
    )
    
    # Register AST Extract Tool
    registry.register(
        name="ast_extract",
        tool_class=ASTExtractTool,
        schema=build_schema(
            tool_name="ast_extract",
            description="Extract code structures using AST parsing. Provides semantic extraction of functions, classes, imports, and other code structures.",
            parameters=[
                {
                    "name": "path",
                    "type": "string",
                    "description": "Directory or file to extract from",
                    "required": True,
                },
                {
                    "name": "extract_type",
                    "type": "string",
                    "description": "Type of extraction: 'function', 'class', 'import', or 'all'",
                    "default": "all",
                    "enum": ["function", "class", "import", "all"],
                },
                {
                    "name": "pattern",
                    "type": "string",
                    "description": "Optional pattern to filter results",
                },
                {
                    "name": "include_docstrings",
                    "type": "boolean",
                    "description": "Include docstrings in results",
                    "default": True,
                },
                {
                    "name": "include_decorators",
                    "type": "boolean",
                    "description": "Include decorators in results",
                    "default": True,
                },
                {
                    "name": "include_parameters",
                    "type": "boolean",
                    "description": "Include function parameters",
                    "default": True,
                },
                {
                    "name": "include_return_types",
                    "type": "boolean",
                    "description": "Include return types",
                    "default": True,
                },
                {
                    "name": "include_bases",
                    "type": "boolean",
                    "description": "Include class bases",
                    "default": True,
                },
                {
                    "name": "include_methods",
                    "type": "boolean",
                    "description": "Include class methods",
                    "default": True,
                },
                {
                    "name": "include_aliases",
                    "type": "boolean",
                    "description": "Include import aliases",
                    "default": True,
                },
            ],
        ),
        namespace="builtin",
    )
    
    # Register AST Analyze Tool
    registry.register(
        name="ast_analyze",
        tool_class=ASTAnalyzeTool,
        schema=build_schema(
            tool_name="ast_analyze",
            description="Code analysis using AST parsing. Provides metrics for code complexity, dependencies, and quality.",
            parameters=[
                {
                    "name": "path",
                    "type": "string",
                    "description": "Directory or file to analyze",
                    "required": True,
                },
                {
                    "name": "analysis_type",
                    "type": "string",
                    "description": "Analysis type: 'complexity', 'dependencies', 'issues', or 'all'",
                    "default": "complexity",
                    "enum": ["complexity", "dependencies", "issues", "all"],
                },
                {
                    "name": "max_depth",
                    "type": "integer",
                    "description": "Maximum depth for dependency analysis",
                    "default": 3,
                },
                {
                    "name": "include_metrics",
                    "type": "boolean",
                    "description": "Include code metrics",
                    "default": True,
                },
                {
                    "name": "include_dependencies",
                    "type": "boolean",
                    "description": "Include dependency analysis",
                    "default": True,
                },
                {
                    "name": "include_issues",
                    "type": "boolean",
                    "description": "Include potential issues",
                    "default": True,
                },
            ],
        ),
        namespace="builtin",
    )
    
    logger.info("AST tools registered successfully")


def get_ast_tool_descriptions() -> List[Dict[str, Any]]:
    """
    Get descriptions of all AST tools.
    
    Returns:
        List of tool descriptions
    """
    return [
        {
            "name": "ast_search",
            "description": "Enhanced search with AST understanding. Combines traditional text search with AST-based structural search for smarter code understanding.",
            "examples": [
                "ast_search pattern='def test_' search_type='function'",
                "ast_search pattern='class.*Service' search_type='structure'",
                "ast_search pattern='import requests' search_type='import'",
            ],
        },
        {
            "name": "ast_extract",
            "description": "Extract code structures using AST parsing. Provides semantic extraction of functions, classes, imports, and other code structures.",
            "examples": [
                "ast_extract path='.' extract_type='function'",
                "ast_extract path='src/' extract_type='class' pattern='Service'",
                "ast_extract path='.' extract_type='all' include_docstrings=False",
            ],
        },
        {
            "name": "ast_analyze",
            "description": "Code analysis using AST parsing. Provides metrics for code complexity, dependencies, and quality.",
            "examples": [
                "ast_analyze path='.' analysis_type='complexity'",
                "ast_analyze path='src/' analysis_type='dependencies' max_depth=5",
                "ast_analyze path='.' analysis_type='all' include_issues=True",
            ],
        },
    ]


def is_ast_available() -> bool:
    """
    Check if AST parsing is available.
    
    Returns:
        True if tree-sitter is installed and AST tools can be used
    """
    try:
        from ...ast.service import ASTService
        service = ASTService(cache_size=1, enable_cache=False)
        # Try to parse a simple Python file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def test():\n    pass\n")
            f.flush()
            ast = service.parse_file(f.name, "python")
            return ast is not None
    except Exception as e:
        logger.warning(f"AST parsing not available: {e}")
        return False


def get_ast_status() -> Dict[str, Any]:
    """
    Get status of AST parsing capabilities.
    
    Returns:
        Dictionary with AST status information
    """
    try:
        from ...ast.parser import ASTParser
        parser = ASTParser()
        
        return {
            "available": parser.is_available(),
            "supported_languages": parser.get_supported_languages() if parser.is_available() else [],
            "tree_sitter_installed": hasattr(parser, 'available') and parser.available,
        }
    except Exception as e:
        logger.error(f"Failed to get AST status: {e}")
        return {
            "available": False,
            "supported_languages": [],
            "tree_sitter_installed": False,
            "error": str(e),
        }
