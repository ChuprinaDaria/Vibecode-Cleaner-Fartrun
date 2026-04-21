"""Per-framework output parsers for the background test runner."""
from __future__ import annotations

from types import ModuleType

from core.health.test_parsers import (
    cargo, generic, jest, pytest, vitest,
)

_REGISTRY: dict[str, ModuleType] = {
    "pytest": pytest,
    "cargo": cargo,
    "jest": jest,
    "vitest": vitest,
    "generic": generic,
}


def for_framework(name: str) -> ModuleType:
    """Return the parser module for the given framework name.

    Unknown names fall back to the generic (exit-code-only) parser.
    The returned module exposes a `parse(output: str, exit_code: int) -> ParseResult`
    function.
    """
    return _REGISTRY.get(name, generic)
