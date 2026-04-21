"""Tests for core/safety_net.py — Save / Rollback / Pick."""

import subprocess
from pathlib import Path

import pytest

from core.history import HistoryDB
from core.safety_net import SafetyNet, SavePointResult, RollbackResult, PickResult


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repo with initial commit."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
    # Initial commit
    (tmp_path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True, check=True)
    return tmp_path


@pytest.fixture
def db():
    hdb = HistoryDB(":memory:")
    hdb.init()
    return hdb


@pytest.fixture
def sn(git_repo, db):
    return SafetyNet(str(git_repo), db)


def _add_file(repo: Path, name: str, content: str = "hello\n"):
    (repo / name).write_text(content)


class TestCreateSavePoint:
    def test_creates_tag_and_commit(self, sn, git_repo, db):
        _add_file(git_repo, "app.py", "print('hello')\n")
        result = sn.create_save_point("before auth")
        assert isinstance(result, SavePointResult)
        assert result.tag_name.startswith("savepoint-")
        assert result.file_count >= 2  # README + app.py
        assert result.lines_total > 0

        # Check DB
        points = db.get_save_points(str(git_repo))
        assert len(points) == 1
        assert points[0]["label"] == "before auth"

        # Check git tag exists
        r = subprocess.run(
            ["git", "tag"], cwd=git_repo, capture_output=True, text=True,
        )
        assert result.tag_name in r.stdout

    def test_save_no_changes(self, sn, git_repo):
        ok, reason = sn.can_save()
        assert not ok
        assert reason == "no_changes"

    def test_save_gitignore_warning(self, sn, git_repo):
        (git_repo / ".env").write_text("SECRET=123\n")
        subprocess.run(["git", "add", ".env"], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add env"],
            cwd=git_repo, capture_output=True,
        )
        # Create new changes so can_save is true
        (git_repo / ".env").write_text("SECRET=456\n")
        warnings = sn.pre_save_warnings()
        assert any(w["type"] == "env_tracked" for w in warnings)

    def test_node_modules_warning(self, sn, git_repo):
        (git_repo / "node_modules").mkdir()
        (git_repo / "node_modules" / "foo.js").write_text("module.exports = {}")
        warnings = sn.pre_save_warnings()
        assert any(w["type"] == "node_modules" for w in warnings)


class TestRollback:
    def test_rollback_restores_files(self, sn, git_repo, db):
        # Save point
        _add_file(git_repo, "app.py", "v1\n")
        sn.create_save_point("baseline")

        # Make changes
        _add_file(git_repo, "app.py", "v2 broken\n")
        _add_file(git_repo, "broken.py", "oops\n")

        sp = db.get_save_points(str(git_repo))[0]
        result = sn.rollback(sp["id"])

        assert isinstance(result, RollbackResult)
        assert result.backup_branch.startswith("backup/")

        # File should be restored
        assert (git_repo / "app.py").read_text() == "v1\n"
        # broken.py should not exist
        assert not (git_repo / "broken.py").exists()

        # Backup branch should exist
        r = subprocess.run(
            ["git", "branch"], cwd=git_repo, capture_output=True, text=True,
        )
        assert result.backup_branch in r.stdout

    def test_rollback_no_changes(self, sn, git_repo, db):
        _add_file(git_repo, "app.py", "v1\n")
        sn.create_save_point("baseline")
        sp = db.get_save_points(str(git_repo))[0]
        ok, reason = sn.can_rollback(sp["id"])
        assert not ok
        assert reason == "already_at_save_point"


