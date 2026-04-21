"""Detect which frameworks/libraries a project uses.

Parses standard manifest files (package.json, pyproject.toml,
requirements.txt, go.mod, Cargo.toml) and returns a list of top-level
dependencies. Used by Prompt Helper to pick which libraries to ask
Context7 about.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class DetectedLib:
    name: str                     # "react"
    version: str | None           # "^19.0.0" or "19.0.0"
    ecosystem: str                # "npm" | "pypi" | "go" | "cargo"


# Libraries we care about for Context7 (well-known, docs-heavy). Others
# are still returned but marked as less important.
DOCS_WORTHY = {
    "npm": {
        "react", "next", "vue", "svelte", "angular",
        "express", "fastify", "nestjs",
        "@shadcn/ui", "shadcn-ui", "tailwindcss", "mui", "chakra-ui",
        "prisma", "drizzle-orm", "typeorm",
        "typescript", "vite", "webpack",
    },
    "pypi": {
        "django", "fastapi", "flask", "starlette", "pydantic",
        "sqlalchemy", "alembic",
        "celery", "redis",
        "pytorch", "tensorflow", "numpy", "pandas",
        "langchain", "llamaindex", "haystack",
    },
    "go": {"gin", "echo", "fiber", "chi", "gorilla/mux"},
    "cargo": {"tokio", "actix-web", "rocket", "warp"},
}


def _parse_package_json(path: Path) -> list[DetectedLib]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    libs: list[DetectedLib] = []
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        deps = data.get(section) or {}
        if isinstance(deps, dict):
            for name, ver in deps.items():
                libs.append(DetectedLib(
                    name=name, version=str(ver) if ver else None,
                    ecosystem="npm",
                ))
    return libs


def _parse_pyproject(path: Path) -> list[DetectedLib]:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ImportError:  # Python < 3.11
        try:
            import tomli as tomllib  # type: ignore[import-not-found]
        except ImportError:
            return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    libs: list[DetectedLib] = []

    # PEP 621
    project = data.get("project") or {}
    for dep in project.get("dependencies") or []:
        name, ver = _split_pep508(dep)
        if name:
            libs.append(DetectedLib(name=name, version=ver, ecosystem="pypi"))

    # Poetry
    poetry = (data.get("tool") or {}).get("poetry") or {}
    for section in ("dependencies", "dev-dependencies"):
        deps = poetry.get(section) or {}
        if isinstance(deps, dict):
            for name, ver in deps.items():
                if name == "python":
                    continue
                version = ver if isinstance(ver, str) else (
                    ver.get("version") if isinstance(ver, dict) else None
                )
                libs.append(DetectedLib(name=name, version=version,
                                         ecosystem="pypi"))
    return libs


def _parse_requirements_txt(path: Path) -> list[DetectedLib]:
    libs: list[DetectedLib] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            name, ver = _split_pep508(line)
            if name:
                libs.append(DetectedLib(name=name, version=ver,
                                         ecosystem="pypi"))
    except OSError:
        pass
    return libs


def _split_pep508(spec: str) -> tuple[str, str | None]:
    """Split 'requests>=2.28,<3' into ('requests', '>=2.28,<3')."""
    m = re.match(r"^([A-Za-z0-9_.\-]+)\s*(.*?)\s*(?:;|$)", spec)
    if not m:
        return "", None
    name = m.group(1).lower()
    ver = m.group(2).strip() or None
    return name, ver


def _parse_go_mod(path: Path) -> list[DetectedLib]:
    libs: list[DetectedLib] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    # Simple line-based — handles both single-line and require blocks
    in_block = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue
        if line.startswith("require "):
            line = line[len("require "):]
        elif not in_block:
            continue
        parts = line.split()
        if len(parts) >= 2 and "/" in parts[0]:
            libs.append(DetectedLib(name=parts[0], version=parts[1],
                                     ecosystem="go"))
    return libs


def _parse_cargo_toml(path: Path) -> list[DetectedLib]:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[import-not-found]
        except ImportError:
            return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    libs: list[DetectedLib] = []
    for section in ("dependencies", "dev-dependencies"):
        deps = data.get(section) or {}
        if isinstance(deps, dict):
            for name, ver in deps.items():
                version = ver if isinstance(ver, str) else (
                    ver.get("version") if isinstance(ver, dict) else None
                )
                libs.append(DetectedLib(name=name, version=version,
                                         ecosystem="cargo"))
    return libs


def detect_stack(project_dir: str) -> list[DetectedLib]:
    """Return all detected dependencies across common manifests."""
    root = Path(project_dir)
    if not root.is_dir():
        return []

    libs: list[DetectedLib] = []
    if (root / "package.json").exists():
        libs += _parse_package_json(root / "package.json")
    if (root / "pyproject.toml").exists():
        libs += _parse_pyproject(root / "pyproject.toml")
    if (root / "requirements.txt").exists():
        libs += _parse_requirements_txt(root / "requirements.txt")
    if (root / "go.mod").exists():
        libs += _parse_go_mod(root / "go.mod")
    if (root / "Cargo.toml").exists():
        libs += _parse_cargo_toml(root / "Cargo.toml")
    return libs


def docs_worthy(libs: list[DetectedLib]) -> list[DetectedLib]:
    """Filter to libraries that are worth querying Context7 for."""
    out: list[DetectedLib] = []
    seen: set[tuple[str, str]] = set()
    for lib in libs:
        key = (lib.ecosystem, lib.name.lower())
        if key in seen:
            continue
        pool = DOCS_WORTHY.get(lib.ecosystem, set())
        if lib.name.lower() in pool or lib.name.lower() in {
            n.lower() for n in pool
        }:
            out.append(lib)
            seen.add(key)
    return out
