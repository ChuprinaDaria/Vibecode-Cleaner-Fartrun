"""Shared scanner primitives — Finding model, sentinel availability."""
from __future__ import annotations

import logging
from dataclasses import dataclass

try:
    from orjson import loads as json_loads
except ImportError:
    from json import loads as json_loads

log = logging.getLogger(__name__)


@dataclass
class Finding:
    type: str        # "docker", "config", "deps", "network", ...
    severity: str    # "critical", "high", "medium", "low"
    description: str
    source: str


# --- Optional Rust sentinel ---

sentinel_available = False
try:
    import sentinel as _sentinel  # noqa: F401
    sentinel_available = True
except ImportError:
    log.warning("sentinel not installed — Rust scanners disabled. pip install sentinel")
