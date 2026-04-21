"""Tests for `# noqa` marker support on import lines.

Task 10 from docs/superpowers/specs/2026-04-16-health-scanner-reliability-design.md.

The scanner must treat an import line with `# noqa` (or `# noqa: F401`) as
intentionally-kept-despite-unused. The repo has an explicit case in
plugins/security_scan/scanners/base.py that was spuriously flagged.
"""
from __future__ import annotations

import health as health_rs


def _write(root, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _unused(result) -> set[tuple[str, str]]:
    return {(u.path, u.name) for u in result.unused_imports}


def test_bare_noqa_suppresses_unused_import(tmp_path):
    _write(tmp_path, "p.py", "import os  # noqa\nprint('hi')\n")
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert ("p.py", "os") not in _unused(r)


def test_noqa_f401_suppresses_unused_import(tmp_path):
    _write(tmp_path, "p.py", "import os  # noqa: F401\nprint('hi')\n")
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert ("p.py", "os") not in _unused(r)


def test_noqa_f401_in_code_list_suppresses(tmp_path):
    _write(tmp_path, "p.py", "import os  # noqa: F401, F811\n")
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert ("p.py", "os") not in _unused(r)


def test_noqa_wrong_code_does_not_suppress(tmp_path):
    """`# noqa: E501` is about line length, not unused imports."""
    _write(tmp_path, "p.py", "import os  # noqa: E501\n")
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert ("p.py", "os") in _unused(r)


def test_aliased_import_with_noqa(tmp_path):
    """The real-world case: `import sentinel as _sentinel  # noqa: F401`."""
    _write(
        tmp_path,
        "p.py",
        "try:\n"
        "    import sentinel as _sentinel  # noqa: F401\n"
        "except ImportError:\n"
        "    pass\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert ("p.py", "_sentinel") not in _unused(r)


def test_from_import_with_noqa(tmp_path):
    _write(tmp_path, "p.py", "from typing import Any  # noqa: F401\n")
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert ("p.py", "Any") not in _unused(r)


def test_no_noqa_still_flagged(tmp_path):
    """Regression: imports without noqa are still checked."""
    _write(tmp_path, "p.py", "import os\n")
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert ("p.py", "os") in _unused(r)


def test_noqa_is_case_insensitive(tmp_path):
    """Different tools emit different casing; accept all."""
    _write(tmp_path, "p.py", "import os  # NOQA\n")
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert ("p.py", "os") not in _unused(r)
