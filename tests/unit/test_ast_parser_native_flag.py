"""Turning on the Rust AST flag must not break AST parsing.

The parser's contract is to return a tree-sitter Tree. The native parser returns a different
object (a summary), so returning it made every caller that reads `tree.root_node` fail.
"""

import sys
import types

import pytest

from cortex.code_ast.parser import ASTParser
from cortex.core.feature_flags import FeatureFlag, FeatureManager

pytest.importorskip("tree_sitter")


@pytest.fixture
def rust_ast_enabled(monkeypatch):
    class NativeSummary:  # what the Rust extension returns: not a tree-sitter Tree
        functions = 1

    native = types.ModuleType("cortex.native")
    native.NATIVE_AVAILABLE = True
    native.native_parse_code = lambda code, language: NativeSummary()
    monkeypatch.setitem(sys.modules, "cortex.native", native)

    FeatureManager.reset()
    manager = FeatureManager.get_instance()
    manager.enable(FeatureFlag.RUST_AST)
    yield
    FeatureManager.reset()


def test_parse_still_returns_a_tree_sitter_tree_with_the_flag_on(rust_ast_enabled):
    parser = ASTParser()

    tree = parser.parse("def f():\n    return 1\n", "python")

    assert tree is not None
    assert hasattr(tree, "root_node"), "callers read tree.root_node"
    assert tree.root_node.type == "module"
