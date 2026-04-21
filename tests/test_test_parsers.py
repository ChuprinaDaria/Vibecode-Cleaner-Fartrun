"""Per-framework parser tests."""
from pathlib import Path

from core.health.test_parsers import pytest as pytest_parser
from core.health.test_parsers import cargo as cargo_parser
from core.health.test_parsers import jest as jest_parser

FIXTURES = Path(__file__).parent / "fixtures" / "parser_outputs"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_pytest_parser_passed():
    r = pytest_parser.parse(_load("pytest_passed.txt"), exit_code=0)
    assert r.passed == 3
    assert r.failed == 0
    assert r.errors == 0
    assert r.skipped == 0


def test_pytest_parser_failed():
    r = pytest_parser.parse(_load("pytest_failed.txt"), exit_code=1)
    assert r.passed == 3
    assert r.failed == 1
    assert r.errors == 0


def test_pytest_parser_errors():
    r = pytest_parser.parse(_load("pytest_errors.txt"), exit_code=2)
    assert r.passed == 1
    assert r.errors == 1
    assert r.failed == 0


def test_pytest_parser_skipped():
    r = pytest_parser.parse(_load("pytest_skipped.txt"), exit_code=0)
    assert r.passed == 3
    assert r.skipped == 2


def test_pytest_parser_unparseable_returns_zeros():
    """When summary line is missing, return all zeros (not None) — the run
    happened, we just couldn't extract counters from this output shape."""
    r = pytest_parser.parse("garbage output\nno summary line here\n", exit_code=0)
    assert r.passed == 0 and r.failed == 0 and r.errors == 0 and r.skipped == 0


def test_cargo_parser_ok():
    r = cargo_parser.parse(_load("cargo_ok.txt"), exit_code=0)
    assert r.passed == 5
    assert r.failed == 0
    assert r.skipped == 0


def test_cargo_parser_failed():
    r = cargo_parser.parse(_load("cargo_failed.txt"), exit_code=101)
    assert r.passed == 2
    assert r.failed == 1
    assert r.skipped == 1  # cargo "ignored" maps to skipped


def test_jest_parser_passed():
    r = jest_parser.parse(_load("jest_passed.json"), exit_code=0)
    assert r.passed == 12
    assert r.failed == 0


def test_jest_parser_failed():
    r = jest_parser.parse(_load("jest_failed.json"), exit_code=1)
    assert r.passed == 9
    assert r.failed == 3
    assert r.skipped == 1


def test_jest_parser_garbage_returns_none():
    """When no JSON object found, parser returns all None (we don't know counters)."""
    r = jest_parser.parse("npm WARN something\nrandom text\n", exit_code=1)
    assert r.passed is None
    assert r.failed is None


from core.health.test_parsers import vitest as vitest_parser


def test_vitest_parser_passed():
    r = vitest_parser.parse(_load("vitest_passed.json"), exit_code=0)
    assert r.passed == 8
    assert r.failed == 0


def test_vitest_parser_failed():
    r = vitest_parser.parse(_load("vitest_failed.json"), exit_code=1)
    assert r.passed == 5
    assert r.failed == 3


from core.health.test_parsers import generic as generic_parser


def test_generic_parser_returns_all_none():
    r = generic_parser.parse("any output at all", exit_code=0)
    assert r.passed is None
    assert r.failed is None
    assert r.errors is None
    assert r.skipped is None


from core.health.test_parsers import for_framework


def test_for_framework_known():
    p = for_framework("pytest")
    r = p.parse(_load("pytest_passed.txt"), exit_code=0)
    assert r.passed == 3


def test_for_framework_unknown_returns_generic():
    p = for_framework("unknown-thing")
    r = p.parse("anything", exit_code=0)
    assert r.passed is None  # generic
