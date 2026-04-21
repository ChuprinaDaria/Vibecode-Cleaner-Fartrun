"""Tests for core/stack_detector.py — manifest parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.stack_detector import (
    DetectedLib, detect_stack, docs_worthy,
)


class TestPackageJson:
    def test_extracts_deps(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "name": "x",
            "dependencies": {"react": "^19.0.0", "next": "15.0.0"},
            "devDependencies": {"typescript": "5.0.0"},
        }))
        libs = detect_stack(str(tmp_path))
        names = {l.name for l in libs}
        assert "react" in names
        assert "next" in names
        assert "typescript" in names

    def test_bad_json_is_skipped(self, tmp_path):
        (tmp_path / "package.json").write_text("{ not json")
        assert detect_stack(str(tmp_path)) == []


class TestPyprojectToml:
    def test_pep621_deps(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            "name = \"x\"\n"
            "dependencies = [\"fastapi>=0.100\", \"pydantic>=2.0\"]\n"
        )
        libs = detect_stack(str(tmp_path))
        names = {l.name for l in libs}
        assert "fastapi" in names
        assert "pydantic" in names

    def test_poetry_deps(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.poetry]\n"
            "name = \"x\"\n"
            "[tool.poetry.dependencies]\n"
            "python = \"^3.11\"\n"
            "django = \"^5.0\"\n"
        )
        libs = detect_stack(str(tmp_path))
        names = {l.name for l in libs}
        assert "django" in names
        # python itself is excluded
        assert "python" not in names


class TestRequirementsTxt:
    def test_basic(self, tmp_path):
        (tmp_path / "requirements.txt").write_text(
            "# comment\n"
            "Django==5.0\n"
            "fastapi>=0.100\n"
            "\n"
            "-r other.txt\n"
        )
        libs = detect_stack(str(tmp_path))
        names = {l.name for l in libs}
        assert "django" in names
        assert "fastapi" in names


class TestDocsWorthy:
    def test_filters_to_known(self):
        libs = [
            DetectedLib(name="react", version="19", ecosystem="npm"),
            DetectedLib(name="some-obscure-lib", version="1.0", ecosystem="npm"),
            DetectedLib(name="fastapi", version="0.1", ecosystem="pypi"),
        ]
        out = docs_worthy(libs)
        names = {l.name for l in out}
        assert "react" in names
        assert "fastapi" in names
        assert "some-obscure-lib" not in names

    def test_dedupes(self):
        libs = [
            DetectedLib(name="react", version="19", ecosystem="npm"),
            DetectedLib(name="react", version="18", ecosystem="npm"),
        ]
        out = docs_worthy(libs)
        assert len(out) == 1


class TestNoManifest:
    def test_empty_dir(self, tmp_path):
        assert detect_stack(str(tmp_path)) == []

    def test_missing_dir(self, tmp_path):
        assert detect_stack(str(tmp_path / "nope")) == []
