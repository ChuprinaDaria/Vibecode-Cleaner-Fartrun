"""Collect environment changes — git, docker, ports.

Cross-platform: Linux, macOS, Windows.
Git via subprocess (shell=False, UTF-8 forced).
Docker via existing docker SDK. Ports via psutil.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import datetime

from core.file_explainer import explain_file
from core.models import (
    FileChange, DockerChange, PortChange, ActivityEntry,
)

log = logging.getLogger(__name__)


class ActivityTracker:
    """Track changes in a project directory."""

    def __init__(self, project_dir: str):
        self._dir = project_dir
        self._prev_containers: dict[str, dict] = {}
        self._prev_ports: set[int] = set()

    def _find_git(self) -> str | None:
        """Find git binary. Cross-platform via shutil.which."""
        return shutil.which("git")

    def _run_git(self, *args: str) -> str | None:
        """Run a git command in project dir. Returns stdout or None on error."""
        git = self._find_git()
        if not git:
            return None
        try:
            result = subprocess.run(
                [git, *args],
                cwd=self._dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if result.returncode != 0:
                return None
            return result.stdout
        except (subprocess.TimeoutExpired, OSError) as e:
            log.warning("git command failed: %s", e)
            return None

    def is_git_repo(self) -> bool:
        """Check if project_dir is inside a git repository."""
        output = self._run_git("rev-parse", "--is-inside-work-tree")
        return output is not None and output.strip() == "true"

    def get_git_changes(self) -> list[FileChange]:
        """Get file changes: staged + unstaged + untracked.

        Works with repos that have no commits yet (empty repos).
        """
        if not self.is_git_repo():
            return []

        changes: dict[str, FileChange] = {}

        # Check if there are any commits
        has_commits = self._run_git("rev-parse", "HEAD") is not None

        if has_commits:
            # Staged changes (diff against HEAD)
            self._parse_diff_output(
                self._run_git("diff", "--cached", "--name-status"),
                self._run_git("diff", "--cached", "--numstat"),
                changes,
            )

            # Unstaged changes (working tree vs index)
            self._parse_diff_output(
                self._run_git("diff", "--name-status"),
                self._run_git("diff", "--numstat"),
                changes,
            )
        else:
            # No commits yet — treat all staged files as added
            output = self._run_git("diff", "--cached", "--name-only", "--diff-filter=A")
            if output:
                for line in output.strip().splitlines():
                    path = line.strip()
                    if path:
                        changes[path] = FileChange(
                            path=path, status="added",
                            explanation=explain_file(path),
                        )

        # Untracked files
        untracked = self._run_git("ls-files", "--others", "--exclude-standard")
        if untracked:
            for line in untracked.strip().splitlines():
                path = line.strip()
                if path and path not in changes:
                    changes[path] = FileChange(
                        path=path, status="added",
                        explanation=explain_file(path),
                    )

        return list(changes.values())

    def _parse_diff_output(
        self,
        name_status: str | None,
        numstat: str | None,
        changes: dict[str, FileChange],
    ) -> None:
        """Parse git diff --name-status and --numstat output."""
        status_map = {"A": "added", "M": "modified", "D": "deleted"}
        statuses: dict[str, str] = {}

        if name_status:
            for line in name_status.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    code = parts[0][0]  # R100 → R
                    path = parts[-1]    # renamed: take new name
                    status = status_map.get(code, "modified")
                    if code == "R":
                        status = "renamed"
                    statuses[path] = status

        stats: dict[str, tuple[int, int]] = {}
        if numstat:
            for line in numstat.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    try:
                        add = int(parts[0]) if parts[0] != "-" else 0
                        rem = int(parts[1]) if parts[1] != "-" else 0
                        path = parts[2]
                        stats[path] = (add, rem)
                    except ValueError:
                        pass

        for path, status in statuses.items():
            add, rem = stats.get(path, (0, 0))
            if path in changes:
                existing = changes[path]
                existing.additions += add
                existing.deletions += rem
            else:
                changes[path] = FileChange(
                    path=path,
                    status=status,
                    additions=add,
                    deletions=rem,
                    explanation=explain_file(path),
                )

    def get_recent_commits(self, limit: int = 10) -> list[str]:
        """Get recent commit onelines."""
        output = self._run_git("log", "--oneline", f"-{limit}")
        if not output:
            return []
        return [line.strip() for line in output.strip().splitlines() if line.strip()]

    def get_docker_changes(self, current_containers: list[dict]) -> list[DockerChange]:
        """Compare current containers against previous state."""
        current_map = {c["name"]: c for c in current_containers}
        changes: list[DockerChange] = []

        # New containers
        for name, info in current_map.items():
            if name not in self._prev_containers:
                ports = []
                raw_ports = info.get("ports", "")
                if isinstance(raw_ports, str) and raw_ports:
                    ports = [p.strip() for p in raw_ports.split(",") if p.strip()]
                elif isinstance(raw_ports, list):
                    ports = [str(p) for p in raw_ports]
                changes.append(DockerChange(
                    name=name,
                    image=info.get("image", ""),
                    status="new",
                    ports=ports,
                    explanation="New container appeared",
                ))
            else:
                prev = self._prev_containers[name]
                if info.get("status") != prev.get("status"):
                    new_status = info.get("status", "unknown")
                    if new_status == "exited" and info.get("exit_code", 0) != 0:
                        change_status = "crashed"
                        explanation = f"Exited with code {info.get('exit_code', '?')}"
                    elif new_status == "running" and prev.get("status") == "exited":
                        change_status = "restarted"
                        explanation = "Restarted"
                    else:
                        change_status = new_status
                        explanation = f"Status: {prev.get('status')} → {new_status}"
                    changes.append(DockerChange(
                        name=name,
                        image=info.get("image", ""),
                        status=change_status,
                        explanation=explanation,
                    ))

        # Removed containers
        for name, info in self._prev_containers.items():
            if name not in current_map:
                changes.append(DockerChange(
                    name=name,
                    image=info.get("image", ""),
                    status="removed",
                    explanation="Container disappeared",
                ))

        self._prev_containers = dict(current_map)
        return changes

    def get_port_changes(self, current_ports: list[dict]) -> list[PortChange]:
        """Compare current listening ports against previous state."""
        current_set = {p["port"] for p in current_ports}
        current_map = {p["port"]: p for p in current_ports}
        changes: list[PortChange] = []

        # New ports
        for port_num in current_set - self._prev_ports:
            info = current_map[port_num]
            changes.append(PortChange(
                port=port_num,
                process=info.get("process", "unknown"),
                status="new",
                explanation=f"Now listening ({info.get('process', '?')})",
            ))

        # Closed ports
        for port_num in self._prev_ports - current_set:
            changes.append(PortChange(
                port=port_num,
                process="",
                status="closed",
                explanation="Stopped listening",
            ))

        self._prev_ports = set(current_set)
        return changes

    def collect_activity(
        self,
        docker_containers: list[dict] | None = None,
        ports: list[dict] | None = None,
    ) -> ActivityEntry:
        """Collect all changes into a single ActivityEntry."""
        files = self.get_git_changes()
        commits = self.get_recent_commits(limit=5)

        docker_changes = []
        if docker_containers is not None:
            docker_changes = self.get_docker_changes(docker_containers)

        port_changes = []
        if ports is not None:
            port_changes = self.get_port_changes(ports)

        return ActivityEntry(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            files=files,
            docker_changes=docker_changes,
            port_changes=port_changes,
            commits=commits,
            project_dir=self._dir,
        )


def serialize_activity(entry: ActivityEntry) -> str:
    import json
    data = {
        "timestamp": entry.timestamp,
        "project_dir": entry.project_dir,
        "files": [{"path": f.path, "status": f.status, "additions": f.additions,
                    "deletions": f.deletions, "explanation": f.explanation} for f in entry.files],
        "docker_changes": [{"name": d.name, "image": d.image, "status": d.status,
                            "ports": d.ports, "explanation": d.explanation} for d in entry.docker_changes],
        "port_changes": [{"port": p.port, "process": p.process, "status": p.status,
                          "explanation": p.explanation} for p in entry.port_changes],
        "commits": entry.commits,
    }
    return json.dumps(data, ensure_ascii=False)


