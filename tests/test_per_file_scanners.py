"""Tests for per-file Rust scanner APIs (scan_monsters_files, scan_tech_debt_files).

These are the building blocks for git-delta scans: callers supply a list
of paths, the scanner only analyzes those files, and the result has the
same shape as the full scanner output.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import health


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _giant_python(line_count: int) -> str:
    """A Python file with `line_count` non-empty lines and 1 class + 1 function."""
    body_lines = ["class Foo:", "    def bar(self):"]
    body_lines.extend(f"        x{i} = {i}" for i in range(line_count - 2))
    return "\n".join(body_lines) + "\n"


# --- scan_monsters_files ---


class TestScanMonstersFiles:
    def test_only_listed_files_are_analyzed(self, tmp_path):
        """Files NOT in the list are ignored, even if they're monsters."""
        _write(tmp_path / "big_a.py", _giant_python(600))
        _write(tmp_path / "big_b.py", _giant_python(600))

        result = health.scan_monsters_files(str(tmp_path), ["big_a.py"])
        paths = [m.path for m in result.monsters]
        assert paths == ["big_a.py"]

    def test_small_file_produces_no_finding(self, tmp_path):
        _write(tmp_path / "tiny.py", "x = 1\n")
        result = health.scan_monsters_files(str(tmp_path), ["tiny.py"])
        assert result.monsters == []

    def test_missing_file_silently_skipped(self, tmp_path):
        """Caller may pass a path that was deleted between commits — no crash."""
        result = health.scan_monsters_files(str(tmp_path), ["nonexistent.py"])
        assert result.monsters == []

    def test_non_source_extension_skipped(self, tmp_path):
        """E.g. config files in the changed-files list shouldn't produce errors."""
        _write(tmp_path / "config.toml", "x = 1\n" * 700)
        result = health.scan_monsters_files(str(tmp_path), ["config.toml"])
        assert result.monsters == []

    def test_generated_file_skipped(self, tmp_path):
        """Same generated-file rule as the full scanner."""
        _write(tmp_path / "schema.generated.ts", "x = 1;\n" * 700)
        result = health.scan_monsters_files(str(tmp_path), ["schema.generated.ts"])
        assert result.monsters == []

    def test_non_directory_root_raises(self, tmp_path):
        with pytest.raises(ValueError):
            health.scan_monsters_files(str(tmp_path / "missing"), [])

    def test_matches_full_scanner_when_set_is_complete(self, tmp_path):
        """The per-file API must produce the SAME output as the full scanner
        when given the full list of source files."""
        _write(tmp_path / "huge.py", _giant_python(700))
        _write(tmp_path / "small.py", "x = 1\n")
        _write(tmp_path / "sub" / "another.py", _giant_python(600))

        full = health.scan_monsters(str(tmp_path))
        partial = health.scan_monsters_files(
            str(tmp_path),
            ["huge.py", "small.py", "sub/another.py"],
        )
        full_paths = sorted(m.path for m in full.monsters)
        partial_paths = sorted(m.path for m in partial.monsters)
        assert full_paths == partial_paths

    def test_path_normalization_accepts_backslash(self, tmp_path):
        """Windows-style separators in the input are normalized to '/'."""
        _write(tmp_path / "sub" / "deep.py", _giant_python(700))
        result = health.scan_monsters_files(str(tmp_path), ["sub\\deep.py"])
        assert [m.path for m in result.monsters] == ["sub/deep.py"]


# --- scan_tech_debt_files ---


class TestScanTechDebtFiles:
    def test_only_listed_files_analyzed_for_todos(self, tmp_path):
        _write(tmp_path / "a.py", "# TODO: fix me\nx = 1\n")
        _write(tmp_path / "b.py", "# FIXME: also broken\ny = 2\n")

        result = health.scan_tech_debt_files(str(tmp_path), ["a.py"])
        todo_paths = [t.path for t in result.todos]
        assert todo_paths == ["a.py"]

    def test_python_missing_types_per_file(self, tmp_path):
        _write(tmp_path / "untyped.py", "def add(a, b):\n    return a + b\n")
        result = health.scan_tech_debt_files(str(tmp_path), ["untyped.py"])
        assert any(mt.path == "untyped.py" for mt in result.missing_types)

    def test_test_file_skipped_for_type_check(self, tmp_path):
        """is_test_path heuristic must apply to per-file calls too —
        tests/foo.py with no types should not be flagged."""
        _write(tmp_path / "tests" / "test_x.py", "def test_add(a, b):\n    assert a + b\n")
        result = health.scan_tech_debt_files(str(tmp_path), ["tests/test_x.py"])
        assert all(mt.path != "tests/test_x.py" for mt in result.missing_types)

    def test_missing_file_silently_skipped(self, tmp_path):
        result = health.scan_tech_debt_files(str(tmp_path), ["gone.py"])
        assert result.todos == []
        assert result.missing_types == []
        assert result.error_gaps == []
        assert result.hardcoded == []

    def test_non_source_extension_skipped(self, tmp_path):
        _write(tmp_path / "x.md", "# TODO: docs\n")
        result = health.scan_tech_debt_files(str(tmp_path), ["x.md"])
        assert result.todos == []

    def test_matches_full_scanner_when_set_is_complete(self, tmp_path):
        _write(tmp_path / "a.py",
               "# TODO: a\ndef f(x):\n    return x\n")
        _write(tmp_path / "b.py",
               "def g(y, z):\n    try:\n        pass\n    except:\n        pass\n")

        full = health.scan_tech_debt(str(tmp_path))
        partial = health.scan_tech_debt_files(str(tmp_path), ["a.py", "b.py"])

        # Findings come back as PyClass objects — compare by their stable fields.
        def _key(items, fields):
            return sorted(tuple(getattr(it, f) for f in fields) for it in items)

        assert _key(full.todos, ("path", "line", "kind")) == _key(partial.todos, ("path", "line", "kind"))
        assert _key(full.missing_types, ("path", "line", "function_name")) == \
               _key(partial.missing_types, ("path", "line", "function_name"))
        assert _key(full.error_gaps, ("path", "line", "kind")) == \
               _key(partial.error_gaps, ("path", "line", "kind"))

    def test_non_directory_root_raises(self, tmp_path):
        with pytest.raises(ValueError):
            health.scan_tech_debt_files(str(tmp_path / "missing"), ["a.py"])
