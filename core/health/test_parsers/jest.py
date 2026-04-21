"""Jest --json output parser.

Jest writes a JSON object to stdout when invoked with --json. npm wrappers
prepend stuff like 'npm info ...', so we scan for the first '{' and try
to json-decode from there to the matching closing brace.
"""
from __future__ import annotations

import json

from core.health.test_runner import ParseResult


def _extract_json(output: str) -> dict | None:
    start = output.find("{")
    if start < 0:
        return None
    # Walk forward until balanced; tolerate string contents.
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(output)):
        ch = output[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(output[start:i+1])
                except json.JSONDecodeError:
                    return None
    return None


def parse(output: str, exit_code: int) -> ParseResult:
    obj = _extract_json(output)
    if obj is None:
        return ParseResult(passed=None, failed=None, errors=None, skipped=None)
    return ParseResult(
        passed=obj.get("numPassedTests"),
        failed=obj.get("numFailedTests"),
        errors=0,
        skipped=obj.get("numPendingTests"),
    )
