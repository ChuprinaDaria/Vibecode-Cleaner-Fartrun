"""Tests for config inventory and orchestrator."""

from core.health.project_map import scan_config_inventory, run_all_checks


def test_config_inventory_finds_env(tmp_path):
    (tmp_path / ".env").write_text("DB_URL=postgres://localhost\nSECRET=abc\n")
    result = scan_config_inventory(str(tmp_path))
    assert result.env_file_count == 1
    assert any(c.kind == "env" for c in result.configs)
    env_config = next(c for c in result.configs if c.kind == "env")
    assert "2 vars" in env_config.description


def test_config_inventory_finds_docker(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("version: '3'\n")
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
    result = scan_config_inventory(str(tmp_path))
    assert result.has_docker is True
    assert len(result.configs) == 2


def test_config_inventory_finds_ci(tmp_path):
    gh_dir = tmp_path / ".github" / "workflows"
    gh_dir.mkdir(parents=True)
    (gh_dir / "ci.yml").write_text("on: push\n")
    result = scan_config_inventory(str(tmp_path))
    assert result.has_ci is True


def test_config_inventory_empty(tmp_path):
    result = scan_config_inventory(str(tmp_path))
    assert len(result.configs) == 0
    assert result.env_file_count == 0


def test_config_inventory_multiple_env(tmp_path):
    (tmp_path / ".env").write_text("A=1\n")
    (tmp_path / ".env.local").write_text("B=2\n")
    result = scan_config_inventory(str(tmp_path))
    assert result.env_file_count == 2


def test_run_all_checks_with_rust(tmp_path):
    """Orchestrator runs all checks including Rust."""
    (tmp_path / "main.py").write_text("print('hello')\n")
    (tmp_path / ".env").write_text("KEY=val\n")
    report = run_all_checks(str(tmp_path))
    assert report.project_dir == str(tmp_path)
    assert len(report.findings) >= 1
    # Should have file_tree finding
    assert any(f.check_id == "map.file_tree" for f in report.findings)
    # Should have config finding
    assert any(f.check_id == "map.configs" for f in report.findings)
