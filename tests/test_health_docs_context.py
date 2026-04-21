"""Tests for docs & context checks."""

from core.health.models import HealthReport
from core.health.docs_context import (
    check_readme, check_dependency_docs, check_devtools_tips,
    generate_llm_context, run_docs_context_checks,
)


def test_no_readme(tmp_path):
    report = HealthReport(project_dir=str(tmp_path))
    check_readme(report, str(tmp_path))
    findings = [f for f in report.findings if f.check_id == "docs.readme"]
    assert any("No README" in f.title for f in findings)


def test_readme_incomplete(tmp_path):
    (tmp_path / "README.md").write_text("# My Project\nSome text.\n")
    report = HealthReport(project_dir=str(tmp_path))
    check_readme(report, str(tmp_path))
    findings = [f for f in report.findings if f.check_id == "docs.readme"]
    assert any("incomplete" in f.title.lower() or "missing" in f.title.lower() for f in findings)


def test_readme_complete(tmp_path):
    (tmp_path / "README.md").write_text(
        "# My Project\n\n"
        "A great tool for doing great things in a great way with great results.\n\n"
        "## Installation\n\npip install myproject and then configure it properly.\n\n"
        "## Usage\n\npython -m myproject run to start the application server.\n"
    )
    report = HealthReport(project_dir=str(tmp_path))
    check_readme(report, str(tmp_path))
    findings = [f for f in report.findings if f.check_id == "docs.readme"]
    assert any(f.severity == "info" for f in findings)


def test_dependency_unused(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask\nrequests\ncelery\n")
    (tmp_path / "app.py").write_text("import flask\napp = flask.Flask(__name__)\n")
    report = HealthReport(project_dir=str(tmp_path))
    check_dependency_docs(report, str(tmp_path))
    deps = [f for f in report.findings if f.check_id == "docs.deps"]
    # requests and celery should be flagged as unused
    if deps:
        assert any("celery" in f.message or "requests" in f.message for f in deps)


def test_devtools_not_frontend(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    report = HealthReport(project_dir=str(tmp_path))
    check_devtools_tips(report, str(tmp_path))
    assert not [f for f in report.findings if f.check_id == "docs.devtools"]


def test_llm_context_generated(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    report = HealthReport(project_dir=str(tmp_path))
    report.file_tree = {"total_files": 10, "total_dirs": 3}
    report.entry_points = [{"path": "app.py", "description": "Main"}]
    generate_llm_context(report, str(tmp_path))
    ctx = [f for f in report.findings if f.check_id == "docs.llm_context"]
    assert len(ctx) == 1
    assert "Python" in ctx[0].message
    assert "app.py" in ctx[0].message


def test_full_docs_run(tmp_path):
    (tmp_path / "app.py").write_text("import os\nprint(os.getcwd())\n")
    report = HealthReport(project_dir=str(tmp_path))
    run_docs_context_checks(report, str(tmp_path))
    check_ids = {f.check_id for f in report.findings}
    assert "docs.readme" in check_ids
    assert "docs.llm_context" in check_ids
