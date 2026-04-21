"""Simple keyword search across a project's source files.

No vector DB, no embeddings, no rerank — just grep-style substring search
with a skip list for junk directories. Uses ripgrep when available,
falls back to pure Python.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".next", ".nuxt", "target", ".idea", ".vscode", ".cache",
}

# Source file extensions we actually want to grep through. Keeps results
# relevant and skips binaries/lockfiles/minified bundles.
SOURCE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
    ".go", ".rs", ".java", ".kt", ".swift", ".rb", ".php",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".sh", ".bash",
    ".html", ".css", ".scss", ".sass", ".less",
    ".md", ".rst", ".yml", ".yaml", ".toml",
}


@dataclass
class CodeMatch:
    path: str          # relative to project root, POSIX style
    line_number: int
    snippet: str       # the matching line, stripped
    keyword: str


def _iter_source_files(project_dir: str, max_files: int = 2000):
    root = Path(project_dir)
    count = 0
    for p in root.rglob("*"):
        if count >= max_files:
            break
        if not p.is_file():
            continue
        # Skip junk dirs anywhere in the path
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        if p.suffix.lower() not in SOURCE_EXTS:
            continue
        yield p
        count += 1


def _python_search(project_dir: str, keywords: list[str],
                   max_per_keyword: int) -> list[CodeMatch]:
    """Pure-Python fallback."""
    root = Path(project_dir)
    per_kw: dict[str, list[CodeMatch]] = {kw: [] for kw in keywords}
    lowered = [(kw, kw.lower()) for kw in keywords]

    for fp in _iter_source_files(project_dir):
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        try:
            rel = fp.relative_to(root).as_posix()
        except ValueError:
            rel = str(fp)

        for lineno, line in enumerate(text.splitlines(), start=1):
            low = line.lower()
            for kw, lkw in lowered:
                if len(per_kw[kw]) >= max_per_keyword:
                    continue
                if lkw in low:
                    per_kw[kw].append(CodeMatch(
                        path=rel, line_number=lineno,
                        snippet=line.strip()[:200], keyword=kw,
                    ))
                    break  # one hit per line is enough

    # Flatten, dedupe by (path, line_number)
    seen: set[tuple[str, int]] = set()
    out: list[CodeMatch] = []
    for kw in keywords:
        for m in per_kw[kw]:
            key = (m.path, m.line_number)
            if key in seen:
                continue
            seen.add(key)
            out.append(m)
    return out


def _ripgrep_search(project_dir: str, keywords: list[str],
                    max_per_keyword: int) -> list[CodeMatch] | None:
    """Fast path via ripgrep. Returns None if rg not available or fails."""
    rg = shutil.which("rg")
    if not rg:
        return None

    out: list[CodeMatch] = []
    seen: set[tuple[str, int]] = set()
    root = Path(project_dir)

    for kw in keywords:
        if not kw.strip():
            continue
        args = [
            rg, "--json", "--max-count", str(max_per_keyword),
            "--ignore-case", "--fixed-strings",
            "--max-columns", "240",
        ]
        for d in SKIP_DIRS:
            args.extend(["--glob", f"!{d}/**"])
        args.append(kw)
        args.append(str(root))

        try:
            proc = subprocess.run(args, capture_output=True, text=True,
                                  timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            return None

        for line in proc.stdout.splitlines():
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if evt.get("type") != "match":
                continue
            data = evt.get("data", {})
            path = data.get("path", {}).get("text", "")
            try:
                rel = Path(path).relative_to(root).as_posix()
            except ValueError:
                rel = path
            lineno = data.get("line_number", 0)
            snippet = (data.get("lines", {}).get("text", "") or "").strip()[:200]
            key = (rel, lineno)
            if key in seen:
                continue
            seen.add(key)
            out.append(CodeMatch(path=rel, line_number=lineno,
                                  snippet=snippet, keyword=kw))

    return out


def search_codebase(
    project_dir: str,
    keywords: list[str],
    max_per_keyword: int = 5,
) -> list[CodeMatch]:
    """Search project source for keywords. Returns deduped list of matches."""
    keywords = [k for k in keywords if k and k.strip()]
    if not keywords or not Path(project_dir).is_dir():
        return []

    rg_hits = _ripgrep_search(project_dir, keywords, max_per_keyword)
    if rg_hits is not None:
        return rg_hits

    return _python_search(project_dir, keywords, max_per_keyword)
