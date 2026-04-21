"""Smoke tests for the fartrun CLI — subcommand parsing + basic flows."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from core import cli


@pytest.fixture
def isolated(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "monitor.db"
    monkeypatch.setenv("FARTRUN_DB_PATH", str(db_path))
    monkeypatch.setenv("NO_COLOR", "1")  # deterministic output for asserts
    monkeypatch.chdir(tmp_path)

    import core.history as h
    original_init = h.HistoryDB.__init__
    def patched(self, p=str(db_path)):
        return original_init(self, p)
    monkeypatch.setattr(h.HistoryDB, "__init__", patched)
    return tmp_path


def test_no_args_prints_logo_and_help(isolated, capsys):
    rc = cli.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "fartrun" in out.lower()
    # Subcommands listed
    assert "status" in out
    assert "mcp" in out
    assert "save" in out


def test_status_on_empty_project(isolated, capsys):
    rc = cli.main(["status"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Save Points: 0" in out
    assert "Frozen files: 0" in out


def test_freeze_creates_claude_md(isolated, capsys):
    (isolated / "my.py").write_text("pass\n")
    rc = cli.main(["freeze", "my.py"])
    assert rc == 0
    assert (isolated / "CLAUDE.md").exists()
    assert "my.py" in (isolated / "CLAUDE.md").read_text()


def test_list_shows_frozen(isolated, capsys):
    cli.main(["freeze", "auth.py", "--note", "works"])
    capsys.readouterr()  # clear
    rc = cli.main(["list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "auth.py" in out
    assert "works" in out


def test_unfreeze(isolated, capsys):
    cli.main(["freeze", "auth.py"])
    capsys.readouterr()
    rc = cli.main(["unfreeze", "auth.py"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "0 frozen" in out


def test_save_outside_git_fails_gracefully(isolated, capsys):
    rc = cli.main(["save", "test"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "git" in out.lower()


def test_save_inside_git(isolated, capsys):
    subprocess.run(["git", "init"], cwd=isolated, check=True,
                     capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=isolated,
                     check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=isolated,
                     check=True)
    (isolated / "x.py").write_text("v1\n")
    subprocess.run(["git", "add", "."], cwd=isolated, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=isolated,
                     check=True, capture_output=True)
    (isolated / "x.py").write_text("v2\n")

    rc = cli.main(["save", "before refactor"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Save Point" in out
