"""Tests for incremental reusable persistence + integration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import health
from core.health import cache
from core.health.reusable import (
    incremental_reusable_scan,
    parse_reusable_files,
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


# A pattern that should appear 3+ times across 3+ files to trigger a finding.
def _jsx_with_card(name: str) -> str:
    return f'''\
export function {name}() {{
    return (
        <button className="btn-primary">Click {name}</button>
    );
}}
'''


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.tsx").write_text(_jsx_with_card("A"))
    (repo / "b.tsx").write_text(_jsx_with_card("B"))
    (repo / "c.tsx").write_text(_jsx_with_card("C"))
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "init")
    return repo


def _pattern_keys(result):
    return sorted(p.pattern for p in result.patterns)


# --- per-file parse / assemble parity ---


class TestParseAndAssemble:
    def test_parse_assemble_matches_full_scan(self, tmp_path):
        repo = _make_repo(tmp_path)
        rel_paths = [
            str(p.relative_to(repo)).replace("\\", "/")
            for p in repo.rglob("*.tsx")
        ]
        payloads = parse_reusable_files(health, str(repo), rel_paths)
        assert set(payloads) == set(rel_paths)

        from_assemble = health.assemble_reusable_from_json(payloads)
        from_full = health.scan_reusable(str(repo))
        assert _pattern_keys(from_assemble) == _pattern_keys(from_full)

    def test_non_jsx_file_skipped(self, tmp_path):
        (tmp_path / "x.py").write_text("def f(): return 1\n")
        payloads = parse_reusable_files(health, str(tmp_path), ["x.py"])
        assert payloads == {}

    def test_empty_pattern_file_dropped(self, tmp_path):
        # JSX with no className/variant tags → no pattern → empty payload.
        (tmp_path / "e.tsx").write_text("export function E() { return null; }\n")
        payloads = parse_reusable_files(health, str(tmp_path), ["e.tsx"])
        assert payloads == {}

    def test_assemble_skips_garbage_payload(self, tmp_path):
        repo = _make_repo(tmp_path)
        rel_paths = [
            str(p.relative_to(repo)).replace("\\", "/")
            for p in repo.rglob("*.tsx")
        ]
        payloads = parse_reusable_files(health, str(repo), rel_paths)
        payloads["broken.tsx"] = "not-json"
        result = health.assemble_reusable_from_json(payloads)
        # Real pattern still surfaces.
        assert any("button" in p.pattern for p in result.patterns)


# --- end-to-end delta ---


class TestRunAllChecksReusableDelta:
    def test_first_run_populates_state(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))
        head = cache.head_hash(str(repo))
        state = cache.get_file_data(str(repo), head, "reusable")
        assert "a.tsx" in state
        assert "b.tsx" in state
        assert "c.tsx" in state

    def test_delta_run_matches_full_rerun(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))

        # Add a 4th file with the same pattern.
        (repo / "d.tsx").write_text(_jsx_with_card("D"))
        _commit(repo, "add d.tsx")

        delta = run_all_checks(str(repo))
        cache.clear(str(repo))
        full = run_all_checks(str(repo), use_cache=False)

        delta_titles = sorted(
            f.title for f in delta.findings if f.check_id == "debt.no_reuse"
        )
        full_titles = sorted(
            f.title for f in full.findings if f.check_id == "debt.no_reuse"
        )
        assert delta_titles == full_titles

    def test_deleted_file_dropped(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))

        (repo / "c.tsx").unlink()
        _commit(repo, "drop c")
        run_all_checks(str(repo))

        head = cache.head_hash(str(repo))
        state = cache.get_file_data(str(repo), head, "reusable")
        assert "c.tsx" not in state
        assert "a.tsx" in state
