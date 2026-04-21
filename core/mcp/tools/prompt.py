"""Prompt-builder tool — vibe-coder one-liner → structured prompt."""
from __future__ import annotations

import logging

import mcp.types as mcp_types

from core.prompt_builder import build_prompt as _build_prompt

from core.mcp.helpers import err, ok, resolve_project_dir
from core.mcp.state import db
from core.mcp.tools._registry import register

log = logging.getLogger("fartrun.mcp")


@register(mcp_types.Tool(
    name="build_prompt",
    description=(
        "Turn a vibe-coder's one-liner into a full structured prompt "
        "with concrete file:line hits, stack, frozen list, and a "
        "Context7 directive. READ-ONLY (uses Haiku if configured)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "text": {
                "type": "string",
                "description": "What the user wants, in any language",
            },
        },
        "required": ["text"],
    },
))
async def build_prompt(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    text = args.get("text") or ""
    if not text.strip():
        return err("text is required")

    haiku = None
    try:
        from core.haiku_client import HaikuClient
        client = HaikuClient()
        if client.is_available():
            haiku = client
    except Exception as e:
        log.warning("Haiku client unavailable, falling back to deterministic prompt: %s", e)

    frozen = [f["path"] for f in db().get_frozen_files(project_dir)]
    result = _build_prompt(
        user_text=text, project_dir=project_dir,
        frozen_paths=frozen, haiku_client=haiku,
    )
    return ok(result.final_prompt)
