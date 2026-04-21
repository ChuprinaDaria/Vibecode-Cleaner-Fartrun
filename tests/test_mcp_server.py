"""Tests for the MCP server tool dispatcher.

We exercise the tool implementations directly (not over stdio JSON-RPC);
the transport layer is the SDK's responsibility.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from core import mcp as mcp_server
from core.mcp import (
    _get_status, _list_save_points, _list_frozen,
    _freeze_file, _unfreeze_file, _detect_stack,
    _search_code, _rollback, _create_save_point,
    _db, _reset_db_for_tests,
)
from core.history import HistoryDB


@pytest.fixture
def fresh_cwd(tmp_path, monkeypatch):
    """Give each test an isolated tmp dir + isolated DB."""
    db_path = tmp_path / "monitor.db"
    monkeypatch.setenv("FARTRUN_DB_PATH", str(db_path))
    # Monkeypatch the default HistoryDB __init__ path
    import core.history as h
    original_init = h.HistoryDB.__init__

    def patched_init(self, db_path_arg=str(db_path)):
        return original_init(self, db_path_arg)

    monkeypatch.setattr(h.HistoryDB, "__init__", patched_init)
    monkeypatch.chdir(tmp_path)

    # Drop any cached singleton from a previous test so this one
    # opens a fresh DB at the patched path.
    from core import mcp as mcp_server
    mcp_server._reset_db_for_tests()
    yield tmp_path
    mcp_server._reset_db_for_tests()


def _text(result) -> str:
    return "\n".join(r.text for r in result)


class TestDBSingleton:
    def test_db_is_cached_within_a_session(self, fresh_cwd):
        a = _db()
        b = _db()
        assert a is b, "second _db() call should return the cached instance"

    def test_reset_drops_singleton(self, fresh_cwd):
        a = _db()
        _reset_db_for_tests()
        b = _db()
        assert a is not b, "reset should force a fresh instance"


class TestStatus:
    def test_empty_project(self, fresh_cwd):
        out = asyncio.run(_get_status({"project_dir": str(fresh_cwd)}))
        data = json.loads(_text(out))
        assert data["save_points"]["count"] == 0
        assert data["frozen_files"]["count"] == 0
        assert data["recent_prompts"] == []

    def test_includes_stack(self, fresh_cwd):
        (fresh_cwd / "package.json").write_text(json.dumps({
            "dependencies": {"react": "19.0.0"},
        }))
        out = asyncio.run(_get_status({"project_dir": str(fresh_cwd)}))
        data = json.loads(_text(out))
        assert data["stack"]["total"] >= 1
        assert "react" in data["stack"]["docs_worthy"]


class TestFrozen:
    def test_freeze_then_list(self, fresh_cwd):
        asyncio.run(_freeze_file({
            "project_dir": str(fresh_cwd),
            "path": "auth.py",
            "note": "works",
        }))
        out = asyncio.run(_list_frozen({"project_dir": str(fresh_cwd)}))
        data = json.loads(_text(out))
        assert len(data) == 1
        assert data[0]["path"] == "auth.py"
        # CLAUDE.md should now have the section
        claude_md = (fresh_cwd / "CLAUDE.md").read_text()
        assert "auth.py" in claude_md

    def test_unfreeze(self, fresh_cwd):
        asyncio.run(_freeze_file({
            "project_dir": str(fresh_cwd), "path": "x.py",
        }))
        asyncio.run(_unfreeze_file({
            "project_dir": str(fresh_cwd), "path": "x.py",
        }))
        out = asyncio.run(_list_frozen({"project_dir": str(fresh_cwd)}))
        assert json.loads(_text(out)) == []

    def test_freeze_requires_path(self, fresh_cwd):
        out = asyncio.run(_freeze_file({"project_dir": str(fresh_cwd)}))
        assert "error" in _text(out).lower()


class TestSearch:
    def test_search_returns_matches(self, fresh_cwd):
        (fresh_cwd / "src").mkdir()
        (fresh_cwd / "src" / "a.py").write_text("def login(): pass\n")
        out = asyncio.run(_search_code({
            "project_dir": str(fresh_cwd),
            "keywords": ["login"],
        }))
        data = json.loads(_text(out))
        assert any(m["path"] == "src/a.py" for m in data)


class TestStack:
    def test_parses_pyproject(self, fresh_cwd):
        (fresh_cwd / "pyproject.toml").write_text(
            "[project]\nname=\"x\"\n"
            "dependencies=[\"fastapi>=0.1\"]\n"
        )
        out = asyncio.run(_detect_stack({"project_dir": str(fresh_cwd)}))
        data = json.loads(_text(out))
        names = {lib["name"] for lib in data}
        assert "fastapi" in names


# Rollback needs a real git repo; use a git fixture
@pytest.fixture
def git_project(fresh_cwd):
    cwd = fresh_cwd
    subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=cwd, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=cwd,
                     check=True)
    (cwd / "a.py").write_text("v1\n")
    subprocess.run(["git", "add", "."], cwd=cwd, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=cwd, check=True,
                     capture_output=True)
    return cwd


class TestDestructiveRollback:
    def test_without_confirm_explains(self, git_project):
        # Make a save point and then a dirty change
        sp_out = asyncio.run(_create_save_point({
            "project_dir": str(git_project),
            "label": "baseline",
        }))
        # Re-open db to find the save-point id
        db = HistoryDB()
        db.init()
        points = db.get_save_points(str(git_project))
        sid = points[0]["id"]

        (git_project / "a.py").write_text("v2\n")

        out = asyncio.run(_rollback({
            "project_dir": str(git_project),
            "save_point_id": sid,
            # No confirm on purpose
        }))
        text = _text(out)
        assert "DESTRUCTIVE PREVIEW" in text
        # Nothing actually happened — a.py still v2
        assert (git_project / "a.py").read_text() == "v2\n"

    # The confirm=True execution path is already covered end-to-end by
    # tests/test_safety_net.py::TestSmartRollback. Keeping a separate MCP
    # integration test for it would re-open the same SQLite file across
    # tool boundaries and hit locking issues, so we trust the underlying
    # primitive and verify only the preview branch here.
