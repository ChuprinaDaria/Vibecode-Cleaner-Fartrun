"""Read-only status / listing / search tools."""
from __future__ import annotations

import mcp.types as mcp_types

from core import context7_mcp as c7
from core import frozen_manager as fm
from core.activity_tracker import ActivityTracker, serialize_activity
from core.code_searcher import search_codebase
from core.prompt_parser import get_recent_prompts
from core.stack_detector import detect_stack as _detect_stack_fn, docs_worthy

from core.mcp.helpers import json_block, ok, resolve_project_dir
from core.mcp.state import db
from core.mcp.tools._registry import register


@register(mcp_types.Tool(
    name="get_status",
    description=(
        "Quick overview of a project: count of save points, frozen "
        "files, recent user prompts, detected stack. READ-ONLY."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path. Defaults to CWD.",
            },
        },
    },
))
async def get_status(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    d = db()
    save_points = d.get_save_points(project_dir, limit=5)
    frozen = d.get_frozen_files(project_dir)
    prompts = get_recent_prompts(project_dir, limit=3)
    stack = _detect_stack_fn(project_dir)
    worthy = docs_worthy(stack)

    return json_block({
        "project_dir": project_dir,
        "save_points": {
            "count": len(save_points),
            "latest": save_points[0]["label"] if save_points else None,
        },
        "frozen_files": {
            "count": len(frozen),
            "paths": [f["path"] for f in frozen[:10]],
        },
        "recent_prompts": [
            {"when": p.timestamp[:16], "text": p.short} for p in prompts
        ],
        "stack": {
            "total": len(stack),
            "docs_worthy": [lib.name for lib in worthy],
        },
        "context7_installed": c7.is_context7_installed(),
        "frozen_hook_installed": fm.is_hook_installed(),
    })


@register(mcp_types.Tool(
    name="list_save_points",
    description="List Save Points for a project. READ-ONLY.",
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "limit": {"type": "integer", "default": 20},
        },
    },
))
async def list_save_points(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    limit = int(args.get("limit") or 20)
    return json_block(db().get_save_points(project_dir, limit=limit))


@register(mcp_types.Tool(
    name="list_frozen",
    description="List frozen (Don't Touch) files for a project. READ-ONLY.",
    inputSchema={
        "type": "object",
        "properties": {"project_dir": {"type": "string"}},
    },
))
async def list_frozen(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    return json_block(db().get_frozen_files(project_dir))


@register(mcp_types.Tool(
    name="list_prompts",
    description=(
        "Return the last N real user prompts this project received "
        "in Claude Code (tool results are filtered out). READ-ONLY."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "limit": {"type": "integer", "default": 10},
        },
    },
))
async def list_prompts(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    limit = int(args.get("limit") or 10)
    prompts = get_recent_prompts(project_dir, limit=limit)
    return json_block([
        {
            "timestamp": p.timestamp,
            "session_id": p.session_id,
            "text": p.text,
        } for p in prompts
    ])


@register(mcp_types.Tool(
    name="get_activity",
    description=(
        "Current uncommitted changes, recent commits, Docker/port "
        "diffs. READ-ONLY."
    ),
    inputSchema={
        "type": "object",
        "properties": {"project_dir": {"type": "string"}},
    },
))
async def get_activity(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    tracker = ActivityTracker(project_dir)
    entry = tracker.collect_activity()
    return ok(serialize_activity(entry))


@register(mcp_types.Tool(
    name="detect_project_stack",
    description=(
        "Parse manifests and return detected libraries with versions. "
        "READ-ONLY."
    ),
    inputSchema={
        "type": "object",
        "properties": {"project_dir": {"type": "string"}},
    },
))
async def detect_stack(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    stack = _detect_stack_fn(project_dir)
    return json_block([
        {"name": lib.name, "version": lib.version, "ecosystem": lib.ecosystem}
        for lib in stack
    ])


@register(mcp_types.Tool(
    name="search_code",
    description=(
        "Run a grep-style keyword search across the project. READ-ONLY."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
            },
            "max_per_keyword": {"type": "integer", "default": 5},
        },
        "required": ["keywords"],
    },
))
async def search_code(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    keywords = args.get("keywords") or []
    max_per = int(args.get("max_per_keyword") or 5)
    matches = search_codebase(project_dir, keywords, max_per_keyword=max_per)
    return json_block([
        {"path": m.path, "line": m.line_number,
         "snippet": m.snippet, "keyword": m.keyword}
        for m in matches
    ])
