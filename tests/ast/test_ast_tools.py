#!/usr/bin/env python3
"""
Test script to verify AST tools functionality.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cortex.tools.registry import ToolRegistry
from cortex.tools.ast.integration import get_ast_status, is_ast_available


def test_ast_status():
    """Test AST status checking."""
    print("Testing AST status...")
    status = get_ast_status()
    print(f"AST available: {status.get('available', False)}")
    print(f"Tree-sitter installed: {status.get('tree_sitter_installed', False)}")
    print(f"Supported languages: {status.get('supported_languages', [])}")

    if status.get("available", False):
        print("✓ AST parsing is available")
    else:
        print("✗ AST parsing is not available")
        print(f"Error: {status.get('error', 'Unknown error')}")

    return status.get("available", False)


def test_tool_registration():
    """Test that AST tools are registered."""
    print("\nTesting tool registration...")

    # Create registry
    registry = ToolRegistry()
    registry.register_builtins()

    # Check for AST tools
    ast_tools = []
    for tool_name in registry.list_tools():
        if tool_name.startswith("ast_"):
            ast_tools.append(tool_name)

    print(f"Found AST tools: {ast_tools}")

    if ast_tools:
        print("✓ AST tools are registered")
        for tool_name in ast_tools:
            schema = registry.get_schema(tool_name)
            if schema:
                print(
                    f"  - {tool_name}: {schema.get('function', {}).get('description', 'No description')}"
                )  # noqa: E501
    else:
        print("✗ No AST tools found")

    return len(ast_tools) > 0


def test_ast_parsing():
    """Test basic AST parsing functionality."""
    print("\nTesting AST parsing...")

    try:
        from cortex.code_ast.service import ASTService
        from cortex.code_ast.parser import ASTParser

        # Create a simple test file
        test_file = project_root / "test_ast_sample.py"
        test_content = '''"""
Test file for AST parsing.
"""

import os
import sys
from typing import List, Dict


def hello_world(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"


class Calculator:
    """Simple calculator class."""

    def __init__(self):
        self.value = 0

    def add(self, x: int) -> int:
        """Add to the value."""
        self.value += x
        return self.value
'''

        test_file.write_text(test_content)

        # Test language detection
        from cortex.code_ast.languages import detect_language

        language = detect_language(test_file)
        print(f"Detected language: {language}")

        # Test AST parsing
        service = ASTService(cache_size=10, enable_cache=True)
        ast = service.parse_file(test_file, language)

        if ast:
            print("✓ AST parsing successful")

            # Test function extraction
            functions = service.extract_functions(test_file, language)
            print(f"Found {len(functions)} functions:")
            for func in functions:
                print(f"  - {func.name} (lines {func.start_line}-{func.end_line})")

            # Test class extraction
            classes = service.extract_classes(test_file, language)
            print(f"Found {len(classes)} classes:")
            for cls in classes:
                print(f"  - {cls.name} (lines {cls.start_line}-{cls.end_line})")
                print(f"    Methods: {len(cls.methods)}")

            # Test import extraction
            imports = service.extract_imports(test_file, language)
            print(f"Found {len(imports)} imports:")
            for imp in imports:
                print(f"  - {imp.module}")

        else:
            print("✗ AST parsing failed")

        # Clean up
        test_file.unlink()

        return ast is not None

    except Exception as e:
        print(f"✗ AST parsing test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("AST Tools Test Suite")
    print("=" * 60)

    tests = [
        ("AST Status", test_ast_status),
        ("Tool Registration", test_tool_registration),
        ("AST Parsing", test_ast_parsing),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ✗ Test failed with error: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:20} {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed! ✓")
    else:
        print("Some tests failed. ✗")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
