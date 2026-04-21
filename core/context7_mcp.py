"""Context7 MCP integration — detect, install, suggest.

We don't run Context7 as a subprocess from our GUI. Instead we make sure
it's registered in ``~/.claude/settings.json`` and generate prompts that
tell Claude Code to call it (``use context7 for <library>``). That way
a single source of truth lives in the user's Claude config, and our
Prompt Helper just emits the right directives.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

CONTEXT7_KEY = "context7"
CONTEXT7_COMMAND = "npx"
CONTEXT7_ARGS = ["-y", "@upstash/context7-mcp"]


def _settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _load_settings(path: Path | None = None) -> dict:
    path = path or _settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text() or "{}")
    except json.JSONDecodeError:
        raise


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(path)


def is_context7_installed(settings_path: Path | None = None) -> bool:
    path = settings_path or _settings_path()
    try:
        settings = _load_settings(path)
    except json.JSONDecodeError:
        return False
    servers = settings.get("mcpServers") or {}
    return CONTEXT7_KEY in servers


def install_context7(settings_path: Path | None = None) -> bool:
    """Add Context7 to ``~/.claude/settings.json``. Idempotent."""
    path = settings_path or _settings_path()
    try:
        settings = _load_settings(path)
    except json.JSONDecodeError:
        return False

    servers = settings.setdefault("mcpServers", {})
    if CONTEXT7_KEY in servers:
        return False

    servers[CONTEXT7_KEY] = {
        "command": CONTEXT7_COMMAND,
        "args": list(CONTEXT7_ARGS),
    }
    _atomic_write_json(path, settings)
    return True


def uninstall_context7(settings_path: Path | None = None) -> bool:
    path = settings_path or _settings_path()
    if not path.exists():
        return False
    try:
        settings = _load_settings(path)
    except json.JSONDecodeError:
        return False

    servers = settings.get("mcpServers") or {}
    if CONTEXT7_KEY not in servers:
        return False

    del servers[CONTEXT7_KEY]
    _atomic_write_json(path, settings)
    return True


def npx_available() -> bool:
    return shutil.which("npx") is not None


def build_context7_directive(libraries: list[str]) -> str:
    """Return a short instruction string Claude Code will act on."""
    if not libraries:
        return ""
    libs_str = ", ".join(libraries[:5])
    return (
        f"Before writing any code, call `context7` for these libraries "
        f"to pull up-to-date docs: {libs_str}."
    )
