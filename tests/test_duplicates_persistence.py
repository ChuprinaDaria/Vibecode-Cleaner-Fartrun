"""Tests for incremental duplicates persistence + integration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import health
from core.health import cache
from core.health.duplicates import (
    incremental_duplicates_scan,
    parse_duplicates_files,
)
from core.health.project_map import run_all_checks


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg_cache"))
    yield


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env={
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": sys.exec_prefix + ":/usr/bin:/bin",
            "HOME": str(repo.parent),
        },
    )
    return res.stdout.strip()


def _commit(repo: Path, msg: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


# A 12-line block that we'll plant in two files so the duplicates
# detector has something to find. (MIN_DUPLICATE_LINES = 10 in the Rust
# crate so we go a couple lines over.)
_DUP_BLOCK = """\
def normalize_user(user):
    name = user.get("name", "").strip()
    email = user.get("email", "").lower()
    age = user.get("age", 0)
    if not name:
        raise ValueError("name required")
    if "@" not in email:
        raise ValueError("invalid email")
    if age < 0:
        raise ValueError("age negative")
    return {"name": name, "email": email, "age": age}
"""


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    # Two files with identical 12-line block → guaranteed duplicate.
    (repo / "a.py").write_text(_DUP_BLOCK + "\nx_a = 1\n")
    (repo / "b.py").write_text(_DUP_BLOCK + "\nx_b = 2\n")
    (repo / "c.py").write_text(
        "def unique():\n"
        + "\n".join(f"    x = {i}" for i in range(15))
        + "\n"
    )
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "init")
    return repo


def _dup_keys(result):
    return sorted(
        (d.file_a, d.file_b, d.line_count)
        for d in result.duplicates
    )


# --- per-file parse / assemble parity ---


class TestParseAndAssemble:
    def test_parse_assemble_matches_full_scan(self, tmp_path):
        repo = _make_repo(tmp_path)
        rel_paths = sorted(
            str(p.relative_to(repo)).replace("\\", "/")
            for p in repo.rglob("*.py")
        )
        payloads = parse_duplicates_files(health, str(repo), rel_paths)
        assert "a.py" in payloads
        assert "b.py" in payloads

        from_assemble = health.assemble_duplicates_from_json(list(payloads.values()))
        from_full = health.scan_duplicates(str(repo))
        assert _dup_keys(from_assemble) == _dup_keys(from_full)

    def test_below_threshold_files_have_no_payload(self, tmp_path):
        # 5-line file is below MIN_DUPLICATE_LINES (10), no payload.
        (tmp_path / "tiny.py").write_text(
            "x = 1\n" "y = 2\n" "z = 3\n" "a = 4\n" "b = 5\n"
        )
        payloads = parse_duplicates_files(health, str(tmp_path), ["tiny.py"])
        assert payloads == {}

    def test_assemble_skips_garbage_payloads(self, tmp_path):
        repo = _make_repo(tmp_path)
        rel_paths = [
            str(p.relative_to(repo)).replace("\\", "/")
            for p in repo.rglob("*.py")
        ]
        payloads = parse_duplicates_files(health, str(repo), rel_paths)
        payloads["broken.py"] = "not-json"
        result = health.assemble_duplicates_from_json(list(payloads.values()))
        # The (a.py, b.py) duplicate still surfaces despite the bad row.
        assert any(
            ("a.py" in (d.file_a, d.file_b)) and ("b.py" in (d.file_a, d.file_b))
            for d in result.duplicates
        )


# --- end-to-end delta scan ---


class TestRunAllChecksDuplicatesDelta:
    def test_first_run_populates_state(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))
        head = cache.head_hash(str(repo))
        state = cache.get_file_data(str(repo), head, "duplicates")
        assert "a.py" in state
        assert "b.py" in state

    def test_delta_run_matches_full_rerun(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))

        # Add a third copy of the dup block.
        (repo / "c.py").write_text(_DUP_BLOCK + "\nx_c = 3\n")
        _commit(repo, "duplicate in c.py")

        delta = run_all_checks(str(repo))
        cache.clear(str(repo))
        full = run_all_checks(str(repo), use_cache=False)

        # Both runs should identify the same set of duplicate findings on
        # the report (same titles).
        delta_dups = sorted(
            f.title for f in delta.findings
            if f.check_id == "dead.duplicates"
        )
        full_dups = sorted(
            f.title for f in full.findings
            if f.check_id == "dead.duplicates"
        )
        assert delta_dups == full_dups

    def test_deleted_file_dropped_from_state(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))

        (repo / "b.py").unlink()
        _commit(repo, "drop b")
        run_all_checks(str(repo))

        head = cache.head_hash(str(repo))
        state = cache.get_file_data(str(repo), head, "duplicates")
        assert "b.py" not in state
        assert "a.py" in state
