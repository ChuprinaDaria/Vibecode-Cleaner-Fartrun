"""SDK Context Fetcher — fetch docs for unknown packages, generate PROJECT_CONTEXT.md.

Helps vibe coders when AI doesn't know a new/niche SDK.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# Max size for fetched docs (50KB)
_MAX_DOC_SIZE = 50_000


@dataclass
class ContextDoc:
    path: str
    title: str
    size: int
    url: str


@dataclass
class UnknownPackage:
    name: str
    version: str
    registry: str       # "pypi" or "npm"
    reason: str         # why it's flagged


# Well-known packages that every model knows — skip these
_WELL_KNOWN_PYTHON = {
    "django", "flask", "fastapi", "requests", "numpy", "pandas", "sqlalchemy",
    "celery", "pytest", "pydantic", "redis", "boto3", "pillow", "scipy",
    "matplotlib", "seaborn", "scikit-learn", "sklearn", "tensorflow", "torch",
    "pytorch", "keras", "transformers", "openai", "anthropic", "langchain",
    "alembic", "gunicorn", "uvicorn", "httpx", "aiohttp", "beautifulsoup4",
    "bs4", "lxml", "jinja2", "mako", "click", "typer", "rich", "pyyaml",
    "toml", "python-dotenv", "dotenv", "cryptography", "paramiko",
    "psycopg2", "psycopg", "pymongo", "motor", "aiomysql", "mysqlclient",
    "docker", "fabric", "invoke", "tox", "black", "isort", "flake8",
    "mypy", "pylint", "ruff", "coverage", "hypothesis", "faker",
    "marshmallow", "attrs", "dataclasses-json", "orjson", "ujson",
    "sentry-sdk", "prometheus-client", "loguru", "structlog",
    "python-telegram-bot", "aiogram", "discord-py", "slack-sdk",
    "scrapy", "selenium", "playwright", "pyppeteer",
    "drf-spectacular", "django-rest-framework", "djangorestframework",
    "django-cors-headers", "django-filter", "django-debug-toolbar",
    "whitenoise", "django-storages", "django-celery-beat",
    "starlette", "tortoise-orm", "peewee", "sqlmodel",
    "networkx", "sympy", "opencv-python", "cv2",
    "arrow", "pendulum", "python-dateutil",
    "tqdm", "colorama", "tabulate",
    "qdrant-client", "pinecone-client", "chromadb", "weaviate-client",
    "cohere", "replicate", "together",
    "gradio", "streamlit", "dash", "plotly",
    "pyqt5", "pyside6", "tkinter", "wx",
}

_WELL_KNOWN_JS = {
    "react", "react-dom", "next", "vue", "nuxt", "angular", "svelte",
    "express", "koa", "fastify", "hapi", "nestjs",
    "typescript", "webpack", "vite", "rollup", "esbuild", "parcel",
    "tailwindcss", "bootstrap", "material-ui", "mui", "chakra-ui",
    "styled-components", "emotion", "sass", "less", "postcss",
    "axios", "node-fetch", "got", "superagent",
    "lodash", "underscore", "ramda", "moment", "dayjs", "date-fns",
    "mongoose", "sequelize", "prisma", "typeorm", "knex", "drizzle-orm",
    "redux", "mobx", "zustand", "jotai", "recoil", "pinia", "vuex",
    "jest", "mocha", "chai", "vitest", "cypress", "playwright",
    "eslint", "prettier", "husky", "lint-staged",
    "socket-io", "ws", "graphql", "apollo-server", "apollo-client",
    "jsonwebtoken", "passport", "bcrypt", "bcryptjs",
    "dotenv", "cors", "helmet", "morgan", "winston", "pino",
    "pm2", "nodemon", "concurrently", "cross-env",
    "storybook", "chromatic",
    "three", "d3", "chart-js", "recharts",
    "framer-motion", "gsap", "lottie",
    "electron", "react-native", "expo",
    "firebase", "supabase", "aws-sdk",
    "openai", "anthropic", "langchain",
    "zod", "yup", "joi", "class-validator",
    "trpc", "tanstack-query", "react-query", "swr",
    "react-router", "react-router-dom", "wouter",
    "next-auth", "clerk",
    "sharp", "jimp", "multer",
    "bull", "bullmq", "agenda",
    "redis", "ioredis",
    "pg", "mysql2", "better-sqlite3",
    "shadcn-ui", "radix-ui", "headless-ui",
}


def _strip_html(html: str) -> str:
    """Strip HTML tags and extract readable text. No dependencies."""
    # Remove script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"')
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class ContextFetcher:
    def __init__(self, project_dir: str):
        self._dir = project_dir

    def fetch_url(self, url: str) -> ContextDoc | None:
        """Fetch URL, extract text, save to docs/context/ folder."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "claude-monitor/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read(_MAX_DOC_SIZE + 1000).decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError, ValueError) as e:
            log.warning("Failed to fetch %s: %s", url, e)
            return None

        # Extract text
        if "html" in content_type.lower() or raw.strip().startswith("<"):
            text = _strip_html(raw)
        else:
            text = raw  # assume markdown/plain

        # Truncate
        if len(text) > _MAX_DOC_SIZE:
            text = text[:_MAX_DOC_SIZE] + "\n\n... (truncated)"

        # Extract title
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", raw, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else url.split("/")[-1]

        # Save to docs/context/
        context_dir = Path(self._dir) / "docs" / "context"
        context_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from URL
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", url.split("//")[-1])[:80].strip("-")
        filename = f"{slug}.md"
        filepath = context_dir / filename

        filepath.write_text(f"# {title}\n\nSource: {url}\n\n{text}\n")

        return ContextDoc(
            path=str(filepath),
            title=title,
            size=len(text),
            url=url,
        )

    def detect_unknown_packages(self) -> list[UnknownPackage]:
        """Find packages that AI probably doesn't know."""
        unknown = []

        # Python: requirements.txt
        req_file = Path(self._dir) / "requirements.txt"
        if req_file.exists():
            unknown.extend(self._check_python_deps(req_file))

        # Also pyproject.toml
        pyproject = Path(self._dir) / "pyproject.toml"
        if pyproject.exists():
            unknown.extend(self._check_pyproject(pyproject))

        # JS: package.json
        pkg_json = Path(self._dir) / "package.json"
        if pkg_json.exists():
            unknown.extend(self._check_js_deps(pkg_json))

        # Deduplicate
        seen = set()
        result = []
        for pkg in unknown:
            if pkg.name not in seen:
                seen.add(pkg.name)
                result.append(pkg)

        return result

    def _check_python_deps(self, req_file: Path) -> list[UnknownPackage]:
        unknown = []
        try:
            for line in req_file.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                parts = re.split(r"[=<>!~\[]", line)
                name = parts[0].strip().lower().replace("-", "_")
                version = parts[1].strip() if len(parts) > 1 else ""
                if name and name not in _WELL_KNOWN_PYTHON:
                    unknown.append(UnknownPackage(
                        name=name, version=version,
                        registry="pypi",
                        reason="not in common packages list",
                    ))
        except OSError:
            pass
        return unknown

    def _check_pyproject(self, pyproject: Path) -> list[UnknownPackage]:
        unknown = []
        try:
            content = pyproject.read_text(errors="replace")
            # Simple TOML parsing for dependencies section
            in_deps = False
            for line in content.splitlines():
                if re.match(r"\[.*dependencies.*\]", line, re.IGNORECASE):
                    in_deps = True
                    continue
                if in_deps and line.startswith("["):
                    in_deps = False
                    continue
                if in_deps:
                    match = re.match(r'["\']?([a-zA-Z0-9_-]+)["\']?\s*[>=<]', line)
                    if not match:
                        match = re.match(r'([a-zA-Z0-9_-]+)\s*=', line)
                    if match:
                        name = match.group(1).lower().replace("-", "_")
                        if name and name not in _WELL_KNOWN_PYTHON:
                            unknown.append(UnknownPackage(
                                name=name, version="",
                                registry="pypi",
                                reason="not in common packages list",
                            ))
        except OSError:
            pass
        return unknown

    def _check_js_deps(self, pkg_json: Path) -> list[UnknownPackage]:
        unknown = []
        try:
            data = json.loads(pkg_json.read_text(errors="replace"))
            for section in ("dependencies", "devDependencies"):
                deps = data.get(section, {})
                for name, version in deps.items():
                    normalized = name.lower().replace("@", "").replace("/", "-")
                    if normalized not in _WELL_KNOWN_JS and name not in _WELL_KNOWN_JS:
                        unknown.append(UnknownPackage(
                            name=name, version=version,
                            registry="npm",
                            reason="not in common packages list",
                        ))
        except (OSError, json.JSONDecodeError):
            pass
        return unknown

    def generate_context_file(self, report=None) -> str:
        """Generate PROJECT_CONTEXT.md for pasting into AI chat."""
        root = Path(self._dir)
        parts = [f"# Project: {root.name}", ""]

        # Stack detection
        stack = []
        from core.health import has_files_with_ext
        if has_files_with_ext(root, "py"):
            stack.append("Python")
            if (root / "manage.py").exists():
                stack.append("Django")
        if has_files_with_ext(root, "js") or has_files_with_ext(root, "ts"):
            stack.append("JavaScript/TypeScript")
            if has_files_with_ext(root, "jsx") or has_files_with_ext(root, "tsx"):
                stack.append("React")
            if has_files_with_ext(root, "vue"):
                stack.append("Vue")
        if (root / "docker-compose.yml").exists() or (root / "docker-compose.yaml").exists():
            stack.append("Docker")
        if stack:
            parts.append(f"**Stack:** {', '.join(stack)}")
            parts.append("")

        # Use report data if available
        if report:
            if report.file_tree:
                ft = report.file_tree
                parts.append(f"**Size:** {ft.get('total_files', '?')} files, "
                             f"{ft.get('total_dirs', '?')} dirs")
                parts.append("")

            if report.entry_points:
                parts.append("**Entry points:**")
                for ep in report.entry_points[:5]:
                    parts.append(f"- `{ep['path']}` — {ep['description']}")
                parts.append("")

            if report.module_map and report.module_map.get("hub_modules"):
                parts.append("**Key modules:**")
                for path, count in report.module_map["hub_modules"][:5]:
                    parts.append(f"- `{path}` (imported by {count} files)")
                parts.append("")

        # Include fetched docs summaries
        context_dir = root / "docs" / "context"
        if context_dir.is_dir():
            docs = list(context_dir.glob("*.md"))
            if docs:
                parts.append("**Fetched SDK docs:**")
                for doc in docs[:10]:
                    parts.append(f"- `{doc.name}` ({doc.stat().st_size // 1024}KB)")
                parts.append("")

        # Unknown packages
        unknown = self.detect_unknown_packages()
        if unknown:
            parts.append("**Packages AI might not know:**")
            for pkg in unknown[:10]:
                parts.append(f"- {pkg.name} ({pkg.registry})")
            parts.append("")

        context_text = "\n".join(parts)

        # Save
        output = root / "PROJECT_CONTEXT.md"
        output.write_text(context_text)

        return str(output)
