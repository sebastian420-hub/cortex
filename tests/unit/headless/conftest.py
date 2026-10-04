"""Fixtures for the headless-run tests: a real git repository and no leaking of the real home."""

import os
from pathlib import Path

import pytest

from tests.unit.headless.gitutil import GIT_ENV, git


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Keep ~/.cortex and any git identity out of the picture."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("CORTEX_STRICT_MESSAGES", "1")
    for name in GIT_ENV:  # the code under test must cope without an identity
        monkeypatch.delenv(name, raising=False)
    return home


@pytest.fixture
def repo(tmp_path) -> Path:
    """A git repository with one commit: a source file and a test."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "a.py").write_text("def hello():\n    return 1\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "init")
    return root
