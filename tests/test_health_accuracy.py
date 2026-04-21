"""Accuracy tests for health scanner — false positive regression suite."""

from pathlib import Path
from core.health.project_map import run_all_checks


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "health_accuracy"


def _findings_by_check(report, check_id):
    return [f for f in report.findings if f.check_id == check_id]


def _finding_titles(report, check_id):
    return [f.title for f in _findings_by_check(report, check_id)]


class TestTypeCheckingImports:
    """Bug 2: imports under `if TYPE_CHECKING:` must not be flagged unused."""

    def test_type_checking_import_not_flagged(self, tmp_path):
        """Copy fixture to tmp_path and scan — User should not appear in unused imports."""
        import shutil
        src = FIXTURES_DIR / "type_checking_imports"
        dst = tmp_path / "project"
        shutil.copytree(src, dst)

        report = run_all_checks(str(dst))
        unused = _finding_titles(report, "dead.unused_imports")
        assert not any("User" in t for t in unused), (
            f"TYPE_CHECKING import 'User' should not be flagged unused. Got: {unused}"
        )

    def test_real_unused_still_caught(self, tmp_path):
        """Ensure TYPE_CHECKING fix doesn't suppress real unused imports."""
        (tmp_path / "app.py").write_text(
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "import json\n"  # truly unused
            "\nif TYPE_CHECKING:\n"
            "    from os import PathLike\n"  # TYPE_CHECKING — not unused
            "\nx = 1\n"
        )
        report = run_all_checks(str(tmp_path))
        unused = _finding_titles(report, "dead.unused_imports")
        assert any("json" in t for t in unused), (
            f"Truly unused 'json' should still be flagged. Got: {unused}"
        )
        assert not any("PathLike" in t for t in unused), (
            f"TYPE_CHECKING import 'PathLike' should not be flagged. Got: {unused}"
        )


class TestSingleMethodClass:
    """Bug 4: QThread/QDialog subclasses with __init__+run should not be flagged."""

    def test_qthread_subclass_not_flagged(self, tmp_path):
        (tmp_path / "threads.py").write_text(
            "from PyQt5.QtCore import QThread, pyqtSignal\n\n"
            "class WorkerThread(QThread):\n"
            "    done = pyqtSignal(object)\n\n"
            "    def __init__(self, parent=None):\n"
            "        super().__init__(parent)\n\n"
            "    def run(self):\n"
            "        self.done.emit(42)\n"
        )
        import health as h
        result = h.scan_overengineering(str(tmp_path))
        flagged = [i.description for i in result.issues if i.kind == "single_method_class"]
        assert not any("WorkerThread" in d for d in flagged), (
            f"QThread subclass should not be flagged. Got: {flagged}"
        )

    def test_real_single_method_still_caught(self, tmp_path):
        (tmp_path / "utils.py").write_text(
            "class Wrapper:\n"
            "    def do_thing(self):\n"
            "        return 42\n"
        )
        import health as h
        result = h.scan_overengineering(str(tmp_path))
        flagged = [i.description for i in result.issues if i.kind == "single_method_class"]
        assert any("Wrapper" in d for d in flagged), (
            f"Real single-method class should be flagged. Got: {flagged}"
        )


class TestHubCounting:
    """Bug 1: hub counting must show real number of importers."""

    def test_hub_module_count(self, tmp_path):
        """5 files import core/models.py — hub count must be 5."""
        import shutil
        src = FIXTURES_DIR / "hub_counting"
        dst = tmp_path / "project"
        shutil.copytree(src, dst)

        import health as h
        result = h.scan_module_map(str(dst), [])
        hub_dict = {path: count for path, count in result.hub_modules}
        models_count = hub_dict.get("core/models.py", 0)
        assert models_count == 5, (
            f"core/models.py should have 5 importers, got {models_count}. "
            f"Hub modules: {result.hub_modules}"
        )


