"""Tests for health check models."""

from core.health.models import (
    ConfigFile, ConfigInventoryResult,
    HealthFinding, HealthReport,
)


def test_config_file_creation():
    cf = ConfigFile(path=".env", kind="env", description="Env vars (5)", severity="warning")
    assert cf.kind == "env"
    assert cf.severity == "warning"


def test_health_finding():
    f = HealthFinding(
        check_id="map.file_tree",
        title="Project Map",
        severity="info",
        message="You have 100 files.",
    )
    assert f.check_id == "map.file_tree"
    assert f.details == {}


def test_health_report():
    r = HealthReport(project_dir="/tmp/test")
    assert r.project_dir == "/tmp/test"
    assert r.findings == []
    assert r.monsters == []
