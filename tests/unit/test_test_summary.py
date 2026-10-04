"""CI's test summary: counts come from the JUnit report, never from anyone's typing."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "test_summary.py"
spec = importlib.util.spec_from_file_location("test_summary_script", SCRIPT)
summary_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary_script)

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="{errors}" failures="{failures}" skipped="{skipped}" tests="{tests}">
</testsuite></testsuites>"""
COVERAGE = '<?xml version="1.0" ?><coverage line-rate="{rate}" version="7"></coverage>'


def junit(tmp_path, tests=10, failures=0, errors=0, skipped=0):
    path = tmp_path / "junit.xml"
    path.write_text(JUNIT.format(tests=tests, failures=failures, errors=errors, skipped=skipped))
    return path


def test_counts_are_read_from_the_report(tmp_path):
    summary = summary_script.build_summary(junit(tmp_path, tests=100, failures=2, skipped=3))

    assert (summary["tests"], summary["passed"], summary["failures"], summary["skipped"]) == (
        100,
        95,
        2,
        3,
    )
    assert summary["ok"] is False


def test_a_clean_run_is_ok_and_the_badge_says_how_many_passed(tmp_path):
    summary = summary_script.build_summary(junit(tmp_path, tests=50, skipped=5))

    assert summary["ok"] is True
    badge = summary_script.tests_badge(summary)
    assert badge["message"] == "45 passed, 5 skipped" and badge["color"] == "brightgreen"
    assert badge["schemaVersion"] == 1


def test_failures_and_errors_make_the_badge_red(tmp_path):
    summary = summary_script.build_summary(junit(tmp_path, tests=10, failures=1, errors=2))

    badge = summary_script.tests_badge(summary)
    assert badge["message"] == "3 failing" and badge["color"] == "red"


def test_a_run_that_ran_nothing_is_not_ok(tmp_path):
    summary = summary_script.build_summary(junit(tmp_path, tests=0))

    assert summary["ok"] is False
    assert summary_script.tests_badge(summary)["message"] == "none ran"


def test_coverage_is_read_and_coloured(tmp_path):
    cov = tmp_path / "coverage.xml"
    cov.write_text(COVERAGE.format(rate="0.664"))

    summary = summary_script.build_summary(junit(tmp_path), cov)

    assert summary["coverage_percent"] == 66.4
    badge = summary_script.coverage_badge(summary)
    assert badge["message"] == "66%" and badge["color"] == "yellow"


def test_unknown_coverage_is_called_unknown(tmp_path):
    summary = summary_script.build_summary(junit(tmp_path))

    assert summary_script.coverage_badge(summary)["message"] == "unknown"


def test_a_bare_testsuite_root_is_understood(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text('<testsuite tests="4" failures="0" errors="0" skipped="1"></testsuite>')

    assert summary_script.read_junit(path)["passed"] == 3


def test_the_command_writes_every_output_and_signals_failure(tmp_path):
    out = tmp_path / "out"

    code_ok = summary_script.main([str(junit(tmp_path)), "--out", str(out)])
    assert code_ok == 0
    for name in ("test-summary.json", "summary.md", "badges/tests.json", "badges/coverage.json"):
        assert (out / name).exists(), name
    assert json.loads((out / "badges" / "tests.json").read_text())["label"] == "tests"

    bad = junit(tmp_path, failures=1)
    assert summary_script.main([str(bad), "--out", str(out)]) == 1