class TestOrphanReexports:
    """Bug 3: files re-exported via __init__.py must not be flagged orphan."""

    def test_init_reexport_not_orphan(self, tmp_path):
        import shutil
        src = FIXTURES_DIR / "init_reexports"
        dst = tmp_path / "project"
        shutil.copytree(src, dst)

        import health as h
        result = h.scan_module_map(str(dst), [])
        orphans = result.orphan_candidates
        assert "pkg/submodule.py" not in orphans, (
            f"pkg/submodule.py re-exported via __init__.py should not be orphan. "
            f"Orphans: {orphans}"
        )
        assert "pkg/internal.py" not in orphans, (
            f"pkg/internal.py re-exported via __init__.py should not be orphan. "
            f"Orphans: {orphans}"
        )


class TestCommentedCode:
    """Bug 5: doc comments / prose must not be flagged as commented-out code."""

    def test_prose_comments_not_flagged(self, tmp_path):
        """English prose comments should not be flagged as commented code."""
        (tmp_path / "app.py").write_text(
            "x = 1\n"
            "# The confirm=True execution path is already covered end-to-end by\n"
            "# tests/test_safety_net.py::TestSmartRollback. Keeping a separate MCP\n"
            "# integration test for it would re-open the same SQLite file across\n"
            "# tool boundaries and hit locking issues, so we trust the underlying\n"
            "# primitive and verify only the preview branch here.\n"
            "y = 2\n"
        )
        report = run_all_checks(str(tmp_path))
        commented = _findings_by_check(report, "dead.commented_code")
        assert len(commented) == 0, (
            f"Prose comments should not be flagged as code. Got: {commented}"
        )

    def test_real_commented_code_still_caught(self, tmp_path):
        """Actually commented-out code should still be caught."""
        (tmp_path / "app.py").write_text(
            "x = 1\n"
            "# def old_function():\n"
            "#     x = 1\n"
            "#     y = 2\n"
            "#     z = x + y\n"
            "#     return z\n"
            "y = 2\n"
        )
        report = run_all_checks(str(tmp_path))
        commented = _findings_by_check(report, "dead.commented_code")
        assert len(commented) > 0, (
            "Real commented-out code should be flagged"
        )


class TestTestFileCounting:
    """Bug 7: test file counting should exclude fixture directories."""

    def test_fixture_test_files_excluded(self, tmp_path):
        """Test files inside fixtures/ should not be counted as project tests."""
        # Real test file
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").write_text("def test_one(): pass\n")
        (tests_dir / "test_utils.py").write_text("def test_two(): pass\n")

        # Fixture test file (should be excluded)
        fixtures_dir = tests_dir / "fixtures" / "sample_project" / "tests"
        fixtures_dir.mkdir(parents=True)
        (fixtures_dir / "test_dummy.py").write_text("def test_dummy(): pass\n")

        # Need pyproject.toml for framework detection
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")

        report = run_all_checks(str(tmp_path))
        test_findings = [f for f in report.findings if f.check_id == "brake.tests"]
        assert len(test_findings) == 1
        # Should count 2 test files, NOT 3
        assert "2 test files" in test_findings[0].message, (
            f"Should count 2 test files (excluding fixture). Got: {test_findings[0].message}"
        )


class TestJsxImports:
    """Bug 1: JSX import resolution must work — components must not be orphans."""

    def test_jsx_imports_resolved(self, tmp_path):
        """App.jsx imports Home.jsx imports Header.jsx — none should be orphans."""
        import shutil
        src = FIXTURES_DIR / "jsx_imports"
        dst = tmp_path / "project"
        shutil.copytree(src, dst)

        import health as h
        result = h.scan_module_map(str(dst), [])
        orphans = result.orphan_candidates
        assert "src/components/Header.jsx" not in orphans, (
            f"Header.jsx is imported by Home.jsx, should not be orphan. Orphans: {orphans}"
        )
        assert "src/pages/Home.jsx" not in orphans, (
            f"Home.jsx is imported by App.jsx, should not be orphan. Orphans: {orphans}"
        )

    def test_jsx_hub_counting(self, tmp_path):
        """Imports from JSX files must be counted in hub modules."""
        import shutil
        src = FIXTURES_DIR / "jsx_imports"
        dst = tmp_path / "project"
        shutil.copytree(src, dst)

        import health as h
        result = h.scan_module_map(str(dst), [])
        # Header.jsx is imported by Home.jsx → imported_by >= 1
        modules_dict = {m.path: m.imported_by_count for m in result.modules}
        header_count = modules_dict.get("src/components/Header.jsx", 0)
        assert header_count >= 1, (
            f"Header.jsx should have >= 1 importer, got {header_count}. Modules: {modules_dict}"
        )


