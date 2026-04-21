"""Tests for the frozen_check hook — must block frozen files, allow others."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.history import HistoryDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_hook(payload: dict, env_db: Path) -> subprocess.CompletedProcess:
    """Invoke the hook as a subprocess with stdin JSON."""
    env = {
        "HOME": str(env_db.parent),  # HistoryDB uses ~/.config/... fallback
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(PROJECT_ROOT),
        "FARTRUN_DB_PATH": str(env_db),
    }
    return subprocess.run(
        [sys.executable, "-m", "core.hooks.frozen_check"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )


class TestHookLogic:
    """Test the hook's in-process logic directly (fast, no subprocess)."""

    def test_extract_paths_edit(self):
        from core.hooks.frozen_check import _extract_paths
        assert _extract_paths("Edit", {"file_path": "auth.py"}) == ["auth.py"]

    def test_extract_paths_write(self):
        from core.hooks.frozen_check import _extract_paths
        assert _extract_paths("Write", {"file_path": "new.py"}) == ["new.py"]

    def test_extract_paths_unknown_tool(self):
        from core.hooks.frozen_check import _extract_paths
        assert _extract_paths("Bash", {"command": "ls"}) == []

    def test_extract_paths_no_file_path(self):
        from core.hooks.frozen_check import _extract_paths
        assert _extract_paths("Edit", {}) == []

    def test_project_paths_relative_and_absolute(self, tmp_path):
        from core.hooks.frozen_check import _project_paths
        target_abs = tmp_path / "src" / "auth.py"
        target_abs.parent.mkdir(parents=True)
        target_abs.write_text("")

        got = _project_paths(str(tmp_path), str(target_abs))
        assert "src/auth.py" in got
        assert str(target_abs) in got

    def test_main_blocks_frozen(self, tmp_path, monkeypatch):
        """Hook should exit 2 when editing a frozen file."""
        db_path = tmp_path / "monitor.db"
        db = HistoryDB(str(db_path))
        db.init()
        db.add_frozen_file(str(tmp_path), "auth.py", note="works")

        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "auth.py"},
            "cwd": str(tmp_path),
        }
        monkeypatch.setattr(sys, "stdin", _StringIO(json.dumps(payload)))
        monkeypatch.setenv("FARTRUN_DB_PATH", str(db_path))

        from core.hooks.frozen_check import main
        assert main() == 2

    def test_main_allows_non_frozen(self, tmp_path, monkeypatch):
        db_path = tmp_path / "monitor.db"
        db = HistoryDB(str(db_path))
        db.init()
        db.add_frozen_file(str(tmp_path), "auth.py")

        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "dashboard.py"},
            "cwd": str(tmp_path),
        }
        monkeypatch.setattr(sys, "stdin", _StringIO(json.dumps(payload)))
        monkeypatch.setenv("FARTRUN_DB_PATH", str(db_path))

        from core.hooks.frozen_check import main
        assert main() == 0

    def test_main_allows_non_edit_tools(self, monkeypatch):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "cwd": "/tmp",
        }
        monkeypatch.setattr(sys, "stdin", _StringIO(json.dumps(payload)))
        from core.hooks.frozen_check import main
        assert main() == 0

    def test_main_survives_garbage_stdin(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", _StringIO("not json at all"))
        from core.hooks.frozen_check import main
        assert main() == 0


class _StringIO:
    """Tiny wrapper because sys.stdin needs .read() to feed json.load."""
    def __init__(self, text: str):
        self._text = text

    def read(self, *args):
        return self._text


