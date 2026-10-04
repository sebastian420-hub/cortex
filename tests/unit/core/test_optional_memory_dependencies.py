"""A base install (no chromadb, no sentence-transformers/torch) must still start and work.

Both packages moved to the optional ``cortex[memory]`` extra. These tests run in a fresh
interpreter in which importing either package raises ImportError, which is what a base install
looks like.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

BLOCK_MEMORY_PACKAGES = (
    "import sys\n"
    "sys.modules['chromadb'] = None\n"
    "sys.modules['sentence_transformers'] = None\n"
)


def _run(code: str):
    return subprocess.run(
        [sys.executable, "-c", BLOCK_MEMORY_PACKAGES + textwrap.dedent(code)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=180,
    )


def test_agent_imports_without_the_memory_extra():
    result = _run("""
        import cortex
        from cortex.agent import Cortex
        from cortex.core.memory_layers import EnhancedMemoryBank
        print("imported")
        """)
    assert result.returncode == 0, result.stderr
    assert "imported" in result.stdout


def test_memory_bank_works_with_semantic_memory_off():
    result = _run("""
        from cortex.core.memory_layers import EnhancedMemoryBank
        bank = EnhancedMemoryBank(max_items=5)
        bank.add_fact("the port is 8080")
        assert bank.semantic_manager is None
        print("ok")
        """)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_enabling_semantic_memory_without_the_extra_explains_how_to_install_it(tmp_path):
    result = _run(f"""
        from pathlib import Path
        from cortex.core.memory.semantic import ChromaMemoryManager
        try:
            ChromaMemoryManager(persist_directory=Path({str(tmp_path)!r}))
        except ImportError as e:
            print(str(e))
        """)
    assert result.returncode == 0, result.stderr
    assert "cortex[memory]" in result.stdout
