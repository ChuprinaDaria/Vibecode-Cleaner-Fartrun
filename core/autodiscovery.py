"""Auto-detect Claude, Docker, projects on the system."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import psutil

try:
    import docker
except ImportError:
    docker = None

log = logging.getLogger(__name__)


@dataclass
class ProjectInfo:
    path: Path
    name: str
    has_docker_compose: bool = False
    has_package_json: bool = False


@dataclass
class SystemState:
    claude_dir: Path | None = None
    docker_available: bool = False
    docker_error: str | None = None
    docker_client: object | None = None
    projects: list[ProjectInfo] = field(default_factory=list)
    psutil_limited: bool = False


def _find_claude_dir(config_override: str | None = None) -> Path | None:
    if config_override:
        p = Path(config_override).expanduser()
        if p.exists():
            return p
        return None
    claude_dir = Path.home() / ".claude"
    projects_dir = claude_dir / "projects"
    if projects_dir.exists():
        for _ in projects_dir.rglob("*.jsonl"):
            return claude_dir
    return None


def _find_docker(config_socket: str | None = None) -> tuple[bool, str | None, object | None]:
    if docker is None:
        return False, "Docker SDK not installed. Install: pip install docker", None
    try:
        kwargs = {}
        if config_socket:
            kwargs["base_url"] = config_socket
        elif sys.platform == "win32":
            kwargs["base_url"] = "npipe:////./pipe/docker_engine"
        client = docker.from_env(**kwargs)
        client.ping()
        return True, None, client
    except PermissionError:
        if sys.platform == "win32":
            return False, "Permission denied. Run as Administrator or add user to docker-users group", None
        return False, "Permission denied. Fix: sudo usermod -aG docker $USER && newgrp docker", None
    except Exception as e:
        err = str(e)
        if "FileNotFoundError" in err or "No such file" in err:
            return False, "Docker socket not found. Is Docker running?", None
        if "Connection refused" in err:
            return False, "Docker daemon not responding. Start Docker Desktop or docker service", None
        return False, f"Docker error: {err}", None


def _find_projects(scan_paths: list[str] | None = None, depth: int = 2) -> list[ProjectInfo]:
    roots = [Path(p).expanduser() for p in scan_paths] if scan_paths else [Path.home()]
    projects = []
    for root in roots:
        if not root.is_dir():
            continue
        _scan_dir(root, projects, depth)
    projects.sort(key=lambda p: p.name.lower())
    return projects


def _scan_dir(base: Path, results: list[ProjectInfo], depth: int) -> None:
    if depth <= 0:
        return
    try:
        for entry in base.iterdir():
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if (entry / ".git").is_dir():
                results.append(ProjectInfo(
                    path=entry,
                    name=entry.name,
                    has_docker_compose=(entry / "docker-compose.yml").exists() or (entry / "docker-compose.yaml").exists(),
                    has_package_json=(entry / "package.json").exists(),
                ))
            else:
                _scan_dir(entry, results, depth - 1)
    except PermissionError:
        pass


def _check_psutil_access() -> bool:
    try:
        psutil.net_connections(kind="inet")
        return False
    except psutil.AccessDenied:
        return True


def discover_system(config_paths: dict | None = None) -> SystemState:
    config_paths = config_paths or {}
    state = SystemState()
    state.claude_dir = _find_claude_dir(config_paths.get("claude_dir"))
    state.docker_available, state.docker_error, state.docker_client = _find_docker(
        config_paths.get("docker_socket")
    )
    state.projects = _find_projects(config_paths.get("scan_paths"))
    state.psutil_limited = _check_psutil_access()
    return state
