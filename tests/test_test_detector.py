"""Tests for project-type test framework detection."""
from pathlib import Path

import pytest

from core.health.test_detector import detect_framework


def _write(tmp_path: Path, name: str, content: str = "") -> None:
    (tmp_path / name).write_text(content)


def test_detects_pytest_from_pyproject(tmp_path):
    _write(tmp_path, "pyproject.toml", '[tool.pytest.ini_options]\nminversion="6.0"\n')
    name, cmd = detect_framework(tmp_path)
    assert name == "pytest"
    assert cmd[0] == "pytest"


def test_detects_cargo_from_cargo_toml(tmp_path):
    _write(tmp_path, "Cargo.toml", '[package]\nname = "x"\nversion = "0.1.0"\n')
    name, cmd = detect_framework(tmp_path)
    assert name == "cargo"
    assert cmd[:2] == ["cargo", "test"]


def test_detects_jest_from_package_json(tmp_path):
    _write(tmp_path, "package.json", '{"scripts": {"test": "jest"}}')
    name, cmd = detect_framework(tmp_path)
    assert name == "jest"
    # Append --json so parser has structured input.
    assert "--json" in " ".join(cmd)


def test_detects_vitest_from_package_json(tmp_path):
    _write(tmp_path, "package.json", '{"scripts": {"test": "vitest run"}}')
    name, cmd = detect_framework(tmp_path)
    assert name == "vitest"
    assert "--reporter=json" in " ".join(cmd)


def test_falls_back_to_generic_for_other_npm_test(tmp_path):
    _write(tmp_path, "package.json", '{"scripts": {"test": "mocha"}}')
    name, cmd = detect_framework(tmp_path)
    assert name == "generic"
    assert cmd == ["npm", "test"]


def test_pyproject_wins_over_cargo_when_both_present(tmp_path):
    _write(tmp_path, "pyproject.toml", '[tool.pytest.ini_options]\n')
    _write(tmp_path, "Cargo.toml", '[package]\nname="x"\n')
    name, _ = detect_framework(tmp_path)
    assert name == "pytest"


def test_empty_project_returns_generic_with_empty_cmd(tmp_path):
    name, cmd = detect_framework(tmp_path)
    assert name == "generic"
    assert cmd == []


def test_pytest_via_conftest_only(tmp_path):
    """Project with no pyproject but conftest.py + tests/ folder -> pytest."""
    (tmp_path / "tests").mkdir()
    _write(tmp_path / "tests", "conftest.py")
    name, _ = detect_framework(tmp_path)
    assert name == "pytest"
