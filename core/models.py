from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ModelUsage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input + self.output + self.cache_read + self.cache_write

    @property
    def billable_tokens(self) -> int:
        return self.input + self.output + self.cache_write


@dataclass
class SessionStats:
    session_id: str
    project: str
    model_stats: dict[str, ModelUsage] = field(default_factory=dict)
    start_time: datetime | None = None


@dataclass
class TokenStats:
    date: str
    sessions: list[SessionStats] = field(default_factory=list)
    total_input: int = 0
    total_output: int = 0
    total_cache_read: int = 0
    total_cache_write: int = 0
    total_billable: int = 0
    model_totals: dict[str, ModelUsage] = field(default_factory=dict)


@dataclass
class CostBreakdown:
    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_read_cost: float = 0.0
    cache_write_cost: float = 0.0
    total_cost: float = 0.0


@dataclass
class DayStats:
    date: str
    total_tokens: int = 0
    total_billable: int = 0
    tokens_by_model: dict[str, int] = field(default_factory=dict)


@dataclass
class ProjectUsage:
    project: str
    total_tokens: int = 0
    total_billable: int = 0
    sessions: int = 0


@dataclass
class Tip:
    category: str
    message_en: str
    message_ua: str
    relevance: float = 0.5
    action: str | None = None


@dataclass
class FileChange:
    path: str
    status: str  # "added", "modified", "deleted", "renamed"
    additions: int = 0
    deletions: int = 0
    explanation: str = ""


@dataclass
class DockerChange:
    name: str
    image: str
    status: str  # "new", "removed", "restarted", "crashed"
    ports: list[str] = field(default_factory=list)
    explanation: str = ""


@dataclass
class PortChange:
    port: int
    process: str
    status: str  # "new", "closed"
    explanation: str = ""


@dataclass
class ActivityEntry:
    timestamp: str
    files: list[FileChange] = field(default_factory=list)
    docker_changes: list[DockerChange] = field(default_factory=list)
    port_changes: list[PortChange] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)
    project_dir: str = ""


@dataclass
class EnvironmentSnapshot:
    id: int = 0
    timestamp: str = ""
    label: str = ""
    project_dir: str = ""
    git_branch: str = ""
    git_last_commit: str = ""
    git_tracked_count: int = 0
    git_dirty_files: list[str] = field(default_factory=list)
    containers: list[dict] = field(default_factory=list)
    listening_ports: list[dict] = field(default_factory=list)
    config_checksums: dict[str, str] = field(default_factory=dict)
    haiku_label: str = ""


@dataclass
class SnapshotDiff:
    branch_changed: bool = False
    old_branch: str = ""
    new_branch: str = ""
    dirty_added: list[str] = field(default_factory=list)
    dirty_removed: list[str] = field(default_factory=list)
    containers_added: list[str] = field(default_factory=list)
    containers_removed: list[str] = field(default_factory=list)
    containers_status_changed: list[tuple] = field(default_factory=list)
    ports_opened: list[int] = field(default_factory=list)
    ports_closed: list[int] = field(default_factory=list)
    configs_changed: list[str] = field(default_factory=list)
    configs_added: list[str] = field(default_factory=list)
    configs_removed: list[str] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return (
            int(self.branch_changed)
            + len(self.dirty_added) + len(self.dirty_removed)
            + len(self.containers_added) + len(self.containers_removed)
            + len(self.containers_status_changed)
            + len(self.ports_opened) + len(self.ports_closed)
            + len(self.configs_changed) + len(self.configs_added) + len(self.configs_removed)
        )
