"""Config loader for dev-monitor. TOML-based with defaults."""

from __future__ import annotations

import logging
import os
import tomllib
from pathlib import Path

log = logging.getLogger("fartrun.config")

DEFAULTS = {
    "general": {
        "refresh_interval": 5,
        "language": "en",
    },
    "sounds": {
        "enabled": True,
        "mode": "classic",
        "quiet_hours_start": "23:00",
        "quiet_hours_end": "07:00",
    },
    "alerts": {
        "cooldown_seconds": 300,
        "desktop_notifications": True,
    },
    "paths": {},
    "plugins": {
        "docker_monitor": {
            "enabled": True,
            "cpu_threshold": 80,
            "ram_threshold": 85,
            "alert_on_exit": True,
        },
        "port_map": {
            "enabled": True,
        },
        "security_scan": {
            "enabled": True,
            "scan_interval": 3600,
            "scan_paths": ["~"],
        },
    },
    "snapshots": {
        "enabled": True,
        "auto_interval_minutes": 30,
        "max_snapshots": 50,
    },
    "haiku": {
        "api_key": "",
    },
    "ai": {
        "provider": "anthropic",
        "api_key": "",
        "model": "",
        "base_url": "",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base recursively."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _project_root() -> Path:
    """Find project root (directory containing pyproject.toml or config.toml)."""
    current = Path(__file__).resolve().parent
    for parent in [current, current.parent, current.parent.parent]:
        if (parent / "pyproject.toml").exists() or (parent / "config.toml").exists():
            return parent
    return current.parent


def load_config(path: Path | None = None) -> dict:
    """Load TOML config. Resolution: explicit path > MONITOR_CONFIG env > platform config dir > project root."""
    if path is None:
        env_path = os.environ.get("MONITOR_CONFIG")
        if env_path:
            path = Path(env_path)
        else:
            # Try platform config dir first
            try:
                from core.platform import get_platform
                platform_config = get_platform().config_dir() / "config.toml"
                if platform_config.exists():
                    path = platform_config
            except Exception as e:
                log.warning("platform config_dir lookup failed, falling back to project root: %s", e)
            if path is None:
                path = _project_root() / "config.toml"

    user_config = {}
    if path.exists():
        with open(path, "rb") as f:
            user_config = tomllib.load(f)

    return _deep_merge(DEFAULTS, user_config)
