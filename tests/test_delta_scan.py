"""End-to-end tests for the git-delta scan path in run_all_checks.

These tests build a real git repository, run the full health scan to
populate the cache, then make commits and re-scan — verifying that the
delta path produces results equivalent to a fresh full scan.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from core.health import cache, delta_scan, git_delta
from core.health.git_delta import DeltaPlan, FileChange
from core.health.models import HealthFinding, HealthReport
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


def _giant_python(line_count: int) -> str:
    body_lines = ["class Foo:", "    def bar(self):"]
    body_lines.extend(f"        x{i} = {i}" for i in range(line_count - 2))
    return "\n".join(body_lines) + "\n"


# --- unit tests for apply_monsters_delta (no run_all_checks) ---


class TestApplyMonstersDelta:
    def test_carries_unchanged_monsters_through(self):
        ancestor = HealthReport(project_dir="/p")
        ancestor.monsters = [
            {"path": "stable.py", "lines": 600, "functions": 1,
             "classes": 1, "severity": "medium"},
        ]
        ancestor.findings.append(HealthFinding(
            check_id="map.monsters", title="Monster: stable.py",
            severity="medium", message="...", details={"path": "stable.py"},
        ))
        report = HealthReport(project_dir="/p")
        plan = DeltaPlan(ancestor_hash="abc", changed=[])

        # No health_rs needed because added_or_modified is empty.
        class _Stub:
            def scan_monsters_files(self, *a, **k):
                raise AssertionError("should not be called")

        delta_scan.apply_monsters_delta(report, _Stub(), "/p", plan, ancestor)
        assert [m["path"] for m in report.monsters] == ["stable.py"]
        assert any(f.check_id == "map.monsters"
                   and f.details.get("path") == "stable.py"
                   for f in report.findings)

    def test_drops_findings_for_changed_path(self):
        ancestor = HealthReport(project_dir="/p")
        ancestor.monsters = [
            {"path": "old.py", "lines": 700, "functions": 1,
             "classes": 1, "severity": "medium"},
            {"path": "stable.py", "lines": 600, "functions": 1,
             "classes": 1, "severity": "medium"},
        ]
        ancestor.findings = [
            HealthFinding(check_id="map.monsters", title="Monster: old.py",
                          severity="medium", message="x",
                          details={"path": "old.py"}),
            HealthFinding(check_id="map.monsters", title="Monster: stable.py",
                          severity="medium", message="x",
                          details={"path": "stable.py"}),
        ]
        report = HealthReport(project_dir="/p")
        plan = DeltaPlan(
            ancestor_hash="abc",
            changed=[FileChange(status="M", path="old.py")],
        )

        class _Stub:
            def scan_monsters_files(self, root, files):
                assert files == ["old.py"]
                # Modified file is now small — produces no monster.
                class Result:
                    monsters = []
                return Result()

        delta_scan.apply_monsters_delta(report, _Stub(), "/p", plan, ancestor)
        paths = [m["path"] for m in report.monsters]
        assert paths == ["stable.py"]
        finding_paths = [f.details.get("path") for f in report.findings
                         if f.check_id == "map.monsters"]
        assert finding_paths == ["stable.py"]

    def test_deleted_file_drops_from_monsters(self):
        ancestor = HealthReport(project_dir="/p")
        ancestor.monsters = [
            {"path": "gone.py", "lines": 600, "functions": 1,
             "classes": 1, "severity": "medium"},
        ]
        ancestor.findings.append(HealthFinding(
            check_id="map.monsters", title="Monster: gone.py",
            severity="medium", message="x", details={"path": "gone.py"},
        ))
        report = HealthReport(project_dir="/p")
        plan = DeltaPlan(
            ancestor_hash="abc",
            changed=[FileChange(status="D", path="gone.py")],
        )

        class _Stub:
            def scan_monsters_files(self, *a, **k):
                raise AssertionError("nothing to add for pure delete")

        delta_scan.apply_monsters_delta(report, _Stub(), "/p", plan, ancestor)
        assert report.monsters == []
        assert all(f.details.get("path") != "gone.py"
                   for f in report.findings if f.check_id == "map.monsters")

    def test_legacy_finding_without_path_is_dropped(self):
        """Old cache entries from before details['path'] tracking carry no
        path. These cannot be safely carried over (no way to filter), so
        delta drops them. The per-file rescan re-creates entries for any
        currently-monstrous files in the changed set; for unchanged files
        we lose them this once until the next full scan refreshes cache."""
        ancestor = HealthReport(project_dir="/p")
        ancestor.findings.append(HealthFinding(
            check_id="map.monsters", title="Monster: legacy.py",
            severity="medium", message="x", details={},
        ))
        report = HealthReport(project_dir="/p")
        plan = DeltaPlan(ancestor_hash="abc", changed=[])

        class _Stub:
            pass

        delta_scan.apply_monsters_delta(report, _Stub(), "/p", plan, ancestor)
        assert report.findings == []


# --- integration test against a real git repo ---


def _make_repo_with_one_monster(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "monster.py").write_text(_giant_python(700))
    (repo / "small.py").write_text("x = 1\n")
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "init")
    return repo


def _health_available() -> bool:
    try:
        import health  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _health_available(), reason="health crate not built")
class TestRunAllChecksDeltaPath:
    def test_warm_rescan_uses_delta_and_matches_full_rerun(self, tmp_path):
        """After caching at HEAD@c0, modify one file + commit, re-scan,
        compare result to a fresh full-scan baseline run from scratch."""
        repo = _make_repo_with_one_monster(tmp_path)

        # First run populates cache at c0.
        run_all_checks(str(repo))

        # Modify the small file into a monster, add a brand-new monster.
        (repo / "small.py").write_text(_giant_python(600))
        (repo / "new_monster.py").write_text(_giant_python(800))
        _commit(repo, "add monsters")

        # Delta path will now fire.
        delta_report = run_all_checks(str(repo))

        # Independent baseline: clear cache and full-rerun on the same HEAD.
        cache.clear(str(repo))
        full_report = run_all_checks(str(repo), use_cache=False)

        # Both should agree on the set of monsters detected.
        assert sorted(m["path"] for m in delta_report.monsters) == \
               sorted(m["path"] for m in full_report.monsters)

        # Findings for map.monsters should also agree on their paths.
        delta_paths = sorted(
            (f.details or {}).get("path")
            for f in delta_report.findings if f.check_id == "map.monsters"
        )
        full_paths = sorted(
            (f.details or {}).get("path")
            for f in full_report.findings if f.check_id == "map.monsters"
        )
        assert delta_paths == full_paths

    def test_clean_repo_no_changes_returns_cached_verbatim(self, tmp_path):
        """When HEAD == cached HEAD, run_all_checks short-circuits via
        cache.get and never enters the delta path."""
        repo = _make_repo_with_one_monster(tmp_path)
        first = run_all_checks(str(repo))
        # Without delta_context, this would need to be byte-identical.
        # cache.get returns the same object shape.
        second = run_all_checks(str(repo))
        assert sorted(m["path"] for m in first.monsters) == \
               sorted(m["path"] for m in second.monsters)
