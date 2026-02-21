#!/usr/bin/env python3
"""Final AST test with fixes."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from cortex.code_ast.parser import ASTParser
from cortex.code_ast.queries import ASTQueries
from cortex.code_ast.service import ASTService

print("=== Testing AST with fixes ===")

# Test 1: Import extraction
print("\n1. Testing import extraction...")
test_code = """import os
import sys as system
from collections import defaultdict

def hello():
    pass
"""

parser = ASTParser()
ast = parser.parse(test_code, 'python')
queries = ASTQueries(parser)

imports = queries.extract_imports(ast, 'python')
print(f"   Found {len(imports)} imports")
for i in imports:
    print(f"   - Module: {i.module}, Imports: {i.imports}, Alias: {i.alias}, Line: {i.line}")

# Test 2: Cache stats
print("\n2. Testing cache...")
service = ASTService(cache_size=10, enable_cache=True)
print(f"   Cache object: {service.cache}")
stats = service.get_cache_stats()
print(f"   Cache stats: {stats}")
print(f"   Cache enabled in stats: {stats.get('enabled', 'key missing')}")

# Test 3: Full service integration
print("\n3. Testing full service...")
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write(test_code)
    temp_file = f.name

try:
    # Parse file
    ast = service.parse_file(temp_file, 'python')
    print(f"   Parse successful: {ast is not None}")

    # Extract functions
    functions = service.extract_functions(temp_file, 'python')
    print(f"   Functions: {len(functions)}")

    # Extract classes (none in test code)
    classes = service.extract_classes(temp_file, 'python')
    print(f"   Classes: {len(classes)}")

    # Extract imports
    imports = service.extract_imports(temp_file, 'python')
    print(f"   Imports: {len(imports)}")
    for i in imports:
        print(f"     - {i.module}: {i.imports}")

    # Cache stats after operations
    stats = service.get_cache_stats()
    print(f"   Cache stats after: size={stats.get('size', 0)}, hits={stats.get('hits', 0)}")

    print("\n=== All tests completed successfully! ===")

except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    os.unlink(temp_file)
