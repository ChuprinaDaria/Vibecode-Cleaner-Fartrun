"""Tests for config loader."""

from pathlib import Path
from core.config import load_config


def test_load_default_config(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("""
[general]
refresh_interval = 10
sound_enabled = false

[alerts]
cooldown_seconds = 60
desktop_notifications = true
sound_enabled = false
quiet_hours_start = "22:00"
quiet_hours_end = "08:00"

[plugins.docker_monitor]
enabled = true
cpu_threshold = 90
ram_threshold = 90
alert_on_exit = false
""")
    cfg = load_config(cfg_file)
    assert cfg["general"]["refresh_interval"] == 10
    assert cfg["general"]["sound_enabled"] is False
    assert cfg["plugins"]["docker_monitor"]["cpu_threshold"] == 90


def test_load_config_missing_file():
    cfg = load_config(Path("/nonexistent/config.toml"))
    assert cfg["general"]["refresh_interval"] == 5
    assert cfg["alerts"]["cooldown_seconds"] == 300


def test_plugin_enabled_check(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("""
[plugins.docker_monitor]
enabled = false

[plugins.port_map]
enabled = true
""")
    cfg = load_config(cfg_file)
    assert cfg["plugins"]["docker_monitor"]["enabled"] is False
    assert cfg["plugins"]["port_map"]["enabled"] is True


def test_load_config_absolute_path(tmp_path):
    """Config resolves from project root, not relative."""
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[general]\nrefresh_interval = 10\n')
    from core.config import load_config
    config = load_config(cfg_file)
    assert config["general"]["refresh_interval"] == 10


def test_config_has_paths_section():
    """Config defaults include [paths] section."""
    from core.config import load_config
    from pathlib import Path
    config = load_config(Path("/nonexistent/config.toml"))
    assert "paths" in config
    assert config["paths"] == {}


def test_config_has_sounds_section():
    """Config defaults include [sounds] section."""
    from core.config import load_config
    from pathlib import Path
    config = load_config(Path("/nonexistent/config.toml"))
    assert "sounds" in config
    assert config["sounds"]["enabled"] is True
    assert config["sounds"]["quiet_hours_start"] == "23:00"
    assert config["sounds"]["quiet_hours_end"] == "07:00"


def test_config_env_var_override(tmp_path, monkeypatch):
    """MONITOR_CONFIG env var overrides default path."""
    cfg_file = tmp_path / "custom.toml"
    cfg_file.write_text('[general]\nrefresh_interval = 42\n')
    monkeypatch.setenv("MONITOR_CONFIG", str(cfg_file))
    from core.config import load_config
    config = load_config()
    assert config["general"]["refresh_interval"] == 42
