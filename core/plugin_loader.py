"""Minimal plugin registry — bridges async Plugin(ABC) contract to sync callers.

For v1 only `test_runner` is wired here. Adding docker_monitor / port_map /
security_scan to `_IMPORTS` migrates them off the direct-import path in
gui/app/threads.py — that's a follow-up, not part of Task 17.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from pathlib import Path

from core.plugin import Alert, Plugin

log = logging.getLogger("fartrun.plugin_loader")

_IMPORTS: dict[str, str] = {
    "test_runner": "plugins.test_runner.plugin.TestRunnerPlugin",
}


class PluginRegistry:
    def __init__(self, config: dict, db_path: Path):
        self._config = config
        self._db_path = db_path
        self._plugins: list[Plugin] = self._load_enabled()

    def _load_enabled(self) -> list[Plugin]:
        enabled = self._config.get("plugins", {}) or {}
        out: list[Plugin] = []
        for key, dotted in _IMPORTS.items():
            if not enabled.get(key):
                continue
            module_path, _, cls_name = dotted.rpartition(".")
            try:
                module = importlib.import_module(module_path)
                cls = getattr(module, cls_name)
                out.append(cls(config=self._config))
            except Exception as e:
                log.warning("Failed to load plugin %s: %s", key, e)
        return out

    def start(self) -> None:
        """Run migrate() for every loaded plugin once at startup."""
        asyncio.run(self._migrate_all())

    async def _migrate_all(self) -> None:
        # Real db connection plumbing isn't needed for v1 plugins (test_runner
        # ignores the db arg). When wiring more plugins, open an aiosqlite
        # connection here and pass it in.
        for p in self._plugins:
            try:
                await p.migrate(db=None)
            except Exception as e:
                log.warning("Plugin %s migrate failed: %s", type(p).__name__, e)

    def collect_all(self) -> list[Alert]:
        """Run collect() then get_alerts() for every plugin. Returns aggregated alerts."""
        return asyncio.run(self._collect_and_alert())

    async def _collect_and_alert(self) -> list[Alert]:
        alerts: list[Alert] = []
        for p in self._plugins:
            try:
                await p.collect(db=None)
            except Exception as e:
                log.warning("Plugin %s collect failed: %s", type(p).__name__, e)
            try:
                got = await p.get_alerts(db=None)
                alerts.extend(got)
            except Exception as e:
                log.warning("Plugin %s get_alerts failed: %s", type(p).__name__, e)
        return alerts