class TestOrphanWhitelist:
    """Bugs 7+8: config files and Django conventional files must not be orphans."""

    def test_config_files_not_orphan(self, tmp_path):
        """vite.config.js and similar build configs should not be orphans."""
        (tmp_path / "vite.config.js").write_text("export default { plugins: [] };\n")
        (tmp_path / "tailwind.config.js").write_text("module.exports = {};\n")
        (tmp_path / "postcss.config.js").write_text("module.exports = {};\n")
        (tmp_path / "eslint.config.mjs").write_text("export default [];\n")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.js").write_text("console.log('hi');\n")

        import health as h
        result = h.scan_module_map(str(tmp_path), [])
        orphans = result.orphan_candidates
        assert "vite.config.js" not in orphans, f"vite.config.js should not be orphan. {orphans}"
        assert "tailwind.config.js" not in orphans, f"tailwind.config.js should not be orphan. {orphans}"
        assert "postcss.config.js" not in orphans, f"postcss.config.js should not be orphan. {orphans}"
        assert "eslint.config.mjs" not in orphans, f"eslint.config.mjs should not be orphan. {orphans}"

    def test_django_conventional_files_not_orphan(self, tmp_path):
        """Django auto-discovered files should not be orphans."""
        app = tmp_path / "myapp"
        app.mkdir()
        (app / "__init__.py").write_text("")
        (app / "admin.py").write_text("from django.contrib import admin\n")
        (app / "apps.py").write_text("from django.apps import AppConfig\nclass MyConfig(AppConfig): pass\n")
        (app / "urls.py").write_text("urlpatterns = []\n")
        (app / "models.py").write_text("class Foo: pass\n")
        (tmp_path / "settings.py").write_text("INSTALLED_APPS = []\n")
        (app / "tasks.py").write_text("# celery tasks\n")
        (app / "signals.py").write_text("from django.dispatch import receiver\n")
        (app / "receivers.py").write_text("# signal receivers\n")

        import health as h
        result = h.scan_module_map(str(tmp_path), [])
        orphans = result.orphan_candidates
        assert "myapp/admin.py" not in orphans, f"admin.py should not be orphan. {orphans}"
        assert "myapp/apps.py" not in orphans, f"apps.py should not be orphan. {orphans}"
        assert "myapp/urls.py" not in orphans, f"urls.py should not be orphan. {orphans}"
        assert "settings.py" not in orphans, f"settings.py should not be orphan. {orphans}"
        assert "myapp/tasks.py" not in orphans, f"tasks.py should not be orphan. {orphans}"
        assert "myapp/signals.py" not in orphans, f"signals.py should not be orphan. {orphans}"
        assert "myapp/receivers.py" not in orphans, f"receivers.py should not be orphan. {orphans}"


