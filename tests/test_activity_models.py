"""Tests for Activity Log data models."""

from core.models import FileChange, DockerChange, PortChange, ActivityEntry


def test_file_change_creation():
    fc = FileChange(
        path="docker-compose.yml",
        status="modified",
        additions=15,
        deletions=2,
        explanation="Docker config — which services run",
    )
    assert fc.path == "docker-compose.yml"
    assert fc.status == "modified"
    assert fc.additions == 15
    assert fc.deletions == 2
    assert fc.explanation == "Docker config — which services run"


def test_file_change_defaults():
    fc = FileChange(path="README.md", status="added")
    assert fc.additions == 0
    assert fc.deletions == 0
    assert fc.explanation == ""


def test_docker_change_creation():
    dc = DockerChange(
        name="redis",
        image="redis:7-alpine",
        status="new",
        ports=["6379"],
        explanation="In-memory cache/queue",
    )
    assert dc.name == "redis"
    assert dc.status == "new"


def test_port_change_creation():
    pc = PortChange(port=6379, process="redis", status="new", explanation="Redis cache")
    assert pc.port == 6379
    assert pc.status == "new"


def test_activity_entry_creation():
    entry = ActivityEntry(
        timestamp="2026-04-15T14:35:00",
        files=[FileChange("a.py", "added")],
        docker_changes=[],
        port_changes=[],
        commits=["abc1234 feat: add worker"],
        project_dir="/home/user/project",
    )
    assert len(entry.files) == 1
    assert entry.project_dir == "/home/user/project"
    assert entry.commits == ["abc1234 feat: add worker"]
