"""Public façade for the MCP server package.

Re-exports stable names so the CLI, tests, and other internal callers
keep working without chasing internal moves. Real implementation
lives in submodules — adding a new tool means dropping a file in
``core/mcp/tools/``, not editing this file.
"""
from __future__ import annotations

from core.mcp.server import main, server  # noqa: F401
from core.mcp.state import (  # noqa: F401
    db as _db,
    reset_db_for_tests as _reset_db_for_tests,
)
from core.mcp.tools.context7_install import (  # noqa: F401
    install_context7 as _install_context7,
    uninstall_context7 as _uninstall_context7,
)
from core.mcp.tools.frozen import (  # noqa: F401
    freeze_file as _freeze_file,
    unfreeze_file as _unfreeze_file,
)
from core.mcp.tools.prompt import build_prompt as _build_prompt  # noqa: F401
from core.mcp.tools.save_points import (  # noqa: F401
    create_save_point as _create_save_point,
    rollback_save_point as _rollback,
)
from core.mcp.tools.status import (  # noqa: F401
    detect_stack as _detect_stack,
    get_activity as _get_activity,
    get_status as _get_status,
    list_frozen as _list_frozen,
    list_prompts as _list_prompts,
    list_save_points as _list_save_points,
    search_code as _search_code,
)
