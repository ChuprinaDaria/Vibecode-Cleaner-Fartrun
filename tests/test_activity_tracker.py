"""Tests for activity_tracker — git/docker/port change detection."""

import subprocess
from unittest.mock import patch

from core.activity_tracker import ActivityTracker


def test_find_git_binary():
    """Git binary found via shutil.which."""
    tracker = ActivityTracker("/tmp/fake")
    with patch("shutil.which", return_value="/usr/bin/git"):
        assert tracker._find_git() == "/usr/bin/git"


def test_find_git_binary_missing():
    """Returns None when git not installed."""
    tracker = ActivityTracker("/tmp/fake")
    with patch("shutil.which", return_value=None):
        assert tracker._find_git() is None


def test_is_git_repo_true(tmp_path):
    """Detects a git repo correctly."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    tracker = ActivityTracker(str(tmp_path))
    assert tracker.is_git_repo() is True


def test_is_git_repo_false(tmp_path):
    """Non-git directory returns False."""
    tracker = ActivityTracker(str(tmp_path))
    assert tracker.is_git_repo() is False


def test_git_file_changes(tmp_path):
    """Detects added/modified/deleted files."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path), capture_output=True,
    )

    # Create and commit a file
    (tmp_path / "hello.py").write_text("print('hello')")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(tmp_path), capture_output=True,
    )

    # Modify file + add new one
    (tmp_path / "hello.py").write_text("print('hello world')")
    (tmp_path / "docker-compose.yml").write_text("version: '3'")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)

    tracker = ActivityTracker(str(tmp_path))
    changes = tracker.get_git_changes()

    paths = [c.path for c in changes]
    assert "docker-compose.yml" in paths
    assert "hello.py" in paths

    # docker-compose.yml should have an explanation
    dc = next(c for c in changes if c.path == "docker-compose.yml")
    assert "Docker" in dc.explanation


def test_git_recent_commits(tmp_path):
    """Gets recent commit messages."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path), capture_output=True,
    )
    (tmp_path / "a.py").write_text("x = 1")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: add a"],
        cwd=str(tmp_path), capture_output=True,
    )

    tracker = ActivityTracker(str(tmp_path))
    commits = tracker.get_recent_commits(limit=5)
    assert len(commits) == 1
    assert "feat: add a" in commits[0]


def test_git_changes_no_git(tmp_path):
    """Gracefully returns empty when not a git repo."""
    tracker = ActivityTracker(str(tmp_path))
    changes = tracker.get_git_changes()
    assert changes == []


def test_git_changes_no_commits(tmp_path):
    """Gracefully handles repo with no commits yet."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    (tmp_path / "new.py").write_text("x = 1")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)

    tracker = ActivityTracker(str(tmp_path))
    changes = tracker.get_git_changes()
    assert any(c.path == "new.py" for c in changes)


# --- Docker change detection ---

def test_docker_changes_new_container():
    tracker = ActivityTracker("/tmp/fake")
    containers = [
        {"name": "web", "image": "python:3.11", "status": "running", "ports": "8000"},
    ]
    changes = tracker.get_docker_changes(containers)
    assert len(changes) == 1
    assert changes[0].name == "web"
    assert changes[0].status == "new"


def test_docker_changes_removed_container():
    tracker = ActivityTracker("/tmp/fake")
    tracker.get_docker_changes([
        {"name": "web", "image": "python:3.11", "status": "running", "ports": "8000"},
    ])
    changes = tracker.get_docker_changes([])
    assert len(changes) == 1
    assert changes[0].name == "web"
    assert changes[0].status == "removed"


def test_docker_changes_crashed():
    tracker = ActivityTracker("/tmp/fake")
    tracker.get_docker_changes([
        {"name": "db", "image": "postgres:16", "status": "running", "ports": "5432"},
    ])
    changes = tracker.get_docker_changes([
        {"name": "db", "image": "postgres:16", "status": "exited", "exit_code": 1, "ports": ""},
    ])
    assert len(changes) == 1
    assert changes[0].status == "crashed"


def test_docker_no_changes():
    tracker = ActivityTracker("/tmp/fake")
    containers = [
        {"name": "web", "image": "python:3.11", "status": "running", "ports": "8000"},
    ]
    tracker.get_docker_changes(containers)
    changes = tracker.get_docker_changes(containers)
    assert len(changes) == 0


def test_port_changes_new():
    tracker = ActivityTracker("/tmp/fake")
    ports = [{"port": 8000, "process": "python", "proto": "tcp"}]
    changes = tracker.get_port_changes(ports)
    assert len(changes) == 1
    assert changes[0].port == 8000
    assert changes[0].status == "new"


def test_port_changes_closed():
    tracker = ActivityTracker("/tmp/fake")
    tracker.get_port_changes([{"port": 8000, "process": "python", "proto": "tcp"}])
    changes = tracker.get_port_changes([])
    assert len(changes) == 1
    assert changes[0].port == 8000
    assert changes[0].status == "closed"


def test_port_no_changes():
    tracker = ActivityTracker("/tmp/fake")
    ports = [{"port": 8000, "process": "python", "proto": "tcp"}]
    tracker.get_port_changes(ports)
    changes = tracker.get_port_changes(ports)
    assert len(changes) == 0


def test_collect_activity(tmp_path):
    """Integration: collect_activity returns an ActivityEntry."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path), capture_output=True,
    )
    (tmp_path / "app.py").write_text("x = 1")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)

    tracker = ActivityTracker(str(tmp_path))
    entry = tracker.collect_activity(
        docker_containers=[{"name": "web", "image": "py", "status": "running", "ports": ""}],
        ports=[{"port": 8000, "process": "python", "proto": "tcp"}],
    )
    assert entry.project_dir == str(tmp_path)
    assert len(entry.files) >= 1
    assert len(entry.docker_changes) == 1
    assert len(entry.port_changes) == 1
    assert entry.timestamp
