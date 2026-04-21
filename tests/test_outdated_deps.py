"""Tests for outdated dependencies check."""

from unittest.mock import patch, MagicMock
import json

from core.health.models import HealthReport
from core.health.outdated_deps import (
    _parse_requirements_txt, _parse_package_json,
    _is_outdated, _parse_version, run_outdated_deps_check,
)
from core.history import HistoryDB


def test_parse_requirements(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("flask==2.3.0\nrequests>=2.28.0\ncelery\n# comment\n-r base.txt\n")
    deps = _parse_requirements_txt(req)
    assert ("flask", "2.3.0") in deps
    assert ("requests", "2.28.0") in deps
    assert ("celery", "") in deps
    assert len(deps) == 3


def test_parse_package_json(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({
        "dependencies": {"react": "^18.2.0", "axios": "~1.6.0"},
        "devDependencies": {"jest": "^29.0.0"},
    }))
    deps = _parse_package_json(pkg)
    assert ("react", "18.2.0") in deps
    assert ("axios", "1.6.0") in deps
    assert ("jest", "29.0.0") in deps


def test_version_comparison():
    assert _is_outdated("2.28.0", "2.32.3") is True
    assert _is_outdated("2.32.3", "2.32.3") is False
    assert _is_outdated("3.0.0", "2.32.3") is False
    assert _is_outdated("1.0.0", "2.0.0") is True
    assert _is_outdated("", "2.0.0") is False


def test_parse_version():
    assert _parse_version("1.2.3") == (1, 2, 3)
    assert _parse_version("2.0.0") > _parse_version("1.9.9")


def test_outdated_deps_with_mock_api(tmp_path):
    """Full check with mocked API responses."""
    (tmp_path / "requirements.txt").write_text("flask==2.3.0\nrequests==2.28.0\n")

    def mock_pypi(package):
        versions = {"flask": "3.1.0", "requests": "2.32.3"}
        return versions.get(package)

    report = HealthReport(project_dir=str(tmp_path))
    db = HistoryDB(":memory:")
    db.init()

    with patch("core.health.outdated_deps._fetch_pypi_latest", side_effect=mock_pypi):
        run_outdated_deps_check(report, str(tmp_path), db=db)

    outdated = [f for f in report.findings if f.check_id == "debt.outdated_deps"]
    assert len(outdated) >= 2
    titles = [f.title for f in outdated]
    assert any("flask" in t for t in titles)
    assert any("requests" in t for t in titles)
    db.close()


def test_all_up_to_date(tmp_path):
    """No outdated deps should give info message."""
    (tmp_path / "requirements.txt").write_text("flask==3.1.0\n")

    def mock_pypi(package):
        return "3.1.0"

    report = HealthReport(project_dir=str(tmp_path))
    db = HistoryDB(":memory:")
    db.init()

    with patch("core.health.outdated_deps._fetch_pypi_latest", side_effect=mock_pypi):
        run_outdated_deps_check(report, str(tmp_path), db=db)

    findings = [f for f in report.findings if f.check_id == "debt.outdated_deps"]
    assert len(findings) == 1
    assert findings[0].severity == "info"
    db.close()


def test_cache_works(tmp_path):
    """Second call should use cache, not API."""
    (tmp_path / "requirements.txt").write_text("flask==2.3.0\n")

    call_count = 0
    def mock_pypi(package):
        nonlocal call_count
        call_count += 1
        return "3.1.0"

    db = HistoryDB(":memory:")
    db.init()

    report1 = HealthReport(project_dir=str(tmp_path))
    with patch("core.health.outdated_deps._fetch_pypi_latest", side_effect=mock_pypi):
        run_outdated_deps_check(report1, str(tmp_path), db=db)
    assert call_count == 1

    report2 = HealthReport(project_dir=str(tmp_path))
    with patch("core.health.outdated_deps._fetch_pypi_latest", side_effect=mock_pypi):
        run_outdated_deps_check(report2, str(tmp_path), db=db)
    # Should still be 1 — cached
    assert call_count == 1
    db.close()


def test_no_dep_files(tmp_path):
    """No requirements.txt or package.json — no findings."""
    report = HealthReport(project_dir=str(tmp_path))
    run_outdated_deps_check(report, str(tmp_path))
    assert not [f for f in report.findings if f.check_id == "debt.outdated_deps"]
