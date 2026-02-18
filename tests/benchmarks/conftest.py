"""Shared fixtures for benchmark tests."""

import os
import json
import random
import string
import tempfile
import shutil
from pathlib import Path
from typing import Optional

import pytest


@pytest.fixture(scope="session")
def benchmark_tmp_dir():
    """Create a temporary directory for benchmark data that persists across tests."""
    tmp = tempfile.mkdtemp(prefix="cortex_bench_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def small_codebase(benchmark_tmp_dir):
    """Generate a small test codebase (100 files, ~50 lines each)."""
    return _generate_codebase(benchmark_tmp_dir / "small", num_files=100, avg_lines=50)


@pytest.fixture(scope="session")
def medium_codebase(benchmark_tmp_dir):
    """Generate a medium test codebase (1000 files, ~100 lines each)."""
    return _generate_codebase(benchmark_tmp_dir / "medium", num_files=1000, avg_lines=100)


@pytest.fixture(scope="session")
def large_codebase(benchmark_tmp_dir):
    """Generate a large test codebase (5000 files, ~150 lines each)."""
    return _generate_codebase(benchmark_tmp_dir / "large", num_files=5000, avg_lines=150)


@pytest.fixture
def sample_python_code():
    """Return a realistic Python source file for AST benchmarks."""
    return '''"""Sample module for benchmarking AST parsing."""

import os
import sys
from typing import List, Dict, Optional
from pathlib import Path


class DataProcessor:
    """Processes data from multiple sources."""

    def __init__(self, config: Dict[str, str], verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self._cache = {}

    def process(self, items: List[str]) -> List[Dict]:
        results = []
        for item in items:
            if item in self._cache:
                results.append(self._cache[item])
            else:
                result = self._transform(item)
                self._cache[item] = result
                results.append(result)
        return results

    def _transform(self, item: str) -> Dict:
        return {"name": item, "length": len(item), "upper": item.upper()}

    @staticmethod
    def validate(data: Dict) -> bool:
        return "name" in data and "length" in data


class FileHandler:
    """Handles file operations."""

    def __init__(self, base_path: Path):
        self.base_path = base_path

    def read_all(self, pattern: str = "*.txt") -> List[str]:
        results = []
        for path in self.base_path.glob(pattern):
            results.append(path.read_text())
        return results

    def write(self, name: str, content: str) -> Path:
        path = self.base_path / name
        path.write_text(content)
        return path


def compute_stats(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0, "max": 0, "avg": 0}
    return {
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
    }


def filter_items(items: List[str], predicate=None) -> List[str]:
    if predicate is None:
        return [item for item in items if item.strip()]
    return [item for item in items if predicate(item)]


if __name__ == "__main__":
    processor = DataProcessor({"key": "value"})
    data = processor.process(["hello", "world", "test"])
    print(data)
'''


@pytest.fixture
def sample_text_1k():
    """Generate ~1K characters of sample text for token counting."""
    return _generate_text(1000)


@pytest.fixture
def sample_text_10k():
    """Generate ~10K characters of sample text for token counting."""
    return _generate_text(10000)


@pytest.fixture
def sample_text_100k():
    """Generate ~100K characters of sample text for token counting."""
    return _generate_text(100000)


@pytest.fixture
def sample_conversation():
    """Generate a sample conversation history for token counting benchmarks."""
    messages = [
        {"role": "system", "content": "You are a helpful coding assistant."},
    ]
    for i in range(20):
        messages.append({"role": "user", "content": f"Question {i}: " + _generate_text(200)})
        messages.append({"role": "assistant", "content": f"Answer {i}: " + _generate_text(500)})
    return messages


@pytest.fixture
def baseline_file(benchmark_tmp_dir):
    """Path for storing benchmark baselines."""
    return benchmark_tmp_dir / "baselines.json"


def save_baseline(path: Path, name: str, value: float):
    """Save a benchmark baseline value."""
    data = {}
    if path.exists():
        data = json.loads(path.read_text())
    data[name] = value
    path.write_text(json.dumps(data, indent=2))


def load_baseline(path: Path, name: str) -> Optional[float]:
    """Load a benchmark baseline value."""
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get(name)


def _generate_codebase(root: Path, num_files: int, avg_lines: int) -> Path:
    """Generate a synthetic codebase with Python and JS files."""
    root.mkdir(parents=True, exist_ok=True)

    extensions = [".py", ".js", ".ts", ".java", ".go"]
    subdirs = ["src", "lib", "utils", "core", "tests", "api", "models"]

    for i in range(num_files):
        subdir = subdirs[i % len(subdirs)]
        ext = extensions[i % len(extensions)]
        dir_path = root / subdir
        dir_path.mkdir(exist_ok=True)

        filename = f"module_{i}{ext}"
        lines = random.randint(max(10, avg_lines - 30), avg_lines + 30)

        content = _generate_source_file(ext, lines)
        (dir_path / filename).write_text(content)

    return root


def _generate_source_file(ext: str, num_lines: int) -> str:
    """Generate a synthetic source file of given length."""
    lines = []
    if ext == ".py":
        lines.append('"""Auto-generated module."""')
        lines.append("import os")
        lines.append("import sys")
        lines.append("")
        for j in range(num_lines - 4):
            if j % 10 == 0:
                lines.append(f"def function_{j}(arg1, arg2):")
                lines.append(f'    """Function {j} docstring."""')
                lines.append(f"    result = arg1 + arg2 + {j}")
                lines.append("    return result")
            elif j % 15 == 0:
                lines.append(f"class Class_{j}:")
                lines.append(f'    """Class {j}."""')
                lines.append("    def __init__(self):")
                lines.append(f"        self.value = {j}")
            else:
                lines.append(f"# Line {j}: " + _random_word(20))
    elif ext in (".js", ".ts"):
        lines.append("// Auto-generated module")
        for j in range(num_lines - 1):
            if j % 10 == 0:
                lines.append(f"function func_{j}(a, b) {{")
                lines.append(f"  return a + b + {j};")
                lines.append("}")
            else:
                lines.append(f"// Line {j}: " + _random_word(20))
    else:
        for j in range(num_lines):
            lines.append(f"// Line {j}: " + _random_word(30))

    return "\n".join(lines) + "\n"


def _generate_text(length: int) -> str:
    """Generate random English-like text of approximate length."""
    words = [
        "the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog",
        "function", "class", "module", "import", "return", "if", "else",
        "for", "while", "try", "except", "with", "as", "from", "in",
        "variable", "constant", "parameter", "argument", "value", "result",
        "data", "process", "compute", "analyze", "transform", "filter",
    ]
    result = []
    current_len = 0
    while current_len < length:
        word = random.choice(words)
        result.append(word)
        current_len += len(word) + 1
    return " ".join(result)[:length]


def _random_word(length: int) -> str:
    return "".join(random.choices(string.ascii_lowercase + " ", k=length))
