"""Tool modules — importing this package triggers @register side-effects.

To add a new tool: drop a file in this package with one or more
``@register(Tool(...))``-decorated async handlers, then add the module
to the import list below.
"""
from core.mcp.tools import (  # noqa: F401
    context7_install,
    frozen,
    health,
    prompt,
    save_points,
    status,
)

__all__ = [
    "context7_install",
    "frozen",
    "health",
    "prompt",
    "save_points",
    "status",
]
