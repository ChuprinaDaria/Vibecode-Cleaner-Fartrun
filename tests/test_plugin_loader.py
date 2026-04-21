"""Tests for PluginRegistry."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.plugin import Alert
from core.plugin_loader import PluginRegistry


def test_loads_only_enabled_plugins(tmp_path):
    config = {"plugins": {"test_runner": True}}
    reg = PluginRegistry(config=config, db_path=tmp_path / "x.db")
    assert len(reg._plugins) == 1
    assert type(reg._plugins[0]).__name__ == "TestRunnerPlugin"


def test_disabled_plugin_not_loaded(tmp_path):
    config = {"plugins": {"test_runner": False}}
    reg = PluginRegistry(config=config, db_path=tmp_path / "x.db")
    assert reg._plugins == []


def test_unknown_key_ignored(tmp_path):
    config = {"plugins": {"definitely_not_a_plugin": True}}
    reg = PluginRegistry(config=config, db_path=tmp_path / "x.db")
    assert reg._plugins == []


def test_start_calls_migrate_on_each_plugin(tmp_path):
    config = {"plugins": {"test_runner": True}}
    reg = PluginRegistry(config=config, db_path=tmp_path / "x.db")
    plugin = reg._plugins[0]
    plugin.migrate = AsyncMock()
    reg.start()
    plugin.migrate.assert_awaited_once()


def test_collect_all_aggregates_alerts(tmp_path):
    config = {"plugins": {"test_runner": True}}
    reg = PluginRegistry(config=config, db_path=tmp_path / "x.db")
    plugin = reg._plugins[0]
    plugin.collect = AsyncMock()
    plugin.get_alerts = AsyncMock(return_value=[
        Alert(source="tests", severity="warning", title="t", message="m"),
    ])
    alerts = reg.collect_all()
    assert len(alerts) == 1
    assert alerts[0].title == "t"


def test_failing_plugin_does_not_break_others(tmp_path, caplog):
    """A plugin that raises in get_alerts must not propagate; others run."""
    config = {"plugins": {"test_runner": True}}
    reg = PluginRegistry(config=config, db_path=tmp_path / "x.db")
    bad = reg._plugins[0]
    bad.collect = AsyncMock()
    bad.get_alerts = AsyncMock(side_effect=RuntimeError("boom"))
    alerts = reg.collect_all()
    assert alerts == []
    assert any("boom" in r.message for r in caplog.records)
