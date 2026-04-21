"""Tests for snapshot manager."""

from core.models import EnvironmentSnapshot, SnapshotDiff


def test_snapshot_creation():
    s = EnvironmentSnapshot(
        id=1,
        timestamp="2026-04-15T14:30:00",
        label="Before AI session",
        project_dir="/tmp/test",
        git_branch="main",
        git_last_commit="abc1234 feat: init",
        git_tracked_count=42,
        git_dirty_files=["app.py"],
        containers=[{"name": "web", "image": "py", "status": "running"}],
        listening_ports=[{"port": 8000, "process": "python"}],
        config_checksums={".env": "abc123"},
    )
    assert s.label == "Before AI session"
    assert len(s.containers) == 1


def test_snapshot_diff_total():
    diff = SnapshotDiff(
        branch_changed=True,
        old_branch="main",
        new_branch="feature",
        containers_added=["redis"],
        ports_opened=[6379, 5555],
        configs_changed=[".env"],
    )
    assert diff.total_changes == 5


from core.history import HistoryDB
from core.snapshot_manager import (
    create_snapshot, load_snapshots, delete_snapshot,
    compare_snapshots, prune_old, _collect_config_checksums,
)


def test_create_and_load(tmp_path):
    db = HistoryDB(":memory:")
    db.init()

    s = create_snapshot(
        project_dir=str(tmp_path),
        label="test snapshot",
        db=db,
        docker_data=[{"name": "web", "status": "running"}],
        port_data=[{"port": 8000, "process": "python"}],
    )
    assert s.id > 0
    assert s.label == "test snapshot"

    loaded = load_snapshots(db, str(tmp_path))
    assert len(loaded) == 1
    assert loaded[0].id == s.id
    assert loaded[0].containers == [{"name": "web", "status": "running"}]
    db.close()


def test_delete_snapshot():
    db = HistoryDB(":memory:")
    db.init()

    s = create_snapshot("/tmp/test", "to delete", db)
    assert len(load_snapshots(db, "/tmp/test")) == 1

    delete_snapshot(db, s.id)
    assert len(load_snapshots(db, "/tmp/test")) == 0
    db.close()


def test_prune_old():
    db = HistoryDB(":memory:")
    db.init()

    for i in range(10):
        create_snapshot("/tmp/test", f"snap {i}", db)

    prune_old(db, "/tmp/test", max_count=3)
    remaining = load_snapshots(db, "/tmp/test")
    assert len(remaining) == 3
    assert remaining[0].label == "snap 9"
    db.close()


def test_compare_snapshots_full():
    old = EnvironmentSnapshot(
        git_branch="main",
        git_dirty_files=["app.py"],
        containers=[{"name": "web", "status": "running"}],
        listening_ports=[{"port": 8000}],
        config_checksums={".env": "aaa", "Makefile": "bbb"},
    )
    new = EnvironmentSnapshot(
        git_branch="feature",
        git_dirty_files=["app.py", "utils.py"],
        containers=[
            {"name": "web", "status": "running"},
            {"name": "redis", "status": "running"},
        ],
        listening_ports=[{"port": 8000}, {"port": 6379}],
        config_checksums={".env": "ccc", "docker-compose.yml": "ddd"},
    )
    diff = compare_snapshots(old, new)
    assert diff.branch_changed is True
    assert diff.dirty_added == ["utils.py"]
    assert diff.containers_added == ["redis"]
    assert diff.ports_opened == [6379]
    assert diff.configs_changed == [".env"]
    assert diff.configs_added == ["docker-compose.yml"]
    assert diff.configs_removed == ["Makefile"]
    assert diff.total_changes == 7


def test_config_checksums(tmp_path):
    (tmp_path / ".env").write_text("KEY=val\n")
    (tmp_path / "requirements.txt").write_text("flask\n")
    checksums = _collect_config_checksums(str(tmp_path))
    assert ".env" in checksums
    assert "requirements.txt" in checksums
    assert len(checksums[".env"]) == 64


def test_no_changes_compare():
    snap = EnvironmentSnapshot(
        git_branch="main",
        git_dirty_files=[],
        containers=[],
        listening_ports=[],
        config_checksums={},
    )
    diff = compare_snapshots(snap, snap)
    assert diff.total_changes == 0
