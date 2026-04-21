"""Background QThreads owned by ``MonitorApp``."""
from __future__ import annotations

import logging

from PyQt5.QtCore import QThread, pyqtSignal

log = logging.getLogger(__name__)


class DataCollectorThread(QThread):
    """Collect Docker + Ports data in background to avoid blocking GUI."""
    data_ready = pyqtSignal(dict)

    def __init__(self, docker_client, parent=None):
        super().__init__(parent)
        self._docker_client = docker_client

    def run(self):
        result = {"docker": [], "ports": []}

        if self._docker_client:
            try:
                from plugins.docker_monitor.collector import collect_containers
                containers = self._docker_client.containers.list(all=True)
                result["docker"] = collect_containers(containers)
            except Exception as e:
                log.error("Docker collect error: %s", e)

        try:
            from plugins.port_map.collector import collect_ports
            result["ports"] = collect_ports()
        except Exception as e:
            log.error("Ports collect error: %s", e)

        self.data_ready.emit(result)


class StatusCheckThread(QThread):
    """Wrap a single ``StatusChecker.check_now()`` call in a thread."""
    done = pyqtSignal(object)

    def __init__(self, checker, parent=None):
        super().__init__(parent)
        self._checker = checker

    def run(self):
        self.done.emit(self._checker.check_now())
