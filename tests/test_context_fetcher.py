"""Tests for core/context_fetcher.py — SDK Context Fetcher."""

import json
from pathlib import Path

import pytest

from core.context_fetcher import (
    ContextFetcher, _strip_html, _WELL_KNOWN_PYTHON, _WELL_KNOWN_JS,
)


class TestStripHTML:
    def test_basic_html(self):
        result = _strip_html("<p>Hello <b>world</b></p>")
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result

    def test_script_removal(self):
        result = _strip_html('<script>alert("xss")</script><p>Content</p>')
        assert "alert" not in result
        assert "Content" in result

    def test_entities(self):
        result = _strip_html("&amp; &lt; &gt;")
        assert "&" in result
        assert "<" in result


class TestWellKnownLists:
    def test_python_has_common_packages(self):
        for pkg in ["django", "flask", "fastapi", "numpy", "pandas", "pytest"]:
            assert pkg in _WELL_KNOWN_PYTHON, f"{pkg} missing from Python list"

    def test_js_has_common_packages(self):
        for pkg in ["react", "vue", "express", "typescript", "tailwindcss"]:
            assert pkg in _WELL_KNOWN_JS, f"{pkg} missing from JS list"


class TestDetectUnknown:
    def test_python_requirements(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("django==5.0\nflask==3.0\nsome-obscure-sdk==0.1\n")
        fetcher = ContextFetcher(str(tmp_path))
        unknown = fetcher.detect_unknown_packages()
        names = [p.name for p in unknown]
        assert "some_obscure_sdk" in names
        assert "django" not in names
        assert "flask" not in names

    def test_js_package_json(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {
                "react": "^18.0",
                "super-niche-lib": "^0.1",
            }
        }))
        fetcher = ContextFetcher(str(tmp_path))
        unknown = fetcher.detect_unknown_packages()
        names = [p.name for p in unknown]
        assert "super-niche-lib" in names
        assert "react" not in [p.name for p in unknown]

    def test_no_deps_files(self, tmp_path):
        fetcher = ContextFetcher(str(tmp_path))
        unknown = fetcher.detect_unknown_packages()
        assert unknown == []


class TestGenerateContext:
    def test_creates_file(self, tmp_path):
        (tmp_path / "app.py").write_text("print('hello')\n")
        fetcher = ContextFetcher(str(tmp_path))
        path = fetcher.generate_context_file()
        assert Path(path).exists()
        content = Path(path).read_text()
        assert "Project:" in content

    def test_includes_stack(self, tmp_path):
        (tmp_path / "manage.py").write_text("#!/usr/bin/env python\n")
        (tmp_path / "app.py").write_text("import django\n")
        fetcher = ContextFetcher(str(tmp_path))
        path = fetcher.generate_context_file()
        content = Path(path).read_text()
        assert "Python" in content
        assert "Django" in content


class TestDocsContextCheck:
    def test_ui_vocabulary_triggers_on_frontend(self, tmp_path):
        (tmp_path / "App.tsx").write_text("export default function App() {}\n")
        from core.health.models import HealthReport
        from core.health.docs_context import check_ui_vocabulary
        report = HealthReport(project_dir=str(tmp_path))
        check_ui_vocabulary(report, str(tmp_path))
        ids = [f.check_id for f in report.findings]
        assert "docs.ui_dictionary" in ids

    def test_ui_vocabulary_skips_backend(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')\n")
        from core.health.models import HealthReport
        from core.health.docs_context import check_ui_vocabulary
        report = HealthReport(project_dir=str(tmp_path))
        check_ui_vocabulary(report, str(tmp_path))
        ids = [f.check_id for f in report.findings]
        assert "docs.ui_dictionary" not in ids

    def test_unknown_packages_check(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("unknown-niche-lib==0.1\n")
        from core.health.models import HealthReport
        from core.health.docs_context import check_unknown_packages
        report = HealthReport(project_dir=str(tmp_path))
        check_unknown_packages(report, str(tmp_path))
        ids = [f.check_id for f in report.findings]
        assert "docs.sdk_context" in ids
