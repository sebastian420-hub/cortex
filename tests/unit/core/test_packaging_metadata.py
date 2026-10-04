"""Guards for pyproject.toml problems that stop a fresh `pip install` from working."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_no_license_classifier_alongside_a_license_expression():
    # Current setuptools rejects "License ::" classifiers when `license = "MIT"` (an SPDX
    # expression) is also set, so a fresh `pip install .` fails with InvalidConfigError.
    assert re.search(r'^license\s*=\s*"', PYPROJECT, re.MULTILINE)
    assert "License ::" not in PYPROJECT


def test_python_floor_matches_what_the_code_needs():
    # The code uses Path.is_relative_to and asyncio.to_thread (both Python 3.9+).
    assert 'requires-python = ">=3.9"' in PYPROJECT
    assert "Programming Language :: Python :: 3.8" not in PYPROJECT


def test_heavy_memory_dependencies_are_an_optional_extra():
    core = PYPROJECT.split("dependencies = [", 1)[1].split("]", 1)[0]
    assert "chromadb" not in core
    assert "sentence-transformers" not in core
    extras = PYPROJECT.split("[project.optional-dependencies]", 1)[1]
    assert re.search(
        r"^memory\s*=\s*\[[^\]]*chromadb[^\]]*sentence-transformers", extras, re.M | re.S
    )


def test_skill_playbooks_ship_in_the_package():
    assert "skills/*.md" in PYPROJECT
    assert list((REPO_ROOT / "cortex" / "skills").glob("*.md"))
