"""Tests for the incremental dead-code building blocks.

These verify:
- parse_dead_code_file_json round-trips through assemble_dead_code_from_json
  and produces the same DeadCodeResult as scan_dead_code on the same fixture
- incremental_dead_code_scan(prior, changed) gives the same result as a
  full re-parse, even when some files came from a stale prior_state and
  others were re-parsed
"""

from __future__ import annotations

from pathlib import Path

import pytest

import health
from core.health.dead_code import (
    incremental_dead_code_scan,
    parse_dead_code_files,
)


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _make_project(root: Path) -> None:
    _write(root / "pkg" / "__init__.py", "")
    _write(root / "pkg" / "models.py",
           "class User:\n    pass\n\nclass Order:\n    pass\n")
    _write(root / "pkg" / "service.py",
           "from pkg.models import User\n\n"
           "def make_user():\n    return User()\n")
    _write(root / "pkg" / "unused.py",
           "import json\n"
           "def helper():\n    return 1\n")
    _write(root / "main.py",
           "from pkg.service import make_user\n"
           "if __name__ == '__main__':\n    print(make_user())\n")


def _result_key(result):
    """Convert DeadCodeResult to a comparable tuple set."""
    return (
        sorted((u.path, u.line, u.name) for u in result.unused_imports),
        sorted((d.path, d.line, d.name, d.kind) for d in result.unused_definitions),
        sorted(result.orphan_files),
        sorted((c.path, c.start_line, c.end_line) for c in result.commented_blocks),
    )


# --- parse + assemble equivalence ---


class TestParseAndAssemble:
    def test_per_file_parse_matches_full_scan(self, tmp_path):
        _make_project(tmp_path)
        # Walk the same files scan_dead_code would and parse them via the
        # per-file API.
        rel_paths = sorted(
            str(p.relative_to(tmp_path)).replace("\\", "/")
            for p in tmp_path.rglob("*.py")
        )
        payloads = parse_dead_code_files(health, str(tmp_path), rel_paths)
        assert set(payloads) == set(rel_paths)

        from_assemble = health.assemble_dead_code_from_json(list(payloads.values()))
        from_full = health.scan_dead_code(str(tmp_path), [])

        assert _result_key(from_assemble) == _result_key(from_full)

    def test_unsupported_extension_skipped(self, tmp_path):
        _write(tmp_path / "config.toml", "x = 1\n")
        payloads = parse_dead_code_files(health, str(tmp_path), ["config.toml"])
        assert payloads == {}

    def test_missing_file_skipped(self, tmp_path):
        payloads = parse_dead_code_files(health, str(tmp_path), ["gone.py"])
        assert payloads == {}

    def test_parse_file_json_raises_on_unknown_lang(self):
        with pytest.raises(ValueError):
            health.parse_dead_code_file_json("foo.cobol", "x", "cobol")

    def test_assemble_skips_garbage_payloads(self, tmp_path):
        _make_project(tmp_path)
        rel_paths = sorted(
            str(p.relative_to(tmp_path)).replace("\\", "/")
            for p in tmp_path.rglob("*.py")
        )
        payloads = parse_dead_code_files(health, str(tmp_path), rel_paths)
        # Inject a couple of bad payloads to ensure they're skipped, not fatal.
        payload_list = list(payloads.values()) + ["{}", "not-json"]
        result = health.assemble_dead_code_from_json(payload_list)
        # Real findings still come through.
        assert any(u.name == "json" for u in result.unused_imports)


# --- incremental scan equivalence ---


class TestIncrementalDeadCodeScan:
    def test_no_changes_replays_prior_state(self, tmp_path):
        _make_project(tmp_path)
        rel_paths = sorted(
            str(p.relative_to(tmp_path)).replace("\\", "/")
            for p in tmp_path.rglob("*.py")
        )
        prior = parse_dead_code_files(health, str(tmp_path), rel_paths)

        result, new_state = incremental_dead_code_scan(
            health, str(tmp_path), prior, changed_paths=set(),
        )
        # State unchanged.
        assert set(new_state) == set(prior)
        # Result identical to a full scan.
        full = health.scan_dead_code(str(tmp_path), [])
        assert _result_key(result) == _result_key(full)

    def test_modified_file_re_parsed(self, tmp_path):
        _make_project(tmp_path)
        rel_paths = sorted(
            str(p.relative_to(tmp_path)).replace("\\", "/")
            for p in tmp_path.rglob("*.py")
        )
        prior = parse_dead_code_files(health, str(tmp_path), rel_paths)

        # Modify unused.py — add a real use of `helper` inside the file
        # itself (still unused from outside, so doesn't affect the cross
        # file analysis but proves we re-parse).
        (tmp_path / "pkg" / "unused.py").write_text(
            "import json\n"
            "import os\n"          # newly unused
            "def helper():\n    return 1\n"
        )

        result, new_state = incremental_dead_code_scan(
            health, str(tmp_path), prior,
            changed_paths={"pkg/unused.py"},
        )

        # State preserved for unchanged files; new payload for unused.py.
        assert new_state["pkg/unused.py"] != prior["pkg/unused.py"]
        assert new_state["pkg/service.py"] == prior["pkg/service.py"]

        # The freshly-added `os` import should now appear as unused.
        unused_names = sorted(u.name for u in result.unused_imports
                              if u.path == "pkg/unused.py")
        assert "os" in unused_names

        # Equivalence: same as a fresh full scan after the edit.
        full = health.scan_dead_code(str(tmp_path), [])
        assert _result_key(result) == _result_key(full)

    def test_deleted_file_dropped_from_state(self, tmp_path):
        _make_project(tmp_path)
        rel_paths = sorted(
            str(p.relative_to(tmp_path)).replace("\\", "/")
            for p in tmp_path.rglob("*.py")
        )
        prior = parse_dead_code_files(health, str(tmp_path), rel_paths)

        # Pretend pkg/unused.py was deleted between scans.
        (tmp_path / "pkg" / "unused.py").unlink()
        result, new_state = incremental_dead_code_scan(
            health, str(tmp_path), prior,
            changed_paths=set(),
            deleted_paths={"pkg/unused.py"},
        )
        assert "pkg/unused.py" not in new_state
        # Result must NOT carry the unused-import finding for the deleted file.
        assert all(u.path != "pkg/unused.py" for u in result.unused_imports)

        # Equivalent to a fresh full scan.
        full = health.scan_dead_code(str(tmp_path), [])
        assert _result_key(result) == _result_key(full)
