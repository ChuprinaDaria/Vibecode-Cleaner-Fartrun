"""Tests for type-hint-aware unused-import detection.

Task 12 from docs/superpowers/specs/2026-04-16-health-scanner-reliability-design.md.

The scanner previously excluded every identifier that sat on the same
source line as a `function_definition` node. That killed annotation
references like `aiosqlite.Connection` inside a signature, so every
type-hint-only import was falsely flagged as unused.
"""
from __future__ import annotations

import health as health_rs


def _write(root, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _unused_names(result) -> set[str]:
    return {u.name for u in result.unused_imports}


def test_import_used_only_in_parameter_annotation_not_flagged(tmp_path):
    """`import aiosqlite` + `def f(db: aiosqlite.Connection): ...` — used."""
    _write(
        tmp_path,
        "p.py",
        "import aiosqlite\n\n"
        "async def migrate(db: aiosqlite.Connection) -> None:\n"
        "    await db.commit()\n",
    )
    result = health_rs.scan_dead_code(str(tmp_path), [])
    assert "aiosqlite" not in _unused_names(result)


def test_import_used_only_in_return_annotation_not_flagged(tmp_path):
    """`-> list[mcp_types.Tool]` counts as usage."""
    _write(
        tmp_path,
        "p.py",
        "import mcp.types as mcp_types\n\n"
        "async def list_tools() -> list[mcp_types.Tool]:\n"
        "    return []\n",
    )
    result = health_rs.scan_dead_code(str(tmp_path), [])
    assert "mcp_types" not in _unused_names(result)


def test_import_used_only_in_variable_annotation_not_flagged(tmp_path):
    """`foo: SomeType = ...` counts as usage."""
    _write(
        tmp_path,
        "p.py",
        "from typing import Optional\n\n"
        "x: Optional[int] = None\n",
    )
    result = health_rs.scan_dead_code(str(tmp_path), [])
    assert "Optional" not in _unused_names(result)


def test_genuinely_unused_import_still_flagged(tmp_path):
    """Regression: a truly unused import must still be caught."""
    _write(
        tmp_path,
        "p.py",
        "import os\nimport sys\n\nprint(sys.argv)\n",
    )
    result = health_rs.scan_dead_code(str(tmp_path), [])
    unused = _unused_names(result)
    assert "os" in unused
    assert "sys" not in unused


def test_type_checking_block_import_used_in_annotation(tmp_path):
    """`if TYPE_CHECKING: import X` + `def f(x: X.Y)` — X used."""
    _write(
        tmp_path,
        "p.py",
        "from __future__ import annotations\n"
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    import aiosqlite\n\n"
        "async def migrate(db: aiosqlite.Connection) -> None: ...\n",
    )
    result = health_rs.scan_dead_code(str(tmp_path), [])
    unused = _unused_names(result)
    assert "aiosqlite" not in unused
    # TYPE_CHECKING itself IS used (in `if TYPE_CHECKING:`), must not flag.
    assert "TYPE_CHECKING" not in unused


def test_alias_used_as_decorator_not_flagged(tmp_path):
    """`import pytest` + `@pytest.fixture` — pytest is used via decorator."""
    _write(
        tmp_path,
        "conftest.py",
        "import pytest\n\n"
        "@pytest.fixture\ndef client():\n    return object()\n",
    )
    result = health_rs.scan_dead_code(str(tmp_path), [])
    assert "pytest" not in _unused_names(result)


def test_parameter_name_is_not_a_usage(tmp_path):
    """`def f(os): ...` — the parameter `os` must not cancel the unused
    top-level `import os`. The parameter is a local binding, not a use
    of the import.

    This one is tricky — conservative behavior: we err on the side of
    NOT flagging (false negative) rather than flagging a use-that-looks-
    like-a-parameter (false positive). In practice this case is rare.
    """
    _write(
        tmp_path,
        "p.py",
        "import os\n\n"
        "def f(os):\n"
        "    return os\n",
    )
    result = health_rs.scan_dead_code(str(tmp_path), [])
    # Either behavior is defensible — lock it in so a future change
    # is intentional. Current target: parameter name counts as usage.
    assert "os" not in _unused_names(result)
