"""Tests for core/code_searcher.py — Python fallback path only.

The ripgrep path is covered implicitly when rg is present on the runner;
here we exercise the fallback directly so tests don't depend on external
binaries.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.code_searcher import (
    CodeMatch, search_codebase, _python_search, SKIP_DIRS, SOURCE_EXTS,
)


@pytest.fixture
def sample_project(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "button.tsx").write_text(
        "export function Button({ label }) {\n"
        "  return <button>{label}</button>;\n"
        "}\n"
    )
    (tmp_path / "src" / "header.tsx").write_text(
        "<Header title=\"Dashboard\" />\n"
    )
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("button everywhere\n")
    (tmp_path / "README.md").write_text("# Click the button to start\n")
    return tmp_path


class TestPythonSearch:
    def test_finds_keyword(self, sample_project):
        matches = _python_search(str(sample_project), ["button"],
                                  max_per_keyword=10)
        paths = {m.path for m in matches}
        assert "src/button.tsx" in paths
        assert "README.md" in paths

    def test_skips_junk_dirs(self, sample_project):
        matches = _python_search(str(sample_project), ["button"],
                                  max_per_keyword=10)
        assert not any("node_modules" in m.path for m in matches)

    def test_respects_max_per_keyword(self, sample_project):
        (sample_project / "src" / "spam.tsx").write_text(
            "button\n" * 20
        )
        matches = _python_search(str(sample_project), ["button"],
                                  max_per_keyword=3)
        spam_hits = [m for m in matches if "spam.tsx" in m.path]
        assert len(spam_hits) <= 3

    def test_case_insensitive(self, sample_project):
        (sample_project / "src" / "mixed.tsx").write_text("Button { }")
        matches = _python_search(str(sample_project), ["button"], 10)
        assert any("mixed.tsx" in m.path for m in matches)

    def test_ignores_non_source_ext(self, tmp_path):
        (tmp_path / "binary.png").write_text("button")
        matches = _python_search(str(tmp_path), ["button"], 10)
        assert matches == []

    def test_dedupes_by_path_line(self, sample_project):
        # Search for two keywords that both hit the same line
        matches = _python_search(str(sample_project),
                                  ["button", "Button"], 10)
        # Count unique path+line pairs
        keys = [(m.path, m.line_number) for m in matches]
        assert len(keys) == len(set(keys))


class TestDispatch:
    def test_empty_keywords(self, sample_project):
        assert search_codebase(str(sample_project), []) == []

    def test_blank_keywords_filtered(self, sample_project):
        assert search_codebase(str(sample_project), ["", "   "]) == []

    def test_bad_dir(self, tmp_path):
        assert search_codebase(str(tmp_path / "nope"), ["x"]) == []
