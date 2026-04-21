"""Vitest --reporter=json output parser.

Vitest's JSON reporter matches Jest's shape for the counters we read.
We delegate to the Jest parser to avoid duplicating the JSON-extraction
walker; if the formats ever diverge, fork this module.
"""
from __future__ import annotations

from core.health.test_parsers import jest as _jest
from core.health.test_runner import ParseResult


def parse(output: str, exit_code: int) -> ParseResult:
    return _jest.parse(output, exit_code)
