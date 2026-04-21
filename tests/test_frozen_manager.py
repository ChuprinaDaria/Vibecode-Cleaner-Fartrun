"""Tests for core/frozen_manager.py — CLAUDE.md sync + hook installer."""

from __future__ import annotations

import json

import pytest

from core import frozen_manager as fm


class TestClaudeMdSync:
    def test_writes_section_when_absent(self, tmp_path):
        changed = fm.sync_claude_md(str(tmp_path), ["auth.py", "config.py"])
        assert changed is True
        content = (tmp_path / "CLAUDE.md").read_text()
        assert fm.CLAUDE_MD_MARKER_START in content
        assert fm.CLAUDE_MD_MARKER_END in content
        assert "auth.py" in content
        assert "config.py" in content

    def test_preserves_existing_content(self, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# My Project\n\nSome notes.\n")
        fm.sync_claude_md(str(tmp_path), ["auth.py"])
        content = claude_md.read_text()
        assert "# My Project" in content
        assert "Some notes." in content
        assert "auth.py" in content

    def test_replaces_managed_section(self, tmp_path):
        fm.sync_claude_md(str(tmp_path), ["old.py"])
        fm.sync_claude_md(str(tmp_path), ["new.py"])
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "old.py" not in content
        assert "new.py" in content
        # Marker appears exactly once
        assert content.count(fm.CLAUDE_MD_MARKER_START) == 1

    def test_empty_list_shows_hint(self, tmp_path):
        fm.sync_claude_md(str(tmp_path), [])
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "No frozen files yet" in content

    def test_idempotent(self, tmp_path):
        fm.sync_claude_md(str(tmp_path), ["a.py"])
        changed = fm.sync_claude_md(str(tmp_path), ["a.py"])
        assert changed is False


class TestHookInstaller:
    def test_install_creates_settings(self, tmp_path):
        settings = tmp_path / "settings.json"
        assert fm.install_hook(settings) is True
        data = json.loads(settings.read_text())
        assert "hooks" in data
        pre = data["hooks"]["PreToolUse"]
        assert len(pre) == 1
        assert pre[0]["_id"] == fm.HOOK_MATCHER_ID

    def test_install_idempotent(self, tmp_path):
        settings = tmp_path / "settings.json"
        fm.install_hook(settings)
        assert fm.install_hook(settings) is False

    def test_install_preserves_other_hooks(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps({
            "hooks": {
                "PreToolUse": [{"_id": "other", "matcher": "Bash",
                                "hooks": [{"type": "command",
                                           "command": "echo hi"}]}],
                "PostToolUse": [{"matcher": "Edit",
                                 "hooks": [{"type": "command",
                                            "command": "echo done"}]}],
            },
            "other_key": "keep me",
        }))

        fm.install_hook(settings)
        data = json.loads(settings.read_text())
        ids = {h.get("_id") for h in data["hooks"]["PreToolUse"]}
        assert {"other", fm.HOOK_MATCHER_ID} <= ids
        assert len(data["hooks"]["PostToolUse"]) == 1
        assert data["other_key"] == "keep me"

    def test_uninstall(self, tmp_path):
        settings = tmp_path / "settings.json"
        fm.install_hook(settings)
        assert fm.uninstall_hook(settings) is True
        data = json.loads(settings.read_text())
        ids = {h.get("_id") for h in data["hooks"]["PreToolUse"]}
        assert fm.HOOK_MATCHER_ID not in ids

    def test_uninstall_when_not_installed(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text("{}")
        assert fm.uninstall_hook(settings) is False

    def test_is_installed(self, tmp_path):
        settings = tmp_path / "settings.json"
        assert fm.is_hook_installed(settings) is False
        fm.install_hook(settings)
        assert fm.is_hook_installed(settings) is True

    def test_malformed_settings_safe(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text("{ not valid json")
        # Should not crash, just return False
        assert fm.install_hook(settings) is False
        assert fm.is_hook_installed(settings) is False
