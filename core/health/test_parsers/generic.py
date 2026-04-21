"""Fallback parser for unknown frameworks.

Returns all None so the GUI shows pass/fail by exit code only without
inventing counters.
"""
from __future__ import annotations

from core.health.test_runner import ParseResult


def parse(output: str, exit_code: int) -> ParseResult:
    return ParseResult(passed=None, failed=None, errors=None, skipped=None)
