#!/usr/bin/env python3
"""Turn a pytest JUnit report (and optionally a coverage.xml) into numbers CI can publish.

Nothing about test counts or coverage is typed by hand anywhere in the repository: CI runs this
after the tests and publishes the result (a job summary, and the two badge files the README
reads).

    python scripts/test_summary.py junit.xml [coverage.xml] --out summary

writes summary/test-summary.json, summary/summary.md, summary/badges/tests.json and
summary/badges/coverage.json (the latter two in the shields.io "endpoint" format).
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Optional


def read_junit(path: Path) -> Dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, 0))
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    return totals


def read_coverage(path: Path) -> Optional[float]:
    root = ET.parse(path).getroot()
    rate = root.get("line-rate")
    return round(float(rate) * 100, 1) if rate is not None else None


def build_summary(junit: Path, coverage: Optional[Path] = None) -> Dict[str, Any]:
    counts = read_junit(junit)
    summary: Dict[str, Any] = dict(counts)
    summary["ok"] = counts["failures"] == 0 and counts["errors"] == 0 and counts["tests"] > 0
    summary["coverage_percent"] = read_coverage(coverage) if coverage else None
    return summary


def tests_badge(summary: Dict[str, Any]) -> Dict[str, Any]:
    if summary["tests"] == 0:
        return {"schemaVersion": 1, "label": "tests", "message": "none ran", "color": "red"}
    if summary["ok"]:
        message = f"{summary['passed']} passed"
        if summary["skipped"]:
            message += f", {summary['skipped']} skipped"
        return {"schemaVersion": 1, "label": "tests", "message": message, "color": "brightgreen"}
    bad = summary["failures"] + summary["errors"]
    return {"schemaVersion": 1, "label": "tests", "message": f"{bad} failing", "color": "red"}


def coverage_badge(summary: Dict[str, Any]) -> Dict[str, Any]:
    percent = summary.get("coverage_percent")
    if percent is None:
        return {"schemaVersion": 1, "label": "coverage", "message": "unknown", "color": "lightgrey"}
    color = "brightgreen" if percent >= 80 else "yellow" if percent >= 60 else "orange"
    return {"schemaVersion": 1, "label": "coverage", "message": f"{percent:.0f}%", "color": color}


def to_markdown(summary: Dict[str, Any]) -> str:
    coverage = summary.get("coverage_percent")
    return "\n".join(
        [
            "## Test results",
            "",
            f"- Passed: **{summary['passed']}** of {summary['tests']}",
            f"- Failed: {summary['failures']}, errors: {summary['errors']}, skipped: {summary['skipped']}",
            f"- Coverage: {'unknown' if coverage is None else f'{coverage}%'}",
            "",
        ]
    )


def write_outputs(summary: Dict[str, Any], out: Path) -> None:
    (out / "badges").mkdir(parents=True, exist_ok=True)
    (out / "test-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    (out / "summary.md").write_text(to_markdown(summary))
    (out / "badges" / "tests.json").write_text(json.dumps(tests_badge(summary)))
    (out / "badges" / "coverage.json").write_text(json.dumps(coverage_badge(summary)))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("junit", type=Path)
    parser.add_argument("coverage", type=Path, nargs="?")
    parser.add_argument("--out", type=Path, default=Path("summary"))
    args = parser.parse_args(argv)

    summary = build_summary(args.junit, args.coverage)
    write_outputs(summary, args.out)
    print(to_markdown(summary))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
