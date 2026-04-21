"""Tests for core/prompt_parser.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.prompt_parser import (
    UserPrompt, project_slug, get_recent_prompts, _extract_text,
    format_prompts_for_haiku,
)


class TestSlug:
    def test_basic(self, tmp_path):
        assert project_slug(str(tmp_path)) == "-" + str(tmp_path).replace("/", "-").lstrip("-")


class TestExtractText:
    def test_plain_string(self):
        assert _extract_text("hello") == "hello"

    def test_list_with_text(self):
        content = [{"type": "text", "text": "do the thing"}]
        assert _extract_text(content) == "do the thing"

    def test_tool_result_returns_empty(self):
        content = [{"type": "tool_result", "content": "output"}]
        assert _extract_text(content) == ""

    def test_mixed_tool_result_drops_whole_message(self):
        """If tool_result appears, even alongside text, it's still a tool message."""
        content = [
            {"type": "tool_result", "content": "output"},
            {"type": "text", "text": "ignored"},
        ]
        assert _extract_text(content) == ""

    def test_empty_list(self):
        assert _extract_text([]) == ""

    def test_multiple_text_parts_joined(self):
        content = [
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ]
        assert _extract_text(content) == "first\nsecond"


@pytest.fixture
def fake_claude_dir(tmp_path):
    """Build a fake ~/.claude/projects/<slug>/*.jsonl tree."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    slug = project_slug(str(project_dir))
    sessions = tmp_path / "claude" / "projects" / slug
    sessions.mkdir(parents=True)
    return tmp_path / "claude", project_dir, sessions


class TestGetRecentPrompts:
    def test_extracts_prompts_newest_first(self, fake_claude_dir):
        claude_dir, project_dir, sessions = fake_claude_dir
        jsonl = sessions / "s1.jsonl"
        lines = [
            {"type": "user", "timestamp": "2026-04-10T10:00:00Z",
             "message": {"content": "old prompt"}},
            {"type": "user", "timestamp": "2026-04-10T11:00:00Z",
             "message": {"content": "new prompt"}},
            {"type": "assistant", "timestamp": "2026-04-10T10:30:00Z",
             "message": {"content": "reply", "usage": {}}},
        ]
        jsonl.write_text("\n".join(json.dumps(l) for l in lines))

        prompts = get_recent_prompts(str(project_dir), str(claude_dir))
        assert len(prompts) == 2
        assert prompts[0].text == "new prompt"
        assert prompts[1].text == "old prompt"

    def test_skips_tool_results(self, fake_claude_dir):
        claude_dir, project_dir, sessions = fake_claude_dir
        jsonl = sessions / "s1.jsonl"
        lines = [
            {"type": "user", "timestamp": "1",
             "message": {"content": "real"}},
            {"type": "user", "timestamp": "2",
             "message": {"content": [{"type": "tool_result",
                                       "content": "output"}]}},
        ]
        jsonl.write_text("\n".join(json.dumps(l) for l in lines))

        prompts = get_recent_prompts(str(project_dir), str(claude_dir))
        assert len(prompts) == 1
        assert prompts[0].text == "real"

    def test_empty_when_no_sessions(self, tmp_path):
        prompts = get_recent_prompts(str(tmp_path), str(tmp_path / "nowhere"))
        assert prompts == []

    def test_limits_output(self, fake_claude_dir):
        claude_dir, project_dir, sessions = fake_claude_dir
        jsonl = sessions / "s1.jsonl"
        lines = [
            {"type": "user", "timestamp": f"2026-04-10T10:{i:02d}:00Z",
             "message": {"content": f"prompt {i}"}}
            for i in range(30)
        ]
        jsonl.write_text("\n".join(json.dumps(l) for l in lines))

        prompts = get_recent_prompts(str(project_dir), str(claude_dir),
                                      limit=5)
        assert len(prompts) == 5

    def test_merges_multiple_sessions(self, fake_claude_dir):
        claude_dir, project_dir, sessions = fake_claude_dir
        (sessions / "a.jsonl").write_text(json.dumps({
            "type": "user", "timestamp": "2026-04-10T10:00:00Z",
            "message": {"content": "from session A"}}))
        (sessions / "b.jsonl").write_text(json.dumps({
            "type": "user", "timestamp": "2026-04-11T10:00:00Z",
            "message": {"content": "from session B"}}))

        prompts = get_recent_prompts(str(project_dir), str(claude_dir))
        texts = [p.text for p in prompts]
        assert "from session A" in texts
        assert "from session B" in texts
        # Newer one first
        assert prompts[0].text == "from session B"

    def test_survives_malformed_lines(self, fake_claude_dir):
        claude_dir, project_dir, sessions = fake_claude_dir
        jsonl = sessions / "s.jsonl"
        jsonl.write_text(
            "not json\n"
            + json.dumps({"type": "user", "timestamp": "t1",
                          "message": {"content": "good"}}) + "\n"
            + "{garbage\n"
        )
        prompts = get_recent_prompts(str(project_dir), str(claude_dir))
        assert len(prompts) == 1
        assert prompts[0].text == "good"


class TestShortRepr:
    def test_truncates_long(self):
        p = UserPrompt(timestamp="t", session_id="s", text="a" * 500)
        assert p.short.endswith("…")
        assert len(p.short) <= 181

    def test_collapses_whitespace(self):
        p = UserPrompt(timestamp="t", session_id="s",
                       text="line1\n\n   line2\t\ttab")
        assert "\n" not in p.short
        assert "  " not in p.short


class TestHaikuFormat:
    def test_oldest_first(self):
        prompts = [
            UserPrompt(timestamp="2026-04-10T12:00:00Z", session_id="s",
                       text="second"),
            UserPrompt(timestamp="2026-04-10T10:00:00Z", session_id="s",
                       text="first"),
        ]
        out = format_prompts_for_haiku(prompts)
        lines = out.splitlines()
        assert "first" in lines[0]
        assert "second" in lines[1]
