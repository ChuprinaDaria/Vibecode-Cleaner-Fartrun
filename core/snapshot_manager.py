"""Create, load, compare, and prune environment snapshots."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from core.history import HistoryDB
from core.models import EnvironmentSnapshot, SnapshotDiff

log = logging.getLogger(__name__)

CONFIG_PATTERNS = [
    "docker-compose*.yml", "docker-compose*.yaml",
    ".env", ".env.*",
    "Dockerfile*",
    "requirements*.txt",
    "package.json", "pyproject.toml",
    "Makefile", "tsconfig*.json",
]


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    try:
        h.update(path.read_bytes())
    except OSError:
        return ""
    return h.hexdigest()


def _collect_config_checksums(project_dir: str) -> dict[str, str]:
    root = Path(project_dir)
    checksums: dict[str, str] = {}
    seen: set[str] = set()
    for pattern in CONFIG_PATTERNS:
        for match_path in root.glob(pattern):
            rel = str(match_path.relative_to(root))
            if rel not in seen:
                seen.add(rel)
                digest = _file_sha256(match_path)
                if digest:
                    checksums[rel] = digest
    return checksums


def _collect_git_state(project_dir: str) -> tuple[str, str, int, list[str]]:
    git = shutil.which("git")
    if not git:
        return "", "", 0, []

    def run_git(*args: str) -> str | None:
        try:
            result = subprocess.run(
                [git, *args],
                cwd=project_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, OSError):
            return None

    branch = run_git("rev-parse", "--abbrev-ref", "HEAD") or ""
    last_commit = run_git("log", "--oneline", "-1") or ""

    tracked_output = run_git("ls-files")
    tracked_count = len(tracked_output.splitlines()) if tracked_output else 0

    dirty_output = run_git("status", "--porcelain")
    dirty_files = []
    if dirty_output:
        for line in dirty_output.splitlines():
            if line.strip():
                dirty_files.append(line[3:].strip())

    return branch, last_commit, tracked_count, dirty_files


def create_snapshot(
    project_dir: str,
    label: str,
    db: HistoryDB,
    docker_data: list[dict] | None = None,
    port_data: list[dict] | None = None,
    haiku_label: str = "",
) -> EnvironmentSnapshot:
    branch, last_commit, tracked_count, dirty_files = _collect_git_state(project_dir)
    checksums = _collect_config_checksums(project_dir)

    snapshot = EnvironmentSnapshot(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        label=label,
        project_dir=project_dir,
        git_branch=branch,
        git_last_commit=last_commit,
        git_tracked_count=tracked_count,
        git_dirty_files=dirty_files,
        containers=docker_data or [],
        listening_ports=port_data or [],
        config_checksums=checksums,
        haiku_label=haiku_label,
    )

    cursor = db.execute(
        """
        INSERT INTO snapshots
        (timestamp, label, project_dir, git_branch, git_last_commit,
         git_tracked_count, git_dirty_files, containers, listening_ports, config_checksums,
         haiku_label)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot.timestamp,
            snapshot.label,
            snapshot.project_dir,
            snapshot.git_branch,
            snapshot.git_last_commit,
            snapshot.git_tracked_count,
            json.dumps(snapshot.git_dirty_files),
            json.dumps(snapshot.containers),
            json.dumps(snapshot.listening_ports),
            json.dumps(snapshot.config_checksums),
            snapshot.haiku_label,
        ),
    )
    db.commit()
    snapshot.id = cursor.lastrowid

    prune_old(db, project_dir)
    return snapshot


def load_snapshots(db: HistoryDB, project_dir: str, limit: int = 50) -> list[EnvironmentSnapshot]:
    cursor = db.execute(
        """
        SELECT id, timestamp, label, project_dir, git_branch, git_last_commit,
               git_tracked_count, git_dirty_files, containers, listening_ports, config_checksums,
               COALESCE(haiku_label, '') as haiku_label
        FROM snapshots
        WHERE project_dir = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (project_dir, limit),
    )
    return [
        EnvironmentSnapshot(
            id=row[0], timestamp=row[1], label=row[2], project_dir=row[3],
            git_branch=row[4], git_last_commit=row[5], git_tracked_count=row[6],
            git_dirty_files=json.loads(row[7]), containers=json.loads(row[8]),
            listening_ports=json.loads(row[9]), config_checksums=json.loads(row[10]),
            haiku_label=row[11],
        )
        for row in cursor.fetchall()
    ]


def delete_snapshot(db: HistoryDB, snapshot_id: int) -> None:
    db.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))
    db.commit()


def prune_old(db: HistoryDB, project_dir: str, max_count: int = 50) -> None:
    db.execute(
        """
        DELETE FROM snapshots
        WHERE project_dir = ? AND id NOT IN (
            SELECT id FROM snapshots
            WHERE project_dir = ?
            ORDER BY id DESC
            LIMIT ?
        )
        """,
        (project_dir, project_dir, max_count),
    )
    db.commit()


def compare_snapshots(old: EnvironmentSnapshot, new: EnvironmentSnapshot) -> SnapshotDiff:
    diff = SnapshotDiff()

    if old.git_branch != new.git_branch:
        diff.branch_changed = True
        diff.old_branch = old.git_branch
        diff.new_branch = new.git_branch

    old_dirty = set(old.git_dirty_files)
    new_dirty = set(new.git_dirty_files)
    diff.dirty_added = sorted(new_dirty - old_dirty)
    diff.dirty_removed = sorted(old_dirty - new_dirty)

    old_containers = {c.get("name", ""): c for c in old.containers}
    new_containers = {c.get("name", ""): c for c in new.containers}
    diff.containers_added = sorted(set(new_containers) - set(old_containers))
    diff.containers_removed = sorted(set(old_containers) - set(new_containers))
    for name in set(old_containers) & set(new_containers):
        old_status = old_containers[name].get("status", "")
        new_status = new_containers[name].get("status", "")
        if old_status != new_status:
            diff.containers_status_changed.append((name, old_status, new_status))

    old_ports = {p.get("port", 0) for p in old.listening_ports}
    new_ports = {p.get("port", 0) for p in new.listening_ports}
    diff.ports_opened = sorted(new_ports - old_ports)
    diff.ports_closed = sorted(old_ports - new_ports)

    old_cfgs = old.config_checksums
    new_cfgs = new.config_checksums
    diff.configs_added = sorted(set(new_cfgs) - set(old_cfgs))
    diff.configs_removed = sorted(set(old_cfgs) - set(new_cfgs))
    diff.configs_changed = sorted(
        k for k in set(old_cfgs) & set(new_cfgs) if old_cfgs[k] != new_cfgs[k]
    )

    return diff
