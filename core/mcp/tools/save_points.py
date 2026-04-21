"""Safety Net save-point tools — create + (destructive) rollback."""
from __future__ import annotations

import mcp.types as mcp_types

from core.mcp.helpers import err, ok, resolve_project_dir
from core.mcp.state import db
from core.mcp.tools._registry import register


@register(mcp_types.Tool(
    name="create_save_point",
    description=(
        "Make a new git-based Save Point. Commits all uncommitted "
        "changes under a tag. WRITE, reversible (rollback gives you "
        "back the prior state)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "label": {"type": "string"},
        },
        "required": ["label"],
    },
))
async def create_save_point(args):
    from core.safety_net import SafetyNet

    project_dir = resolve_project_dir(args.get("project_dir"))
    label = args.get("label") or ""
    if not label:
        return err("label is required")

    sn = SafetyNet(project_dir, db())
    can, reason = sn.can_save()
    if not can:
        return err(f"Can't save: {reason}")
    result = sn.create_save_point(label)
    return ok(
        f"Save Point #{result.id} created.\n"
        f"  commit: {result.commit_hash[:8]}\n"
        f"  files: {result.file_count}, lines: {result.lines_total}"
    )


@register(mcp_types.Tool(
    name="rollback_save_point",
    description=(
        "DESTRUCTIVE. Hard-reset the working tree to a save point. "
        "Creates a backup branch with your current work. Pass "
        "confirm=True to actually perform the rollback — without it "
        "we only explain the consequences."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "save_point_id": {"type": "integer"},
            "keep_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": ("Paths to re-apply from the current "
                                "state after rollback."),
            },
            "confirm": {"type": "boolean", "default": False},
        },
        "required": ["save_point_id"],
    },
))
async def rollback_save_point(args):
    from core.safety_net import SafetyNet

    project_dir = resolve_project_dir(args.get("project_dir"))
    save_point_id = args.get("save_point_id")
    confirm = bool(args.get("confirm", False))
    keep_paths = list(args.get("keep_paths") or [])

    if save_point_id is None:
        return err("save_point_id is required")

    sn = SafetyNet(project_dir, db())
    can, reason = sn.can_rollback(int(save_point_id))
    if not can:
        return err(f"Can't rollback: {reason}")

    preview = sn.rollback_preview(int(save_point_id))
    if not preview:
        return err("Save point not found")

    if not confirm:
        changes = sn.get_changes_since(int(save_point_id))
        changed_names = ", ".join(c.path for c in changes[:8])
        if len(changes) > 8:
            changed_names += f", ... +{len(changes) - 8} more"
        return ok(
            "[DESTRUCTIVE PREVIEW — not executed]\n"
            f"Rolling back to Save Point #{save_point_id} "
            f"(\"{preview.target_label}\") will:\n"
            f"  1. Reset the working tree to commit "
            f"{preview.target_commit[:8]}.\n"
            f"  2. Save your current {len(changes)} changed file(s) to a new "
            f"backup branch so nothing is lost.\n"
            f"  3. Optionally re-apply files listed in `keep_paths` from the "
            f"backup onto the rolled-back state.\n\n"
            f"Changed files that would be affected:\n  {changed_names}\n\n"
            f"To actually do it, call again with confirm=true."
        )

    result = sn.rollback_with_picks(int(save_point_id), keep_paths)
    return ok(
        f"Rolled back to Save Point #{save_point_id}.\n"
        f"  backup branch: {result.backup_branch}\n"
        f"  files restored: {result.files_restored}\n"
        f"  kept after rollback: {len(keep_paths)}"
    )