class TestDjangoDeadCodeWhitelist:
    """Bugs 2-5: Django/DRF framework patterns must not be flagged as dead code."""

    def test_meta_inner_class_not_flagged(self, tmp_path):
        """Django Meta inner classes should not be flagged as unused."""
        (tmp_path / "models.py").write_text(
            "class Article:\n"
            "    class Meta:\n"
            "        ordering = ['-created']\n"
            "        verbose_name = 'Article'\n"
            "\n"
            "    def __str__(self):\n"
            "        return 'article'\n"
        )
        (tmp_path / "serializers.py").write_text(
            "class ArticleSerializer:\n"
            "    class Meta:\n"
            "        model = 'Article'\n"
            "        fields = '__all__'\n"
        )
        report = run_all_checks(str(tmp_path))
        unused = _finding_titles(report, "dead.unused_definitions")
        meta_flags = [t for t in unused if "Meta" in t]
        assert not meta_flags, f"Meta inner classes should not be flagged. Got: {meta_flags}"

    def test_admin_hooks_not_flagged(self, tmp_path):
        """Django admin hooks should not be flagged as unused methods."""
        (tmp_path / "admin.py").write_text(
            "class ArticleAdmin:\n"
            "    def has_add_permission(self, request):\n"
            "        return False\n"
            "\n"
            "    def has_delete_permission(self, request, obj=None):\n"
            "        return False\n"
            "\n"
            "    def save_model(self, request, obj, form, change):\n"
            "        obj.save()\n"
            "\n"
            "    def get_readonly_fields(self, request, obj=None):\n"
            "        return []\n"
        )
        report = run_all_checks(str(tmp_path))
        unused = _finding_titles(report, "dead.unused_definitions")
        admin_flags = [t for t in unused if any(hook in t for hook in [
            "has_add_permission", "has_delete_permission", "save_model", "get_readonly_fields"
        ])]
        assert not admin_flags, f"Admin hooks should not be flagged. Got: {admin_flags}"

    def test_drf_validators_not_flagged(self, tmp_path):
        """DRF validate_<field> and Django clean_<field> should not be flagged."""
        (tmp_path / "serializers.py").write_text(
            "class ContactSerializer:\n"
            "    def validate_email(self, value):\n"
            "        return value\n"
            "\n"
            "    def validate_consent(self, value):\n"
            "        if not value:\n"
            "            raise ValueError('Required')\n"
            "        return value\n"
        )
        (tmp_path / "forms.py").write_text(
            "class ContactForm:\n"
            "    def clean_email(self, value):\n"
            "        return value\n"
        )
        report = run_all_checks(str(tmp_path))
        unused = _finding_titles(report, "dead.unused_definitions")
        validator_flags = [t for t in unused if "validate_" in t or "clean_" in t]
        assert not validator_flags, f"Validators should not be flagged. Got: {validator_flags}"

    def test_appconfig_not_flagged(self, tmp_path):
        """Django AppConfig subclasses in apps.py should not be flagged."""
        (tmp_path / "apps.py").write_text(
            "from django.apps import AppConfig\n"
            "\n"
            "class WebsiteConfig(AppConfig):\n"
            "    name = 'website'\n"
        )
        report = run_all_checks(str(tmp_path))
        unused = _finding_titles(report, "dead.unused_definitions")
        config_flags = [t for t in unused if "Config" in t]
        assert not config_flags, f"AppConfig should not be flagged. Got: {config_flags}"


class TestDjangoModelSingleMethod:
    """Bug 6: Django Model subclasses should not be flagged as single-method."""

    def test_django_model_not_flagged(self, tmp_path):
        (tmp_path / "models.py").write_text(
            "from django.db import models\n\n"
            "class Article(models.Model):\n"
            "    title = models.CharField(max_length=200)\n\n"
            "    def __str__(self):\n"
            "        return self.title\n"
        )
        import health as h
        result = h.scan_overengineering(str(tmp_path))
        flagged = [i.description for i in result.issues if i.kind == "single_method_class"]
        assert not any("Article" in d for d in flagged), (
            f"Django Model subclass should not be flagged. Got: {flagged}"
        )

    def test_django_form_not_flagged(self, tmp_path):
        (tmp_path / "forms.py").write_text(
            "from django import forms\n\n"
            "class ContactForm(forms.Form):\n"
            "    def clean(self):\n"
            "        return self.cleaned_data\n"
        )
        import health as h
        result = h.scan_overengineering(str(tmp_path))
        flagged = [i.description for i in result.issues if i.kind == "single_method_class"]
        assert not any("ContactForm" in d for d in flagged), (
            f"Django Form subclass should not be flagged. Got: {flagged}"
        )
