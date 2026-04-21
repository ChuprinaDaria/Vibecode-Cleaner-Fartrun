"""Cargo test output parser.

Sums counters across all 'test result: ...' lines (one per test binary).
"""
from __future__ import annotations

import re

from core.health.test_runner import ParseResult

_RESULT_RE = re.compile(
    r"test result:\s+\S+\.\s+(\d+)\s+passed;\s+(\d+)\s+failed;\s+(\d+)\s+ignored",
    re.MULTILINE,
)


def parse(output: str, exit_code: int) -> ParseResult:
    passed = failed = skipped = 0
    matches = _RESULT_RE.findall(output)
    for p, f, ign in matches:
        passed += int(p)
        failed += int(f)
        skipped += int(ign)
    return ParseResult(passed=passed, failed=failed, errors=0, skipped=skipped)
