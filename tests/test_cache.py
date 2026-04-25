"""Tests for core.health.cache: persistence layer for scan reports."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from core.health import cache
from core.health.models import HealthFinding, HealthReport


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    """Redirect XDG_CACHE_HOME so tests never touch the user's real cache."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    yield


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": sys.exec_prefix + ":/usr/bin:/bin",
            "HOME": str(repo.parent),
        },
    )


def _make_clean_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "hello.py").write_text("print('hi')\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _sample_report(project_dir: str) -> HealthReport:
    r = HealthReport(project_dir=project_dir)
    r.findings.append(HealthFinding(
        check_id="dead.unused_imports",
        title="t",
        severity="medium",
        message="m",
        details={"name": "X", "line": 4},
    ))
    r.file_tree = {"total_files": 1}
    r.entry_points = [{"path": "hello.py", "kind": "main", "description": "d"}]
    return r


# --- bypass cases (no caching attempted) ---


def test_bypass_when_not_git_repo(tmp_path):
    """A plain directory has no HEAD — get returns None, put returns False."""
    plain = tmp_path / "plain"
    plain.mkdir()
    assert cache.head_hash(str(plain)) is None
    assert cache.get(str(plain)) is None
    assert cache.put(str(plain), _sample_report(str(plain))) is False


def test_bypass_when_working_tree_dirty(tmp_path):
    """Uncommitted changes mean a cached scan would lie — bypass."""
    repo = _make_clean_repo(tmp_path)
    assert cache.head_hash(str(repo)) is not None  # clean: caching ON

    (repo / "hello.py").write_text("print('changed')\n")
    assert cache.head_hash(str(repo)) is None      # dirty: caching OFF
    assert cache.get(str(repo)) is None
    assert cache.put(str(repo), _sample_report(str(repo))) is False


# --- happy path ---


def test_round_trip_clean_repo(tmp_path):
    repo = _make_clean_repo(tmp_path)
    report = _sample_report(str(repo))
    assert cache.put(str(repo), report) is True

    got = cache.get(str(repo))
    assert got is not None
    assert got.project_dir == report.project_dir
    assert len(got.findings) == 1
    assert got.findings[0].check_id == "dead.unused_imports"
    assert got.findings[0].details == {"name": "X", "line": 4}
    assert got.file_tree == {"total_files": 1}
    assert got.entry_points == report.entry_points


def test_miss_returns_none(tmp_path):
    repo = _make_clean_repo(tmp_path)
    assert cache.get(str(repo)) is None


def test_invalidates_on_new_commit(tmp_path):
    """A new commit changes HEAD — old cache entry no longer matches."""
    repo = _make_clean_repo(tmp_path)
    cache.put(str(repo), _sample_report(str(repo)))
    assert cache.get(str(repo)) is not None

    (repo / "hello.py").write_text("print('v2')\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "v2")

    # New HEAD, no entry yet — miss.
    assert cache.get(str(repo)) is None


def test_schema_version_bump_invalidates(tmp_path, monkeypatch):
    repo = _make_clean_repo(tmp_path)
    cache.put(str(repo), _sample_report(str(repo)))
    assert cache.get(str(repo)) is not None

    monkeypatch.setattr(cache, "CACHE_SCHEMA_VERSION", cache.CACHE_SCHEMA_VERSION + 1)
    assert cache.get(str(repo)) is None  # old entry hidden by schema bump


def test_clear_specific_project(tmp_path):
    repo_a = _make_clean_repo(tmp_path)
    # Second repo in a sibling tmp path
    other_root = tmp_path / "other"
    other_root.mkdir()
    repo_b = other_root / "repo"
    repo_b.mkdir()
    (repo_b / "x.py").write_text("x = 1\n")
    _git(repo_b, "init", "-q", "-b", "main")
    _git(repo_b, "add", ".")
    _git(repo_b, "commit", "-q", "-m", "init")

    cache.put(str(repo_a), _sample_report(str(repo_a)))
    cache.put(str(repo_b), _sample_report(str(repo_b)))

    removed = cache.clear(str(repo_a))
    assert removed == 1
    assert cache.get(str(repo_a)) is None
    assert cache.get(str(repo_b)) is not None  # untouched


def test_clear_all(tmp_path):
    repo = _make_clean_repo(tmp_path)
    cache.put(str(repo), _sample_report(str(repo)))
    assert cache.clear() >= 1
    assert cache.get(str(repo)) is None


def test_db_lives_under_xdg_cache_home(tmp_path):
    """The redirected XDG_CACHE_HOME must be honoured."""
    p = cache.cache_db_path()
    assert str(p).startswith(str(tmp_path / "cache" / "fartrun"))
