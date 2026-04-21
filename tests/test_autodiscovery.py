"""Tests for autodiscovery module."""

import psutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from core.autodiscovery import discover_system, SystemState, ProjectInfo


def test_discover_claude_dir_exists(tmp_path):
    claude_dir = tmp_path / ".claude" / "projects" / "test"
    claude_dir.mkdir(parents=True)
    (claude_dir / "session.jsonl").touch()
    with patch("core.autodiscovery.Path.home", return_value=tmp_path):
        state = discover_system()
    assert state.claude_dir == tmp_path / ".claude"


def test_discover_claude_dir_missing(tmp_path):
    with patch("core.autodiscovery.Path.home", return_value=tmp_path):
        state = discover_system()
    assert state.claude_dir is None


def test_discover_claude_dir_from_config(tmp_path):
    claude_dir = tmp_path / "custom-claude"
    claude_dir.mkdir()
    (claude_dir / "projects").mkdir()
    state = discover_system(config_paths={"claude_dir": str(claude_dir)})
    assert state.claude_dir == claude_dir


def test_discover_docker_available():
    with patch("core.autodiscovery.docker") as mock_docker:
        mock_docker.from_env.return_value = MagicMock()
        state = discover_system()
    assert state.docker_available is True
    assert state.docker_error is None


def test_discover_docker_permission_denied():
    with patch("core.autodiscovery.docker") as mock_docker:
        mock_docker.from_env.side_effect = PermissionError("access denied")
        mock_docker.errors = MagicMock()
        mock_docker.errors.DockerException = Exception
        state = discover_system()
    assert state.docker_available is False
    assert "permission" in state.docker_error.lower()


def test_discover_docker_not_installed():
    with patch("core.autodiscovery.docker", None):
        state = discover_system()
    assert state.docker_available is False
    assert state.docker_error is not None


def test_discover_projects(tmp_path):
    proj1 = tmp_path / "myapp"
    proj1.mkdir()
    (proj1 / ".git").mkdir()
    (proj1 / "docker-compose.yml").touch()

    proj2 = tmp_path / "other"
    proj2.mkdir()
    (proj2 / ".git").mkdir()
    (proj2 / "package.json").touch()

    with patch("core.autodiscovery.Path.home", return_value=tmp_path):
        state = discover_system()

    names = [p.name for p in state.projects]
    assert "myapp" in names
    assert "other" in names

    myapp = [p for p in state.projects if p.name == "myapp"][0]
    assert myapp.has_docker_compose is True

    other = [p for p in state.projects if p.name == "other"][0]
    assert other.has_package_json is True


def test_discover_psutil_limited():
    with patch("core.autodiscovery.psutil") as mock_ps:
        mock_ps.AccessDenied = psutil.AccessDenied
        mock_ps.net_connections.side_effect = psutil.AccessDenied(pid=0)
        state = discover_system()
    assert state.psutil_limited is True
