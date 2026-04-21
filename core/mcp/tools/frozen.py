"""Frozen-file tools — freeze / unfreeze + sync to CLAUDE.md."""
from __future__ import annotations

import mcp.types as mcp_types

from core import frozen_manager as fm

from core.mcp.helpers import err, ok, resolve_project_dir
from core.mcp.state import db
from core.mcp.tools._registry import register


@register(mcp_types.Tool(
    name="freeze_file",
    description=(
        "Lock a file so it gets listed in CLAUDE.md's DO NOT TOUCH "
        "section. WRITE, non-destructive."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "path": {"type": "string"},
            "note": {"type": "string", "default": ""},
        },
        "required": ["path"],
    },
))
async def freeze_file(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    path = args.get("path") or ""
    note = args.get("note") or ""
    if not path:
        return err("path is required")
    d = db()
    d.add_frozen_file(project_dir, path, note)
    frozen = [f["path"] for f in d.get_frozen_files(project_dir)]
    fm.sync_claude_md(project_dir, frozen)
    return ok(f"Frozen '{path}'. CLAUDE.md updated. "
              f"Total frozen: {len(frozen)}.")


@register(mcp_types.Tool(
    name="unfreeze_file",
    description=(
        "Remove a file from the Don't Touch list. WRITE, reversible."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["path"],
    },
))
async def unfreeze_file(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    path = args.get("path") or ""
    if not path:
        return err("path is required")
    d = db()
    d.remove_frozen_file(project_dir, path)
    frozen = [f["path"] for f in d.get_frozen_files(project_dir)]
    fm.sync_claude_md(project_dir, frozen)
    return ok(f"Unfrozen '{path}'. Total frozen: {len(frozen)}.")
