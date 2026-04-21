"""
Claude Code session parser.
Reads all JSONL logs from ~/.claude/projects/ and extracts session data.
"""

import json
from pathlib import Path
from collections import defaultdict


def get_project_name(path: Path) -> str:
    """Extract project name from folder path."""
    # e.g. -home-dchuprina-sloth-all -> sloth-all
    parts = path.parent.name.split("-")
    return "-".join(parts[3:]) if len(parts) > 3 else path.parent.name


def parse_session(records: list) -> dict | None:
    """Parse a list of records belonging to one session into a summary."""
    if not records:
        return None

    session_id = records[0].get("sessionId")
    timestamp = records[0].get("timestamp")
    project = records[0].get("_project", "unknown")

    model = None
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_creation_tokens = 0
    duration_ms = None
    first_user_message = None
    skills_used = []
    assistant_turns = 0

    for r in records:
        t = r.get("type")

        if t == "user" and first_user_message is None:
            msg = r.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        first_user_message = block.get("text", "")[:500]
                        break
            elif isinstance(content, str):
                first_user_message = content[:500]

            # шукаємо /skill команди
            if first_user_message:
                for word in first_user_message.split():
                    if word.startswith("/") and len(word) > 1:
                        skills_used.append(word)

        elif t == "assistant":
            assistant_turns += 1
            msg = r.get("message", {})
            if not model:
                model = msg.get("model")
            usage = msg.get("usage", {})
            input_tokens += usage.get("input_tokens", 0)
            output_tokens += usage.get("output_tokens", 0)
            cache_read_tokens += usage.get("cache_read_input_tokens", 0)
            cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)

        elif t == "system":
            if r.get("durationMs"):
                duration_ms = r.get("durationMs")

    if not model:
        return None

    return {
        "session_id": session_id,
        "project": project,
        "timestamp": timestamp,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "total_tokens": input_tokens + output_tokens,
        "duration_ms": duration_ms,
        "assistant_turns": assistant_turns,
        "first_user_message": first_user_message,
        "skills_used": skills_used,
        "outcome": None,  # заповнюється юзером при виході
    }


def parse_all_sessions() -> list[dict]:
    """Parse all JSONL files from all Claude Code projects."""
    projects_dir = Path.home() / ".claude" / "projects"
    sessions_raw = defaultdict(list)

    for jsonl_file in projects_dir.glob("**/*.jsonl"):
        # пропускаємо subagents — це внутрішні сесії агентів
        if "subagents" in str(jsonl_file):
            continue

        project_name = get_project_name(jsonl_file)

        with open(jsonl_file, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    session_id = record.get("sessionId")
                    if session_id:
                        record["_project"] = project_name
                        sessions_raw[session_id].append(record)
                except json.JSONDecodeError:
                    continue

    sessions = []
    for session_id, records in sessions_raw.items():
        # сортуємо по timestamp
        records.sort(key=lambda r: r.get("timestamp", ""))
        session = parse_session(records)
        if session:
            sessions.append(session)

    sessions.sort(key=lambda s: s.get("timestamp") or "")
    return sessions


if __name__ == "__main__":
    sessions = parse_all_sessions()
    print(f"Found {len(sessions)} sessions\n")
    for s in sessions[-5:]:  # останні 5
        print(f"[{s['timestamp'][:19]}] {s['project']}")
        print(f"  model: {s['model']}, tokens: {s['total_tokens']}")
        print(f"  task: {(s['first_user_message'] or '')[:80]}")
        print()