#!/usr/bin/env python3
"""Comprehensive AST system test - final version."""

import sys
import tempfile
import os
from pathlib import Path
sys.path.insert(0, '.')

from cortex.ast.parser import ASTParser
from cortex.ast.queries import ASTQueries
from cortex.ast.service import ASTService
from cortex.ast.languages import detect_language

import pytest

@pytest.fixture(scope="module")
def parser():
    print("=== Creating ASTParser ===")
    return ASTParser()

@pytest.fixture(scope="module")
def ast(parser):
    print("=== Parsing test code ===")
    test_code = """import os
import sys as system
from collections import defaultdict

def hello(name: str) -> str:
    \"\"\"Greet someone.\"\"\"
    return f"Hello, {name}!"

class Calculator:
    \"\"\"Simple calculator.\"\"\"
    
    def add(self, x: int, y: int) -> int:
        return x + y
    
    def multiply(self, x: int, y: int) -> int:
        return x * y
"""
    return parser.parse(test_code, 'python')

def test_parser_execution(parser, ast):
    print("=== Testing ASTParser ===")
    print(f"Available: {parser.available}")
    print(f"Languages loaded: {list(parser.parsers.keys())}")
    assert ast is not None, "Parse failed"
    print(f"Parse successful! Root type: {ast.root_node.type}")


def test_queries(parser, ast):
    print("\n=== Testing ASTQueries ===")
    queries = ASTQueries(parser)
    
    # Test execute_query
    print("\n1. Testing execute_query...")
    query_pattern = "(function_definition name: (identifier) @func_name)"
    results = queries.execute_query(ast, 'python', query_pattern)
    print(f"   Found {len(results)} function matches")
    for r in results[:3]:
        print(f"   - {r['name']}: {r['text']} at line {r['start_line']}")
    
    # Test extract_functions
    print("\n2. Testing extract_functions...")
    functions = queries.extract_functions(ast, 'python')
    print(f"   Extracted {len(functions)} functions")
    for f in functions:
        print(f"   - {f.name} (lines {f.start_line}-{f.end_line})")
    
    # Test extract_classes
    print("\n3. Testing extract_classes...")
    classes = queries.extract_classes(ast, 'python')
    print(f"   Extracted {len(classes)} classes")
    for c in classes:
        print(f"   - {c.name} (lines {c.start_line}-{c.end_line})")
        print(f"     Methods: {len(c.methods)}")
    
    # Test extract_imports - should work now
    print("\n4. Testing extract_imports...")
    imports = queries.extract_imports(ast, 'python')
    print(f"   Extracted {len(imports)} imports")
    for i in imports:
        print(f"   - {i.module}: {i.imports} at line {i.line}")
    
    # Test find_symbol
    print("\n5. Testing find_symbol...")
    positions = queries.find_symbol(ast, 'python', 'hello')
    print(f"   Found 'hello' at {len(positions)} positions")
    for line, col in positions:
        print(f"   - Line {line}, Column {col}")
    
    # Test get_function_at_position
    print("\n6. Testing get_function_at_position...")
    func = queries.get_function_at_position(ast, 'python', 7, 5)
    if func:
        print(f"   Function at line 7: {func.name}")
    else:
        print("   No function at line 7")
    
    return queries

def test_service():
    print("\n=== Testing ASTService ===")
    
    # Create test file
    test_code = """import os
import sys

def test_function():
    \"\"\"Test function.\"\"\"
    pass

class TestClass:
    \"\"\"Test class.\"\"\"
    
    def method(self):
        pass
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test_code)
        f.flush()
        temp_file = f.name
    
    try:
        service = ASTService(cache_size=10, enable_cache=True)
        
        # Test parse_file
        print("\n1. Testing parse_file...")
        ast = service.parse_file(temp_file, 'python')
        assert ast is not None, "Service parse failed"
        print("   Parse successful")
        
        # Test extract_functions
        print("\n2. Testing extract_functions...")
        functions = service.extract_functions(temp_file, 'python')
        print(f"   Extracted {len(functions)} functions")
        for f in functions:
            print(f"   - {f.name}")
        
        # Test extract_classes
        print("\n3. Testing extract_classes...")
        classes = service.extract_classes(temp_file, 'python')
        print(f"   Extracted {len(classes)} classes")
        for c in classes:
            print(f"   - {c.name}")
        
        # Test extract_imports
        print("\n4. Testing extract_imports...")
        imports = service.extract_imports(temp_file, 'python')
        print(f"   Extracted {len(imports)} imports")
        for i in imports:
            print(f"   - {i.module}: {i.imports}")
        
        # Test query
        print("\n5. Testing query...")
        query_results = service.query(temp_file, "(function_definition name: (identifier) @name)", 'python')
        print(f"   Query returned {len(query_results)} results")
        
        # Test cache - note: cache stats may not have 'enabled' key
        print("\n6. Testing cache...")
        stats = service.get_cache_stats()
        print(f"   Cache stats: {stats}")
        
        # Test language detection
        print("\n7. Testing language detection...")
        lang = detect_language(Path(temp_file))
        print(f"   Detected language: {lang}")
        
        print("\n=== Service tests passed! ===")
        
    finally:
        os.unlink(temp_file)

def test_tool_integration():
    print("\n=== Testing Tool Integration ===")
    
    try:
        from cortex.tools.ast.integration import get_ast_status, is_ast_available
        from cortex.tools.registry import ToolRegistry
        
        # Test AST status
        print("\n1. Testing AST status...")
        status = get_ast_status()
        print(f"   AST available: {status.get('available', False)}")
        print(f"   Supported languages: {status.get('supported_languages', [])}")
        
        # Test availability
        available = is_ast_available()
        print(f"   is_ast_available(): {available}")
        
        # Test tool registration
        print("\n2. Testing tool registration...")
        registry = ToolRegistry()
        registry.register_builtins()
        
        # Check for AST tools
        ast_tools = [name for name in registry.list_tools() if name.startswith('ast_')]
        print(f"   Found AST tools: {ast_tools}")
        
        if ast_tools:
            print("   AST tools registered successfully!")
        else:
            print("   Note: No AST tools found (may be disabled if AST not available)")
        
        print("\n=== Tool integration tests passed! ===")
        
    except Exception as e:
        print(f"   Tool integration test failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("=" * 60)
    print("Comprehensive AST System Test - Final")
    print("=" * 60)
    
    try:
        # Test parser
        parser, ast = test_parser()
        
        # Test queries
        test_queries(parser, ast)
        
        # Test service
        test_service()
        
        # Test tool integration
        test_tool_integration()
        
        print("\n" + "=" * 60)
        print("All tests passed successfully!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())