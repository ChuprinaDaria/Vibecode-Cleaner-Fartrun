"""Pytest text-output parser.

Parses the standard summary line at the bottom of pytest output.
Format is stable across pytest 6+: '=== N passed, M failed, K skipped, E errors in 1.23s ==='.
"""
from __future__ import annotations

import re

from core.health.test_runner import ParseResult

# Match individual counters anywhere on the summary line.
_COUNTER_RE = re.compile(
    r"(\d+)\s+(passed|failed|skipped|error|errors)\b"
)
# The summary line begins and ends with at least one '=' run.
_SUMMARY_LINE_RE = re.compile(r"^=+\s*(.*?)\s*=+$", re.MULTILINE)


def parse(output: str, exit_code: int) -> ParseResult:
    passed = failed = errors = skipped = 0
    summary_lines = _SUMMARY_LINE_RE.findall(output)
    # Pick the last summary line that contains at least one counter word.
    for line in reversed(summary_lines):
        if any(kw in line for kw in ("passed", "failed", "skipped", "error")):
            for count, kind in _COUNTER_RE.findall(line):
                n = int(count)
                if kind == "passed":
                    passed = n
                elif kind == "failed":
                    failed = n
                elif kind == "skipped":
                    skipped = n
                elif kind in ("error", "errors"):
                    errors = n
            break
    return ParseResult(passed=passed, failed=failed, errors=errors, skipped=skipped)
