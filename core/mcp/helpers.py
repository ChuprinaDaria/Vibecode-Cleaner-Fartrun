"""Shared argument resolution + content-shaping helpers for MCP tools."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import mcp.types as mcp_types


def resolve_project_dir(project_dir: str | None) -> str:
    """If ``None``/empty, fall back to CWD — how agents mostly invoke us."""
    if project_dir:
        return str(Path(project_dir).expanduser().resolve())
    return str(Path.cwd())


def ok(text: str) -> list[mcp_types.TextContent]:
    return [mcp_types.TextContent(type="text", text=text)]


def err(text: str) -> list[mcp_types.TextContent]:
    return [mcp_types.TextContent(type="text", text=f"[fartrun error] {text}")]


def json_block(data: Any) -> list[mcp_types.TextContent]:
    return [mcp_types.TextContent(
        type="text", text=json.dumps(data, indent=2, ensure_ascii=False),
    )]
