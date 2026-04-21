"""Fetch and parse Markdown resource files from GitHub or local cache."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Resource:
    title: str
    url: str
    description: str = ""


@dataclass
class Section:
    title: str
    items: list[Resource] = field(default_factory=list)


def fetch_local_md(path: Path) -> str:
    """Read MD from local file."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


# --- Line format: - [Title](url) — description ---
_ITEM_RE = re.compile(r"^-\s+\[(.+?)\]\((.+?)\)\s*[—–\-]\s*(.*)$")


def parse_resource_md(content: str) -> list[Section]:
    """Parse MD with ## sections and - [Title](url) — desc items."""
    sections: list[Section] = []
    current: Section | None = None

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("## "):
            current = Section(title=line[3:].strip())
            sections.append(current)
            continue
        if current is None:
            continue
        m = _ITEM_RE.match(line)
        if m:
            current.items.append(Resource(
                title=m.group(1).strip(),
                url=m.group(2).strip(),
                description=m.group(3).strip(),
            ))

    return sections


def parse_education_md(content: str) -> dict[str, dict[str, list[Resource]]]:
    """Parse education MD: ## Category -> ### lang -> items.

    Returns: {category: {lang: [Resource, ...]}}
    """
    result: dict[str, dict[str, list[Resource]]] = {}
    current_cat: str | None = None
    current_lang: str | None = None

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("## "):
            current_cat = line[3:].strip()
            result[current_cat] = {}
            current_lang = None
            continue
        if line.startswith("### ") and current_cat:
            current_lang = line[4:].strip()
            result[current_cat][current_lang] = []
            continue
        if current_cat and current_lang:
            m = _ITEM_RE.match(line)
            if m:
                result[current_cat][current_lang].append(Resource(
                    title=m.group(1).strip(),
                    url=m.group(2).strip(),
                    description=m.group(3).strip(),
                ))

    return result
