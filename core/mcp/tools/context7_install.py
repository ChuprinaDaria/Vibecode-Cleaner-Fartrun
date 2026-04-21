"""Context7 MCP install / uninstall — manage ~/.claude/settings.json."""
from __future__ import annotations

import mcp.types as mcp_types

from core import context7_mcp as c7

from core.mcp.helpers import ok
from core.mcp.tools._registry import register


@register(mcp_types.Tool(
    name="install_context7",
    description=(
        "Add Context7 MCP to ~/.claude/settings.json (idempotent). "
        "WRITE, reversible via uninstall_context7."
    ),
    inputSchema={"type": "object", "properties": {}},
))
async def install_context7(args):
    changed = c7.install_context7()
    if changed:
        return ok("Context7 MCP added to ~/.claude/settings.json. "
                  "Restart Claude Code to pick it up.")
    return ok("Context7 is already installed.")


@register(mcp_types.Tool(
    name="uninstall_context7",
    description=(
        "Remove Context7 MCP from ~/.claude/settings.json. "
        "WRITE, reversible."
    ),
    inputSchema={"type": "object", "properties": {}},
))
async def uninstall_context7(args):
    changed = c7.uninstall_context7()
    return ok("Context7 removed." if changed
              else "Context7 was not installed.")
