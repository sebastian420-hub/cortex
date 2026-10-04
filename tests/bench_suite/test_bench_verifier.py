"""The verifier cannot be talked into passing."""

import tempfile
from pathlib import Path

import pytest

from bench.suite import get
from bench.task import apply_solution, materialize, verify

TASK = get("bug-sum-to-off-by-one")


@pytest.fixture
def project():
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch) / "project"
        materialize(TASK, root)
        yield root


def test_editing_the_tests_does_not_help(project):
    (project / "tests" / "test_mathutil.py").write_text(
        "def test_everything_is_fine():\n    assert True\n"
    )

    result = verify(TASK, project)

    assert not result.passed  # the real tests were put back and they fail on the bug


def test_deleting_the_tests_does_not_help(project):
    (project / "tests" / "test_mathutil.py").unlink()

    assert not verify(TASK, project).passed


def test_a_conftest_that_could_change_the_tests_is_refused(project):
    apply_solution(TASK, project)
    (project / "conftest.py").write_text("import pytest\n")

    result = verify(TASK, project)

    assert not result.passed
    assert result.tampered == ("conftest.py",)
    assert "conftest.py" in result.output


@pytest.mark.parametrize("name", ["pytest.py", "sitecustomize.py", "pytest.ini", "tox.ini"])
def test_other_files_that_change_how_tests_run_are_refused(project, name):
    apply_solution(TASK, project)
    (project / name).write_text("")

    assert verify(TASK, project).tampered == (name,)


def test_ordinary_extra_files_are_fine(project):
    apply_solution(TASK, project)
    (project / "notes.txt").write_text("hello")
    (project / "helper.py").write_text("X = 1\n")

    assert verify(TASK, project).passed


def test_a_hanging_solution_times_out_and_fails(project):
    from dataclasses import replace

    hung = replace(TASK, timeout=2)
    (project / "mathutil.py").write_text(
        "import time\n\ndef sum_to(n):\n    time.sleep(30)\n    return 0\n"
    )

    result = verify(hung, project)

    assert not result.passed
    assert "timed out" in result.output