class TestSmartRollback:
    def test_get_changes_since(self, sn, git_repo, db):
        _add_file(git_repo, "app.py", "v1\n")
        sn.create_save_point("baseline")

        _add_file(git_repo, "app.py", "v2\n")
        _add_file(git_repo, "new.py", "hello\n")

        sp = db.get_save_points(str(git_repo))[0]
        changes = sn.get_changes_since(sp["id"])
        paths = {c.path for c in changes}
        assert "app.py" in paths
        assert "new.py" in paths
        # new.py is 'added'
        new_entry = next(c for c in changes if c.path == "new.py")
        assert new_entry.status == "added"

    def test_get_changes_skips_junk_dirs(self, sn, git_repo, db):
        _add_file(git_repo, "app.py", "v1\n")
        sn.create_save_point("baseline")
        (git_repo / "node_modules").mkdir()
        (git_repo / "node_modules" / "trash.js").write_text("never\n")
        _add_file(git_repo, "real.py", "code\n")

        sp = db.get_save_points(str(git_repo))[0]
        changes = sn.get_changes_since(sp["id"])
        paths = {c.path for c in changes}
        assert "real.py" in paths
        assert "node_modules/trash.js" not in paths

    def test_rollback_with_picks_keeps_selected(self, sn, git_repo, db):
        _add_file(git_repo, "app.py", "v1\n")
        sn.create_save_point("baseline")

        _add_file(git_repo, "good.py", "works\n")
        _add_file(git_repo, "bad.py", "broken\n")

        sp = db.get_save_points(str(git_repo))[0]
        result = sn.rollback_with_picks(sp["id"], keep_paths=["good.py"])

        assert isinstance(result, RollbackResult)
        assert (git_repo / "good.py").read_text() == "works\n"
        assert not (git_repo / "bad.py").exists()

    def test_rollback_with_picks_empty_behaves_like_rollback(self, sn, git_repo, db):
        _add_file(git_repo, "app.py", "v1\n")
        sn.create_save_point("baseline")

        _add_file(git_repo, "trash.py", "oops\n")

        sp = db.get_save_points(str(git_repo))[0]
        result = sn.rollback_with_picks(sp["id"], keep_paths=[])
        assert isinstance(result, RollbackResult)
        assert not (git_repo / "trash.py").exists()


class TestPickFiles:
    def test_pick_selective(self, sn, git_repo, db):
        # Save point
        _add_file(git_repo, "app.py", "v1\n")
        sn.create_save_point("baseline")

        # Make 3 file changes
        _add_file(git_repo, "app.py", "v2\n")
        _add_file(git_repo, "good.py", "good code\n")
        _add_file(git_repo, "bad.py", "bad code\n")

        sp = db.get_save_points(str(git_repo))[0]
        sn.rollback(sp["id"])

        # Now pick only good.py
        backups = db.get_rollback_backups(str(git_repo))
        assert len(backups) == 1

        files = sn.list_pickable_files(backups[0]["id"])
        paths = [f.path for f in files]
        assert "good.py" in paths
        assert "bad.py" in paths

        result = sn.pick_files(backups[0]["id"], ["good.py"])
        assert isinstance(result, PickResult)
        assert "good.py" in result.files_applied
        assert (git_repo / "good.py").read_text() == "good code\n"
        # bad.py should NOT be here
        assert not (git_repo / "bad.py").exists()

    def test_pick_empty_backup(self, sn, git_repo, db):
        _add_file(git_repo, "app.py", "v1\n")
        sn.create_save_point("baseline")
        # No changes, rollback immediately — backup diff should be empty
        sp = db.get_save_points(str(git_repo))[0]
        # Can't rollback (no changes)
        ok, _ = sn.can_rollback(sp["id"])
        assert not ok


class TestEnsureGit:
    def test_non_git_dir(self, tmp_path, db):
        sn = SafetyNet(str(tmp_path), db)
        assert not sn._is_repo()
        result = sn.ensure_git()
        assert result
        assert sn._is_repo()

    def test_fix_gitignore(self, git_repo, db):
        sn = SafetyNet(str(git_repo), db)
        sn.fix_gitignore([".env", "node_modules/"])
        gitignore = (git_repo / ".gitignore").read_text()
        assert ".env" in gitignore
        assert "node_modules/" in gitignore


class TestMaxSavePoints:
    def test_cleanup_oldest(self, sn, git_repo, db):
        config = {"safety_net": {"max_save_points": 3}}
        sn_limited = SafetyNet(str(git_repo), db, config)

        for i in range(5):
            _add_file(git_repo, f"file{i}.py", f"content {i}\n")
            sn_limited.create_save_point(f"sp-{i}")

        points = db.get_save_points(str(git_repo))
        assert len(points) <= 3

        # Oldest tags should be cleaned up
        r = subprocess.run(
            ["git", "tag", "-l", "savepoint-*"],
            cwd=git_repo, capture_output=True, text=True,
        )
        tags = [t.strip() for t in r.stdout.splitlines() if t.strip()]
        assert len(tags) <= 3
