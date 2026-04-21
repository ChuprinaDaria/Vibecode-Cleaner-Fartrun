"""Data models for health check results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConfigFile:
    path: str
    kind: str           # "env", "docker", "python_deps", "js_config", "ci", "build"
    description: str
    severity: str       # "warning", "info"


@dataclass
class ConfigInventoryResult:
    configs: list[ConfigFile] = field(default_factory=list)
    env_file_count: int = 0
    has_docker: bool = False
    has_ci: bool = False


@dataclass
class HealthFinding:
    check_id: str       # "map.file_tree", "map.entry_points", etc.
    title: str
    severity: str       # "critical", "high", "medium", "low", "info"
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class HealthReport:
    project_dir: str
    findings: list[HealthFinding] = field(default_factory=list)
    file_tree: dict = field(default_factory=dict)
    entry_points: list[dict] = field(default_factory=list)
    module_map: dict = field(default_factory=dict)
    monsters: list[dict] = field(default_factory=list)
    configs: list[dict] = field(default_factory=list)
    unused_imports: list[dict] = field(default_factory=list)
    unused_definitions: list[dict] = field(default_factory=list)
    commented_blocks: list[dict] = field(default_factory=list)
