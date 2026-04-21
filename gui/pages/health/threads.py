"""Background QThreads owned by ``HealthPage`` — scan + Haiku explainer."""
from __future__ import annotations

import logging

from PyQt5.QtCore import QThread, pyqtSignal

from i18n import get_language

log = logging.getLogger("fartrun.health_page")


class HealthScanThread(QThread):
    """Run health scan in background thread."""
    scan_done = pyqtSignal(object)

    def __init__(self, project_dir: str, parent=None):
        super().__init__(parent)
        self._dir = project_dir

    def run(self):
        from core.health.project_map import run_all_checks
        report = run_all_checks(self._dir)
        self.scan_done.emit(report)


class HaikuHealthThread(QThread):
    """Get Haiku explanations for top findings in background."""
    done = pyqtSignal(dict, str)  # explanations dict, summary text

    def __init__(self, findings: list, config: dict, on_api_error=None, parent=None):
        super().__init__(parent)
        self._findings = findings
        self._config = dict(config or {})
        self._on_api_error = on_api_error

    def run(self):
        explanations = {}
        summary = ""
        try:
            from core.haiku_client import HaikuClient
            haiku = HaikuClient(config=self._config, on_api_error=self._on_api_error)
            if not haiku.is_available():
                self.done.emit({}, "")
                return
            lang = get_language()
            # Batch explain top 10
            top = self._findings[:10]
            items = [f"{f.title}: {f.message}" for f in top]
            explanations = haiku.batch_explain(items=items, context="code health check results", language=lang)
            # Summary
            severity_counts = {}
            for f in self._findings:
                severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
            stats = ", ".join(f"{k}: {v}" for k, v in severity_counts.items())
            lang_name = "Ukrainian" if lang == "ua" else "English"
            summary = haiku.ask(
                f"Project health scan found: {stats}. Total {len(self._findings)} issues. "
                f"Give overall assessment in 2-3 sentences. Simple words, no jargon. Respond in {lang_name}.",
                max_tokens=200
            ) or ""
        except Exception as e:
            log.warning("Haiku health summary failed, using empty summary: %s", e)
        self.done.emit(explanations, summary)
