"""Tests for conservative commented-code detection (Task 13).

The old regex flagged any comment block containing `=`, parens, or
a stopword at ≥40% density. English prose with tokens like
`confirm=True` or `return None` got swept in.

The new rule: commented text must parse as valid Python (or JS) with
non-trivial statements. Plain English does not.
"""
from __future__ import annotations

import health as health_rs


def _write(root, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _commented_lines(result) -> list[tuple[str, int, int]]:
    return [(b.path, b.start_line, b.end_line) for b in result.commented_blocks]


def test_real_commented_code_flagged(tmp_path):
    """Classic dead code commented out — must still fire."""
    _write(
        tmp_path,
        "p.py",
        "x = 1\n"
        "# def old_function(a, b):\n"
        "#     y = a + b\n"
        "#     z = y * 2\n"
        "#     return z\n"
        "# print(old_function(1, 2))\n"
        "\n"
        "y = 2\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert any(p == "p.py" for p, _, _ in _commented_lines(r))


def test_english_prose_with_equals_not_flagged(tmp_path):
    """The case that blew up self-audit: english comment mentioning
    `confirm=True` and `return None` inline."""
    _write(
        tmp_path,
        "p.py",
        "x = 1\n"
        "# The confirm=True execution path is already covered by\n"
        "# tests/test_safety_net.py. Keeping a separate MCP integration\n"
        "# test for it would re-open the same SQLite file across tool\n"
        "# boundaries and hit locking issues, so we trust the underlying\n"
        "# primitive and verify only the preview branch here.\n"
        "y = 2\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert not _commented_lines(r), (
        f"English prose was flagged: {_commented_lines(r)}"
    )


def test_module_docstring_style_comment_not_flagged(tmp_path):
    """Long explanatory comment at top of module."""
    _write(
        tmp_path,
        "p.py",
        "# This module parses session logs. The input is JSONL, one\n"
        "# record per line. Each record has a timestamp and a payload.\n"
        "# We group by session id and compute totals.\n"
        "# Returns a list of session summaries sorted by time.\n"
        "# See docs/sessions.md for the format spec.\n"
        "\n"
        "def parse(): ...\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert not _commented_lines(r)


def test_short_comment_block_not_flagged(tmp_path):
    """Blocks under 5 lines never fire — existing threshold."""
    _write(
        tmp_path,
        "p.py",
        "x = 1\n"
        "# def old():\n"
        "#     return 1\n"
        "y = 2\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert not _commented_lines(r)


def test_commented_imports_block_flagged(tmp_path):
    """A block that's all commented imports — clearly dead code."""
    _write(
        tmp_path,
        "p.py",
        "x = 1\n"
        "# import os\n"
        "# import sys\n"
        "# from pathlib import Path\n"
        "# from typing import Optional\n"
        "# from collections import defaultdict\n"
        "y = 2\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert any(p == "p.py" for p, _, _ in _commented_lines(r))


def test_todo_list_in_comments_not_flagged(tmp_path):
    """English TODO / notes block — no Python syntax."""
    _write(
        tmp_path,
        "p.py",
        "x = 1\n"
        "# TODO items for next release:\n"
        "# - add retry logic with exponential backoff\n"
        "# - refactor the parser to stream output\n"
        "# - investigate the memory leak reported by Anna\n"
        "# - ship a migration script for the new schema\n"
        "y = 2\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert not _commented_lines(r)
