"""Group changed files into human-readable feature buckets.

Vibe coders don't know which file does what. Instead of a raw file list,
we show feature groups like "Authentication (3 files)" / "Dashboard (2 files)"
and let them tick entire features as "works" / "doesn't work".

Uses Haiku when available, falls back to directory-based grouping.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class FileChange:
    path: str
    additions: int
    deletions: int
    status: str = "modified"  # "added" | "modified" | "deleted"


@dataclass
class FeatureGroup:
    name: str                 # human-readable, e.g. "Authentication"
    description: str          # 1-line what this group is about
    files: list[str]          # paths in this group


def group_files_by_feature(
    files: list[FileChange],
    haiku_client=None,
) -> list[FeatureGroup]:
    """Split files into feature groups. Prefers Haiku, falls back to dir-based."""
    if not files:
        return []

    if haiku_client is not None and haiku_client.is_available():
        groups = _haiku_group(files, haiku_client)
        if groups:
            return groups

    return _fallback_group(files)


def _haiku_group(files: list[FileChange], haiku_client) -> list[FeatureGroup]:
    """Ask Haiku to cluster files into 2-6 feature groups."""
    file_list = "\n".join(
        f"- {f.path} (+{f.additions} / -{f.deletions})" for f in files[:60]
    )

    prompt = (
        "You are helping a non-technical developer understand what changed "
        "in their project. Group the following changed files into 2-6 "
        "feature groups with short human names (e.g. 'Authentication', "
        "'Dashboard UI', 'Styles', 'Tests'). Each file belongs to exactly "
        "one group.\n\n"
        "Return ONLY valid JSON (no prose, no markdown fences). Schema:\n"
        '[{"name": "...", "description": "...", "files": ["path1", "path2"]}]\n\n'
        f"Files:\n{file_list}"
    )

    raw = haiku_client.ask(prompt, max_tokens=800)
    if not raw:
        return []

    # Strip potential markdown fences
    clean = raw.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean, flags=re.DOTALL)

    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        log.debug("Haiku group parse failed: %s", e)
        return []

    if not isinstance(data, list):
        return []

    all_paths = {f.path for f in files}
    groups: list[FeatureGroup] = []
    claimed: set[str] = set()

    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        description = str(entry.get("description", "")).strip()
        raw_files = entry.get("files") or []
        if not name or not isinstance(raw_files, list):
            continue
        group_files = [p for p in raw_files
                       if isinstance(p, str) and p in all_paths]
        if not group_files:
            continue
        groups.append(FeatureGroup(name=name, description=description,
                                    files=group_files))
        claimed.update(group_files)

    # Anything Haiku forgot — add as "Other"
    leftover = [f.path for f in files if f.path not in claimed]
    if leftover:
        groups.append(FeatureGroup(name="Other", description="", files=leftover))

    return groups


def _fallback_group(files: list[FileChange]) -> list[FeatureGroup]:
    """Group by top-level directory. Good enough when Haiku is off."""
    buckets: dict[str, list[str]] = {}
    for f in files:
        parts = f.path.split("/")
        if len(parts) == 1:
            key = "Root files"
        else:
            key = parts[0]
        buckets.setdefault(key, []).append(f.path)

    # Prettify directory names
    groups = []
    for key, paths in sorted(buckets.items(), key=lambda x: -len(x[1])):
        pretty = key.replace("_", " ").replace("-", " ").title()
        groups.append(FeatureGroup(name=pretty, description="",
                                    files=sorted(paths)))
    return groups
