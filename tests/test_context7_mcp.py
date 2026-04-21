"""Tests for core/context7_mcp.py."""

from __future__ import annotations

import json

import pytest

from core import context7_mcp as c7


def test_install_creates_entry(tmp_path):
    path = tmp_path / "settings.json"
    assert c7.install_context7(path) is True
    data = json.loads(path.read_text())
    assert "context7" in data["mcpServers"]
    assert data["mcpServers"]["context7"]["command"] == "npx"


def test_install_idempotent(tmp_path):
    path = tmp_path / "settings.json"
    c7.install_context7(path)
    assert c7.install_context7(path) is False


def test_preserves_other_servers(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "mcpServers": {
            "other": {"command": "python", "args": ["-m", "other"]}
        },
        "keep_me": True,
    }))
    c7.install_context7(path)
    data = json.loads(path.read_text())
    assert "other" in data["mcpServers"]
    assert "context7" in data["mcpServers"]
    assert data["keep_me"] is True


def test_uninstall(tmp_path):
    path = tmp_path / "settings.json"
    c7.install_context7(path)
    assert c7.uninstall_context7(path) is True
    data = json.loads(path.read_text())
    assert "context7" not in data.get("mcpServers", {})


def test_uninstall_noop_when_missing(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{}")
    assert c7.uninstall_context7(path) is False


def test_is_installed(tmp_path):
    path = tmp_path / "settings.json"
    assert c7.is_context7_installed(path) is False
    c7.install_context7(path)
    assert c7.is_context7_installed(path) is True


def test_directive_empty():
    assert c7.build_context7_directive([]) == ""


def test_directive_truncates():
    directive = c7.build_context7_directive(["aaa", "bbb", "ccc", "ddd",
                                               "eee", "fff", "ggg"])
    assert "aaa" in directive
    # Only first 5 listed
    assert "fff" not in directive
    assert "ggg" not in directive


def test_malformed_settings_safe(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ bad json")
    assert c7.install_context7(path) is False
    assert c7.is_context7_installed(path) is False
