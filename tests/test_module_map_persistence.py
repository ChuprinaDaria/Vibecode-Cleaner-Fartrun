"""Tests for incremental module_map persistence + integration.

Mirrors test_dead_code_persistence.py: per-file parse/assemble parity,
file_data_cache round-trip, and end-to-end delta scan against a real
git repo whose findings should match a fresh full re-scan.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import health
from core.health import cache
from core.health.module_map import (
    incremental_module_map_scan,
    parse_module_map_files,
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


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pkg").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "models.py").write_text(
        "class User:\n    pass\n"
    )
    (repo / "pkg" / "service.py").write_text(
        "from pkg.models import User\n\n"
        "def make_user():\n    return User()\n"
    )
    (repo / "pkg" / "circular_a.py").write_text(
        "from pkg.circular_b import b_thing\n"
        "def a_thing(): return b_thing()\n"
    )
    (repo / "pkg" / "circular_b.py").write_text(
        "from pkg.circular_a import a_thing\n"
        "def b_thing(): return a_thing()\n"
    )
    (repo / "main.py").write_text(
        "from pkg.service import make_user\n"
        "if __name__ == '__main__':\n    print(make_user())\n"
    )
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "init")
    return repo


def _module_map_summary(report):
    """Stable comparison key for ModuleMap findings + report.module_map."""
    mm = report.module_map
    return (
        sorted(tuple(h) for h in mm["hub_modules"]),
        sorted(
            (cd.file_a, cd.file_b, cd.is_lazy)
            for cd in mm["circular_deps"]
        ),
        sorted(mm["orphan_candidates"]),
    )


# --- per-file parse/assemble ---


class TestParseAndAssemble:
    def test_parse_and_assemble_match_full_scan(self, tmp_path):
        repo = _make_repo(tmp_path)
        rel_paths = sorted(
            str(p.relative_to(repo)).replace("\\", "/")
            for p in repo.rglob("*.py")
        )

        payloads = parse_module_map_files(health, str(repo), rel_paths)
        assert set(payloads) == set(rel_paths)

        from_assemble = health.assemble_module_map_from_json(
            str(repo), [], payloads, None,
        )
        from_full = health.scan_module_map(str(repo), [])

        # hub_modules, circular_deps, orphan_candidates should agree.
        a_hubs = sorted(tuple(h) for h in from_assemble.hub_modules)
        b_hubs = sorted(tuple(h) for h in from_full.hub_modules)
        assert a_hubs == b_hubs

        a_circ = sorted(
            (cd.file_a, cd.file_b, cd.is_lazy) for cd in from_assemble.circular_deps
        )
        b_circ = sorted(
            (cd.file_a, cd.file_b, cd.is_lazy) for cd in from_full.circular_deps
        )
        assert a_circ == b_circ

    def test_assemble_skips_garbage_payloads(self, tmp_path):
        repo = _make_repo(tmp_path)
        rel_paths = [
            str(p.relative_to(repo)).replace("\\", "/")
            for p in repo.rglob("*.py")
        ]
        payloads = parse_module_map_files(health, str(repo), rel_paths)
        payloads["broken.py"] = "not-json"

        result = health.assemble_module_map_from_json(
            str(repo), [], payloads, None,
        )
        # Real findings still come through despite the bad row.
        circ = [(c.file_a, c.file_b) for c in result.circular_deps]
        assert any("circular" in a or "circular" in b for a, b in circ)

    def test_unsupported_extension_skipped(self, tmp_path):
        (tmp_path / "config.toml").write_text("x = 1\n")
        payloads = parse_module_map_files(health, str(tmp_path), ["config.toml"])
        assert payloads == {}


# --- end-to-end delta scan ---


class TestRunAllChecksModuleMapDelta:
    def test_first_run_populates_module_map_state(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))

        head = cache.head_hash(str(repo))
        state = cache.get_file_data(str(repo), head, "module_map")
        assert "main.py" in state
        assert "pkg/service.py" in state
        assert "pkg/circular_a.py" in state

    def test_delta_run_matches_full_rerun(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))

        # Add a new module + import it from main.py.
        (repo / "pkg" / "extras.py").write_text(
            "def extra(): return 'hello'\n"
        )
        (repo / "main.py").write_text(
            "from pkg.service import make_user\n"
            "from pkg.extras import extra\n"
            "if __name__ == '__main__':\n    print(make_user(), extra())\n"
        )
        _commit(repo, "add pkg.extras")

        delta_report = run_all_checks(str(repo))

        cache.clear(str(repo))
        full_report = run_all_checks(str(repo), use_cache=False)

        assert _module_map_summary(delta_report) == _module_map_summary(full_report)

    def test_delta_run_persists_updated_state(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))
        head_a = cache.head_hash(str(repo))
        state_a = cache.get_file_data(str(repo), head_a, "module_map")

        # Modify service.py — add another import.
        (repo / "pkg" / "service.py").write_text(
            "from pkg.models import User\n"
            "from pkg import circular_a\n"
            "def make_user():\n    return User()\n"
        )
        _commit(repo, "edit service.py")
        run_all_checks(str(repo))

        head_b = cache.head_hash(str(repo))
        state_b = cache.get_file_data(str(repo), head_b, "module_map")
        assert state_b
        # service.py re-parsed; payload differs.
        assert state_b["pkg/service.py"] != state_a["pkg/service.py"]
        # main.py unchanged → carried over verbatim.
        assert state_b["main.py"] == state_a["main.py"]

    def test_deleted_file_removed_from_state(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_all_checks(str(repo))

        (repo / "pkg" / "circular_b.py").unlink()
        (repo / "pkg" / "circular_a.py").write_text(
            "def a_thing(): return None\n"
        )
        _commit(repo, "drop circular_b")
        run_all_checks(str(repo))

        head = cache.head_hash(str(repo))
        state = cache.get_file_data(str(repo), head, "module_map")
        assert "pkg/circular_b.py" not in state
        # circular_a is still in state but its imports are different now.
        assert "pkg/circular_a.py" in state
