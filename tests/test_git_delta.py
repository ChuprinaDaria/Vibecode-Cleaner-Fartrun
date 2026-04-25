"""Tests for core.health.git_delta primitives."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from core.health import cache, git_delta
from core.health.models import HealthReport


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    """Each test gets its own XDG cache so they don't pollute each other
    or the user's real ~/.cache/fartrun."""
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
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _make_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("a = 1\n")
    (repo / "b.py").write_text("b = 2\n")
    _git(repo, "init", "-q", "-b", "main")
    head = _commit(repo, "init")
    return repo, head


# --- changed_files_since ---


def test_changed_files_when_nothing_moved(tmp_path):
    repo, head = _make_repo(tmp_path)
    changes = git_delta.changed_files_since(str(repo), head)
    assert changes == []


def test_changed_files_after_modify(tmp_path):
    repo, anchor = _make_repo(tmp_path)
    (repo / "a.py").write_text("a = 99\n")
    _commit(repo, "edit a")

    changes = git_delta.changed_files_since(str(repo), anchor)
    assert len(changes) == 1
    assert changes[0].path == "a.py"
    assert changes[0].status == "M"


def test_changed_files_add_modify_delete(tmp_path):
    repo, anchor = _make_repo(tmp_path)
    (repo / "a.py").write_text("a = 99\n")           # modify
    (repo / "c.py").write_text("c = 3\n")            # add
    (repo / "b.py").unlink()                          # delete
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "shake")

    plan = git_delta.changed_files_since(str(repo), anchor)
    assert plan is not None
    by_path = {c.path: c.status for c in plan}
    assert by_path == {"a.py": "M", "c.py": "A", "b.py": "D"}


def test_changed_files_returns_none_for_unknown_hash(tmp_path):
    repo, _ = _make_repo(tmp_path)
    bogus = "0" * 40
    assert git_delta.changed_files_since(str(repo), bogus) is None


def test_changed_files_returns_none_outside_git(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert git_delta.changed_files_since(str(plain), "0" * 40) is None


# --- find_ancestor_cache_hash ---


def test_ancestor_lookup_finds_matching_cached_commit(tmp_path):
    repo, c0 = _make_repo(tmp_path)
    cache.put(str(repo), HealthReport(project_dir=str(repo)))  # cache @ c0

    # Add 3 commits — c0 should still be findable as an ancestor.
    for i in range(3):
        (repo / f"x{i}.py").write_text(f"x = {i}\n")
        _commit(repo, f"edit {i}")

    found = git_delta.find_ancestor_cache_hash(str(repo))
    assert found == c0


def test_ancestor_lookup_picks_most_recent_when_multiple_cached(tmp_path):
    repo, c0 = _make_repo(tmp_path)
    cache.put(str(repo), HealthReport(project_dir=str(repo)))

    (repo / "extra.py").write_text("extra = 1\n")
    c1 = _commit(repo, "c1")
    cache.put(str(repo), HealthReport(project_dir=str(repo)))

    (repo / "extra.py").write_text("extra = 2\n")
    _commit(repo, "c2")

    # Both c0 and c1 are cached; lookup must return c1 (closer to HEAD).
    assert git_delta.find_ancestor_cache_hash(str(repo)) == c1


def test_ancestor_lookup_returns_none_when_no_cache_entries(tmp_path):
    repo, _ = _make_repo(tmp_path)
    assert git_delta.find_ancestor_cache_hash(str(repo)) is None


def test_ancestor_lookup_respects_lookback(tmp_path):
    repo, c0 = _make_repo(tmp_path)
    cache.put(str(repo), HealthReport(project_dir=str(repo)))

    # 5 commits past c0; lookback=2 must not see c0.
    for i in range(5):
        (repo / f"f{i}.py").write_text(f"f = {i}\n")
        _commit(repo, f"c{i}")

    assert git_delta.find_ancestor_cache_hash(str(repo), max_lookback=2) is None
    assert git_delta.find_ancestor_cache_hash(str(repo), max_lookback=10) == c0


# --- plan_delta ---


def test_plan_delta_returns_none_without_cache(tmp_path):
    repo, _ = _make_repo(tmp_path)
    assert git_delta.plan_delta(str(repo)) is None


def test_plan_delta_combines_anchor_and_diff(tmp_path):
    repo, c0 = _make_repo(tmp_path)
    cache.put(str(repo), HealthReport(project_dir=str(repo)))

    (repo / "a.py").write_text("a = 99\n")
    (repo / "new.py").write_text("new = 1\n")
    _commit(repo, "edit + add")

    plan = git_delta.plan_delta(str(repo))
    assert plan is not None
    assert plan.ancestor_hash == c0
    assert sorted(plan.added_or_modified) == ["a.py", "new.py"]
    assert plan.deleted == []


def test_plan_delta_categorises_deleted(tmp_path):
    repo, _ = _make_repo(tmp_path)
    cache.put(str(repo), HealthReport(project_dir=str(repo)))

    (repo / "b.py").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "drop b")

    plan = git_delta.plan_delta(str(repo))
    assert plan is not None
    assert plan.added_or_modified == []
    assert plan.deleted == ["b.py"]
