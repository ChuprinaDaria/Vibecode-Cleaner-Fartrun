"""MCP Server and Skill installer — adds to ~/.claude/settings.json."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_ENV_VAR_RE = re.compile(r"`([A-Z][A-Z0-9_]{2,})`")

_COMMON_NON_ENV = {"README", "LICENSE", "INSTALL", "TODO", "NOTE", "IMPORTANT",
                   "HTTPS", "HTTP", "JSON", "YAML", "TOML", "HTML", "CSS"}


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict = {"command": self.command, "args": self.args}
        if self.env:
            d["env"] = self.env
        return d


def detect_mcp_type(files: dict[str, bool]) -> str:
    """Detect MCP server type from repo file presence."""
    if files.get("package.json"):
        return "npm"
    if files.get("requirements.txt") or files.get("pyproject.toml") or files.get("setup.py"):
        return "pip"
    return "unknown"


def parse_mcp_readme(readme_content: str) -> list[str]:
    """Extract environment variable names from README."""
    env_vars = _ENV_VAR_RE.findall(readme_content)
    return [v for v in set(env_vars) if v not in _COMMON_NON_ENV and len(v) >= 4]



