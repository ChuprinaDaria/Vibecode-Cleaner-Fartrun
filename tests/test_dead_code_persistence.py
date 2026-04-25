"""End-to-end tests for incremental dead_code via file_data_cache.

These check the full chain: run_all_checks on HEAD A populates the
file_data table, run_all_checks on HEAD B (B child of A) consumes that
state via incremental_dead_code_scan, and the resulting findings match
a fresh full re-scan from a cleared cache.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from core.health import cache
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


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pkg").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "models.py").write_text(
        "class User:\n    pass\n\nclass Order:\n    pass\n"
    )
    (repo / "pkg" / "service.py").write_text(
        "from pkg.models import User\n\n"
        "def make_user():\n    return User()\n"
    )
    (repo / "pkg" / "unused.py").write_text(
        "import json\n"
        "def helper():\n    return 1\n"
    )
    (repo / "main.py").write_text(
        "from pkg.service import make_user\n"
        "if __name__ == '__main__':\n    print(make_user())\n"
    )
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "init")
    return repo


def _dead_code_findings(report):
    return sorted(
        (f.check_id, (f.details or {}).get("path"))
        for f in report.findings
        if f.check_id.startswith("dead.")
    )


# --- file_data_cache primitives ---


class TestFileDataCacheApi:
    def test_round_trip(self, tmp_path):
        repo = _make_repo(tmp_path)
        head = cache.head_hash(str(repo))
        assert head is not None

        state = {"a.py": '{"x": 1}', "b.py": '{"y": 2}'}
        assert cache.put_file_data(str(repo), head, "dead_code", state) is True

        loaded = cache.get_file_data(str(repo), head, "dead_code")
        assert loaded == state

    def test_put_replaces_full_set(self, tmp_path):
        repo = _make_repo(tmp_path)
        head = cache.head_hash(str(repo))
        cache.put_file_data(str(repo), head, "dead_code",
                             {"a.py": "x", "b.py": "y"})
        cache.put_file_data(str(repo), head, "dead_code",
                             {"a.py": "x2"})
        loaded = cache.get_file_data(str(repo), head, "dead_code")
        # b.py wiped, only a.py with new payload remains.
        assert loaded == {"a.py": "x2"}

    def test_get_for_unknown_hash_returns_empty(self, tmp_path):
        repo = _make_repo(tmp_path)
        loaded = cache.get_file_data(str(repo), "0" * 40, "dead_code")
        assert loaded == {}

    def test_clear_wipes_file_data_too(self, tmp_path):
        repo = _make_repo(tmp_path)
        head = cache.head_hash(str(repo))
        cache.put_file_data(str(repo), head, "dead_code", {"a.py": "x"})
        cache.clear(str(repo))
        assert cache.get_file_data(str(repo), head, "dead_code") == {}


# --- end-to-end delta scan via file_data_cache ---


class TestRunAllChecksDeadCodeDelta:
    def test_first_run_populates_file_data_cache(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))

        head = cache.head_hash(str(repo))
        state = cache.get_file_data(str(repo), head, "dead_code")
        # Every Python file the scanner processes should be persisted.
        assert "main.py" in state
        assert "pkg/service.py" in state
        assert "pkg/unused.py" in state

    def test_delta_run_matches_full_rerun(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))

        # Modify pkg/unused.py — add another unused import.
        (repo / "pkg" / "unused.py").write_text(
            "import json\n"
            "import os\n"          # newly unused
            "def helper():\n    return 1\n"
        )
        _commit(repo, "edit unused.py")

        delta_report = run_all_checks(str(repo))

        # Independent baseline: clear and full rerun.
        cache.clear(str(repo))
        full_report = run_all_checks(str(repo), use_cache=False)

        assert _dead_code_findings(delta_report) == _dead_code_findings(full_report)

        # The freshly-added 'os' should be flagged.
        os_unused = [
            f for f in delta_report.findings
            if f.check_id == "dead.unused_imports"
            and "os" in f.title
        ]
        assert os_unused, "delta path missed the new unused import"

    def test_delta_run_persists_updated_state(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))
        head_a = cache.head_hash(str(repo))
        state_a = cache.get_file_data(str(repo), head_a, "dead_code")

        (repo / "pkg" / "service.py").write_text(
            "from pkg.models import User, Order\n\n"
            "def make_user():\n    return User()\n"
        )
        _commit(repo, "edit service.py")
        run_all_checks(str(repo))

        head_b = cache.head_hash(str(repo))
        state_b = cache.get_file_data(str(repo), head_b, "dead_code")
        # Cache populated under the new HEAD.
        assert state_b
        assert "pkg/service.py" in state_b
        # service.py payload differs from the previous one — was re-parsed.
        assert state_b["pkg/service.py"] != state_a["pkg/service.py"]
        # Unchanged file payload was carried over verbatim.
        assert state_b["main.py"] == state_a["main.py"]
