"""Tests for absolute-import resolution in module_map.

Task 15 from docs/superpowers/specs/2026-04-16-health-scanner-reliability-design.md.

These tests cover the cases that were producing false positives on the
claude-monitor repo itself:
- `from core.X import Y` (absolute dotted import)
- `from core import X as Y` (absolute import with alias)
- `from plugins.a.b import c` (absolute nested-package import)
- Namespace packages (no __init__.py)
"""
from __future__ import annotations

import health as health_rs


def _write(root, rel: str, content: str = "") -> None:
    """Write a file at root/rel, creating parent dirs."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_absolute_dotted_import_registers_as_dependency(tmp_path):
    """`from core.b import x` must count b.py as imported."""
    _write(tmp_path, "core/__init__.py")
    _write(tmp_path, "core/b.py", "def x(): ...\n")
    _write(
        tmp_path,
        "core/a.py",
        "from core.b import x\n\n\ndef main():\n    x()\n",
    )

    result = health_rs.scan_module_map(str(tmp_path), [])

    by_count = {m.path: m.imported_by_count for m in result.modules}
    assert by_count.get("core/b.py", 0) >= 1, (
        f"core/b.py should be imported by core/a.py; got {by_count}"
    )
    assert "core/b.py" not in result.orphan_candidates


def test_absolute_import_with_alias(tmp_path):
    """`from core import b as x` must count core/b.py as imported.

    This is the `from core import context7_mcp as c7` pattern that
    falsely flagged context7_mcp.py as an orphan in the self-audit.
    """
    _write(tmp_path, "core/__init__.py")
    _write(tmp_path, "core/context7_mcp.py", "def directive(): ...\n")
    _write(
        tmp_path,
        "gui/app.py",
        "from core import context7_mcp as c7\n\n\nc7.directive()\n",
    )

    result = health_rs.scan_module_map(str(tmp_path), [])

    assert "core/context7_mcp.py" not in result.orphan_candidates, (
        f"context7_mcp.py should not be orphan; "
        f"orphans: {result.orphan_candidates}"
    )


def test_absolute_nested_package_import(tmp_path):
    """`from plugins.port_map.collector import collect_ports` must resolve."""
    _write(tmp_path, "plugins/__init__.py")
    _write(tmp_path, "plugins/port_map/__init__.py")
    _write(
        tmp_path,
        "plugins/port_map/collector.py",
        "def collect_ports(): ...\n",
    )
    _write(
        tmp_path,
        "plugins/port_map/plugin.py",
        "from plugins.port_map.collector import collect_ports\n",
    )

    result = health_rs.scan_module_map(str(tmp_path), [])

    assert "plugins/port_map/collector.py" not in result.orphan_candidates


def test_namespace_package_import(tmp_path):
    """PEP 420 implicit namespace package — no __init__.py.

    `from data.hooks_guide_ua import HOOKS_GUIDE` with no data/__init__.py.
    """
    _write(tmp_path, "data/hooks_guide_ua.py", "HOOKS_GUIDE = 'ua'\n")
    _write(
        tmp_path,
        "gui/pages/discover.py",
        "from data.hooks_guide_ua import HOOKS_GUIDE\n\n\nprint(HOOKS_GUIDE)\n",
    )

    result = health_rs.scan_module_map(str(tmp_path), [])

    assert "data/hooks_guide_ua.py" not in result.orphan_candidates


def test_hub_count_reflects_absolute_imports(tmp_path):
    """A file imported from 5 places via absolute paths gets count=5."""
    _write(tmp_path, "core/__init__.py")
    _write(tmp_path, "core/models.py", "class Token: ...\n")
    for i in range(5):
        _write(
            tmp_path,
            f"core/user_{i}.py",
            "from core.models import Token\n\n\nt = Token()\n",
        )

    result = health_rs.scan_module_map(str(tmp_path), [])

    by_count = {m.path: m.imported_by_count for m in result.modules}
    assert by_count.get("core/models.py", 0) == 5, (
        f"expected 5, got {by_count.get('core/models.py')}; "
        f"all counts: {by_count}"
    )


def test_relative_import_still_works(tmp_path):
    """Regression: the existing `.foo` relative-import logic must survive."""
    _write(tmp_path, "pkg/__init__.py")
    _write(tmp_path, "pkg/helper.py", "def util(): ...\n")
    _write(
        tmp_path,
        "pkg/main.py",
        "from .helper import util\n\n\nutil()\n",
    )

    result = health_rs.scan_module_map(str(tmp_path), [])
    assert "pkg/helper.py" not in result.orphan_candidates


def test_relative_sibling_import(tmp_path):
    """`from . import en, ua` — real i18n pattern from the repo.

    __init__.py imports sibling modules via the relative parent dot.
    Every name on the right of `import` must be resolved as a file
    alongside __init__.py.
    """
    _write(
        tmp_path,
        "i18n/__init__.py",
        "from . import en, ua\n\nX = en.STRINGS\nY = ua.STRINGS\n",
    )
    _write(tmp_path, "i18n/en.py", "STRINGS = {}\n")
    _write(tmp_path, "i18n/ua.py", "STRINGS = {}\n")

    result = health_rs.scan_module_map(str(tmp_path), [])
    orphans = set(result.orphan_candidates)
    assert "i18n/en.py" not in orphans, f"orphans: {orphans}"
    assert "i18n/ua.py" not in orphans, f"orphans: {orphans}"


def test_third_party_import_is_not_treated_as_local(tmp_path):
    """`import os` must NOT become an orphan claim against os.py."""
    _write(tmp_path, "a.py", "import os\n\nprint(os.getcwd())\n")

    result = health_rs.scan_module_map(str(tmp_path), [])
    # No local file named os.py exists — nothing to assert on resolution,
    # but the scan must not crash and must not produce phantom modules.
    paths = {m.path for m in result.modules}
    assert "os.py" not in paths
    # a.py itself is an orphan only because nothing imports it — that's fine.
