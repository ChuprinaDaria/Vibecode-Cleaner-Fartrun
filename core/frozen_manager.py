"""Frozen Files manager — keep files AI must not touch.

Two layers of protection:

1. Documentation — writes a ``## DO NOT TOUCH — managed by fartrun``
   section into the project's ``CLAUDE.md`` so AI knows what's off-limits.
2. Enforcement — installs a PreToolUse hook into ``~/.claude/settings.json``
   that blocks Edit/Write on frozen paths (hook script lives in
   ``core.hooks.frozen_check``).

The user can temporarily disable the hook via a config toggle
(``[frozen_files].hook_enabled = false``) without losing the list.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

log = logging.getLogger(__name__)

CLAUDE_MD_MARKER_START = "<!-- fartrun-frozen-start -->"
CLAUDE_MD_MARKER_END = "<!-- fartrun-frozen-end -->"
CLAUDE_MD_SECTION_HEADER = "## DO NOT TOUCH — managed by fartrun"

HOOK_MATCHER_ID = "fartrun-frozen-check"


# ---------------------------------------------------------------- CLAUDE.md

def _frozen_section(paths: list[str]) -> str:
    if not paths:
        body = ("_No frozen files yet. Add them in fartrun → "
                "Save Points → Don't touch list._")
    else:
        body = "\n".join(f"- `{p}`" for p in paths)

    return (
        f"{CLAUDE_MD_MARKER_START}\n"
        f"{CLAUDE_MD_SECTION_HEADER}\n\n"
        f"These files are locked by the developer. **Do not edit or "
        f"rewrite them.** Build around them.\n\n"
        f"{body}\n"
        f"{CLAUDE_MD_MARKER_END}\n"
    )


def sync_claude_md(project_dir: str, frozen_paths: list[str]) -> bool:
    """Write/update the fartrun-managed section in project CLAUDE.md.

    Returns True if the file changed.
    """
    claude_md = Path(project_dir) / "CLAUDE.md"
    new_section = _frozen_section(sorted(frozen_paths))

    try:
        existing = claude_md.read_text() if claude_md.exists() else ""
    except OSError as e:
        log.warning("Can't read %s: %s", claude_md, e)
        return False

    if CLAUDE_MD_MARKER_START in existing and CLAUDE_MD_MARKER_END in existing:
        # Replace whole managed block (incl. markers)
        pattern = re.compile(
            re.escape(CLAUDE_MD_MARKER_START) + r".*?"
            + re.escape(CLAUDE_MD_MARKER_END) + r"\n?",
            re.DOTALL,
        )
        updated = pattern.sub(new_section, existing, count=1)
    else:
        sep = "\n\n" if existing and not existing.endswith("\n\n") else ""
        updated = existing + sep + new_section

    if updated == existing:
        return False

    try:
        claude_md.write_text(updated)
    except OSError as e:
        log.warning("Can't write %s: %s", claude_md, e)
        return False
    return True


# ---------------------------------------------------------------- hook

def _hook_command() -> str:
    """Return the shell command that invokes our frozen-check hook."""
    # Using sys.executable gives us a portable path to the installed Python
    # with our package available. The hook module reads stdin.
    py = sys.executable or "python3"
    return f"{py} -m core.hooks.frozen_check"


def _load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text() or "{}")
    except json.JSONDecodeError as e:
        log.warning("Malformed %s: %s — not touching", path, e)
        raise


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(path)


def install_hook(settings_path: Path | None = None) -> bool:
    """Add the PreToolUse hook to ``~/.claude/settings.json``.

    Idempotent: if our hook is already there, returns False.
    Leaves any other user hooks intact.
    """
    path = settings_path or (Path.home() / ".claude" / "settings.json")

    try:
        settings = _load_settings(path)
    except json.JSONDecodeError:
        return False

    hooks = settings.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])

    for entry in pre:
        if entry.get("_id") == HOOK_MATCHER_ID:
            return False  # already installed

    pre.append({
        "_id": HOOK_MATCHER_ID,
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
            {"type": "command", "command": _hook_command()},
        ],
    })

    _atomic_write_json(path, settings)
    return True


def uninstall_hook(settings_path: Path | None = None) -> bool:
    path = settings_path or (Path.home() / ".claude" / "settings.json")
    if not path.exists():
        return False

    try:
        settings = _load_settings(path)
    except json.JSONDecodeError:
        return False

    hooks = settings.get("hooks", {})
    pre = hooks.get("PreToolUse", [])
    kept = [h for h in pre if h.get("_id") != HOOK_MATCHER_ID]
    if len(kept) == len(pre):
        return False

    hooks["PreToolUse"] = kept
    _atomic_write_json(path, settings)
    return True


def is_hook_installed(settings_path: Path | None = None) -> bool:
    path = settings_path or (Path.home() / ".claude" / "settings.json")
    if not path.exists():
        return False
    try:
        settings = _load_settings(path)
    except json.JSONDecodeError:
        return False
    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        if entry.get("_id") == HOOK_MATCHER_ID:
            return True
    return False
