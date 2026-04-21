"""Tests for brake system checks."""

import subprocess

from core.health.project_map import run_all_checks
from core.health.models import HealthReport
from core.health.brake_system import (
    check_unfinished_work, check_test_health, check_scope_creep,
)


def test_unfinished_work_dirty_repo(tmp_path):
    """Dirty git repo should trigger unfinished work."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=str(tmp_path), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=str(tmp_path), capture_output=True,
    )
    (tmp_path / "app.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(tmp_path), capture_output=True,
    )
    # Make dirty
    (tmp_path / "new.py").write_text("y = 2\n")

    report = HealthReport(project_dir=str(tmp_path))
    check_unfinished_work(report, str(tmp_path))
    unfinished = [f for f in report.findings if f.check_id == "brake.unfinished"]
    assert len(unfinished) == 1
    assert "uncommitted" in unfinished[0].message


def test_unfinished_work_clean_repo(tmp_path):
    """Clean git repo should NOT trigger."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=str(tmp_path), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=str(tmp_path), capture_output=True,
    )
    (tmp_path / "app.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(tmp_path), capture_output=True,
    )

    report = HealthReport(project_dir=str(tmp_path))
    check_unfinished_work(report, str(tmp_path))
    assert not [f for f in report.findings if f.check_id == "brake.unfinished"]


def test_test_health_no_tests(tmp_path):
    """Project with no tests should get high severity."""
    (tmp_path / "app.py").write_text("x = 1\n")

    report = HealthReport(project_dir=str(tmp_path))
    check_test_health(report, str(tmp_path))
    tests = [f for f in report.findings if f.check_id == "brake.tests"]
    assert len(tests) == 1
    assert tests[0].severity == "high"


def test_test_health_has_tests(tmp_path):
    """Project with tests should get info severity."""
    (tmp_path / "app.py").write_text("x = 1\n")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text("def test_x():\n    assert True\n")

    report = HealthReport(project_dir=str(tmp_path))
    check_test_health(report, str(tmp_path))
    tests = [f for f in report.findings if f.check_id == "brake.tests"]
    assert len(tests) == 1
    assert tests[0].severity == "info"
    assert "pytest" in tests[0].message or "1 test" in tests[0].message


def test_overengineering_in_full_scan(tmp_path):
    """Full scan should include overengineering check."""
    (tmp_path / "app.py").write_text(
        "class Processor:\n    def process(self):\n        pass\n"
    )
    report = run_all_checks(str(tmp_path))
    overeng = [f for f in report.findings if f.check_id == "brake.overengineering"]
    assert any("single_method_class" in f.title for f in overeng)
