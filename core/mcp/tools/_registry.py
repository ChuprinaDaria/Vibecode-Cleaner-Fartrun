"""Tool registry: each tool module @register's its definition + handler.

Adding a new tool = create a new file (or function) decorated with
``@register(Tool(...))`` — server.py automatically picks it up by
importing the ``tools`` package.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import mcp.types as mcp_types

ToolHandler = Callable[[dict[str, Any]], Awaitable[list[mcp_types.TextContent]]]

TOOL_DEFS: list[mcp_types.Tool] = []
TOOL_HANDLERS: dict[str, ToolHandler] = {}


def register(tool_def: mcp_types.Tool) -> Callable[[ToolHandler], ToolHandler]:
    """Pin tool_def into the list and bind the handler under its name."""
    def decorator(fn: ToolHandler) -> ToolHandler:
        if tool_def.name in TOOL_HANDLERS:
            raise RuntimeError(f"Tool already registered: {tool_def.name}")
        TOOL_DEFS.append(tool_def)
        TOOL_HANDLERS[tool_def.name] = fn
        return fn
    return decorator
