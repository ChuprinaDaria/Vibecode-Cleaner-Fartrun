"""Tests for case-insensitive README detection (Task 14).

The old detector hardcoded ["README.md", "README.rst", ...] and missed
variants like README.MD (which this very repo uses).
"""
from __future__ import annotations

import pytest

from core.health.docs_context import check_readme
from core.health.models import HealthReport


@pytest.fixture
def empty_report():
    return HealthReport(project_dir="")


@pytest.mark.parametrize("filename", [
    "README.md",
    "README.MD",
    "README.Md",
    "Readme.md",
    "readme.md",
    "README.rst",
    "README.RST",
    "README.txt",
    "README",
    "readme",
    "README.mdx",
    "README.adoc",
])
def test_readme_variant_detected(tmp_path, filename, empty_report):
    (tmp_path / filename).write_text(
        "# Project\n\nInstall: pip install .\n\nRun: python -m app\n"
        + "word " * 25
    )
    empty_report.project_dir = str(tmp_path)
    check_readme(empty_report, str(tmp_path))
    titles = [f.title for f in empty_report.findings]
    assert not any("No README" in t for t in titles), (
        f"{filename} should be detected; findings: {titles}"
    )


def test_no_readme_flagged_when_missing(tmp_path, empty_report):
    (tmp_path / "other.txt").write_text("hi")
    check_readme(empty_report, str(tmp_path))
    titles = [f.title for f in empty_report.findings]
    assert any("No README" in t for t in titles)


def test_readme_subdirectory_ignored(tmp_path, empty_report):
    """A README in a subdir is not the project README."""
    sub = tmp_path / "docs"
    sub.mkdir()
    (sub / "README.md").write_text("sub")
    check_readme(empty_report, str(tmp_path))
    titles = [f.title for f in empty_report.findings]
    assert any("No README" in t for t in titles)
