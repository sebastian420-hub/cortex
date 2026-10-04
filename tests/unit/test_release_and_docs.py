"""The release metadata and the documentation cannot quietly drift apart."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

HEADING = re.compile(r"^## \[?([^\]\n]+?)\]?(?: - (.+))?$", re.MULTILINE)


def released_versions():
    """(version, date) for every released section, newest first as written."""
    return [
        (m.group(1).strip(), (m.group(2) or "").strip())
        for m in HEADING.finditer(CHANGELOG)
        if re.match(r"^\d+\.\d+\.\d+$", m.group(1).strip())
    ]


def version_key(version):
    return tuple(int(part) for part in version.split("."))


def test_the_changelog_lists_the_version_pyproject_declares():
    declared = re.search(r'^version = "([^"]+)"', PYPROJECT, re.MULTILINE).group(1)

    versions = [v for v, _ in released_versions()]

    assert declared in versions, f"CHANGELOG.md has no section for {declared}"
    assert versions[0] == declared, "the newest changelog section must be the declared version"


def test_changelog_sections_are_newest_first():
    versions = [version_key(v) for v, _ in released_versions()]

    assert versions == sorted(versions, reverse=True)


def test_every_release_has_a_real_date_or_says_it_is_unknown():
    for version, date in released_versions():
        assert "XX" not in date, f"{version} has a placeholder date"
        assert date, f"{version} has no date"


def test_there_is_an_unreleased_section_and_a_release_checklist():
    assert "## [Unreleased]" in CHANGELOG
    assert "Release checklist" in CHANGELOG


LINK = re.compile(r"\]\(([^)\s]+)\)")


def documents():
    names = ["README.md", "CONTRIBUTING.md", "CHANGELOG.md"]
    return [ROOT / n for n in names] + sorted((ROOT / "docs").glob("*.md"))


@pytest.mark.parametrize("path", documents(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_relative_links_point_at_files_that_exist(path):
    missing = []
    for target in LINK.findall(path.read_text(encoding="utf-8")):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue  # a URL or an in-page anchor
        file_part = target.split("#", 1)[0]
        if file_part and not (path.parent / file_part).resolve().exists():
            missing.append(target)
    assert missing == [], f"broken links in {path.name}: {missing}"
