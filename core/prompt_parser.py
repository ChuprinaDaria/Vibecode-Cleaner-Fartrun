"""Parse Claude Code JSONL sessions to extract actual user prompts.

Claude Code stores every session under ``~/.claude/projects/<slug>/<id>.jsonl``
where the slug is derived from the project directory (``/`` replaced with
``-`` and prefixed with ``-``). Each line is an event; we only care about
genuine user prompts (not tool results, which also carry ``type: user``).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from glob import glob
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class UserPrompt:
    timestamp: str   # ISO string from the JSONL line
    session_id: str
    text: str

    @property
    def short(self) -> str:
        """First 180 chars, one line."""
        t = " ".join(self.text.split())
        return t[:180] + ("…" if len(t) > 180 else "")


def project_slug(project_dir: str) -> str:
    """Convert a project path to the Claude Code directory slug.

    ``/home/dchuprina/claude-monitor`` → ``-home-dchuprina-claude-monitor``
    """
    p = str(Path(project_dir).resolve())
    return "-" + p.replace(os.sep, "-").lstrip("-")


def _default_claude_dir() -> str:
    return os.path.expanduser("~/.claude")


def _extract_text(content) -> str:
    """Pull the user-typed text out of a message.content value.

    Returns '' for tool results or anything that isn't a real prompt.
    """
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    # If ANY part is a tool_result, treat whole message as tool result
    parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "tool_result":
            return ""
        if part.get("type") == "text":
            txt = part.get("text", "")
            if isinstance(txt, str) and txt.strip():
                parts.append(txt.strip())
    return "\n".join(parts)


def _session_prompts(jsonl_path: str) -> list[UserPrompt]:
    session_id = Path(jsonl_path).stem
    prompts: list[UserPrompt] = []
    try:
        with open(jsonl_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "user":
                    continue
                msg = entry.get("message") or {}
                if not isinstance(msg, dict):
                    continue
                text = _extract_text(msg.get("content"))
                if not text:
                    continue
                ts = entry.get("timestamp") or ""
                prompts.append(UserPrompt(
                    timestamp=str(ts), session_id=session_id, text=text,
                ))
    except OSError as e:
        log.debug("Can't read %s: %s", jsonl_path, e)
    return prompts


def get_recent_prompts(
    project_dir: str,
    claude_dir: str | None = None,
    limit: int = 20,
) -> list[UserPrompt]:
    """Return the latest user prompts for a project, newest first."""
    claude_dir = claude_dir or _default_claude_dir()
    slug = project_slug(project_dir)
    session_dir = Path(claude_dir) / "projects" / slug
    if not session_dir.is_dir():
        return []

    all_prompts: list[UserPrompt] = []
    for jsonl_path in glob(str(session_dir / "*.jsonl")):
        all_prompts.extend(_session_prompts(jsonl_path))

    # Newest first (JSONL timestamps are ISO so lexicographic sort works)
    all_prompts.sort(key=lambda p: p.timestamp, reverse=True)
    return all_prompts[:limit]


def format_prompts_for_haiku(prompts: list[UserPrompt]) -> str:
    """Compact representation of a prompt list for a Haiku summary."""
    lines = []
    for p in reversed(prompts):  # oldest first — so summary reads chronologically
        t = p.timestamp[:16].replace("T", " ") if p.timestamp else "?"
        lines.append(f"[{t}] {p.short}")
    return "\n".join(lines)
