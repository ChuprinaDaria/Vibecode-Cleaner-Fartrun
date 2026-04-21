"""Map file paths to human-readable explanations.

Uses pattern matching on file names, extensions, and directory paths.
No AI calls — pure heuristic mapping.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath


# (compiled_regex, explanation) — first match wins
_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Docker
    (re.compile(r"(^|/)docker-compose[^/]*\.ya?ml$", re.I), "Docker config — which services run"),
    (re.compile(r"(^|/)Dockerfile(\.[^/]*)?$", re.I), "Docker image — how container is built"),
    (re.compile(r"(^|/)\.dockerignore$", re.I), "Docker ignore — files excluded from build"),

    # CI/CD
    (re.compile(r"\.github/workflows/.*\.ya?ml$", re.I), "GitHub Actions CI/CD pipeline"),
    (re.compile(r"\.gitlab-ci\.ya?ml$", re.I), "GitLab CI/CD pipeline"),
    (re.compile(r"(^|/)Jenkinsfile$", re.I), "Jenkins CI/CD pipeline"),

    # Python
    (re.compile(r"(^|/)requirements.*\.txt$", re.I), "Python dependencies — what gets installed"),
    (re.compile(r"(^|/)pyproject\.toml$", re.I), "Python project config — dependencies & tools"),
    (re.compile(r"(^|/)setup\.(py|cfg)$", re.I), "Python package config"),
    (re.compile(r"(^|/)Pipfile(\.lock)?$", re.I), "Python dependencies (Pipenv)"),
    (re.compile(r"(^|/)poetry\.lock$", re.I), "Python dependency lock — exact versions pinned"),
    (re.compile(r"/migrations/.*\.py$", re.I), "DB migration — changes database structure"),
    (re.compile(r"alembic/versions/.*\.py$", re.I), "DB migration (Alembic) — changes database structure"),

    # JS/Node
    (re.compile(r"(^|/)package\.json$", re.I), "Node.js/JS project config — dependencies & scripts"),
    (re.compile(r"(^|/)package-lock\.json$", re.I), "JS dependency lock — exact versions pinned"),
    (re.compile(r"(^|/)yarn\.lock$", re.I), "JS dependency lock (Yarn) — exact versions pinned"),
    (re.compile(r"(^|/)pnpm-lock\.yaml$", re.I), "JS dependency lock (pnpm) — exact versions pinned"),
    (re.compile(r"(^|/)tsconfig.*\.json$", re.I), "TypeScript config"),
    (re.compile(r"(^|/)webpack\.config\.", re.I), "Webpack bundler config"),
    (re.compile(r"(^|/)vite\.config\.", re.I), "Vite bundler config"),

    # Environment & secrets
    (re.compile(r"(^|/)\.env\.example$", re.I), "Env template — example config (no real secrets)"),
    (re.compile(r"(^|/)\.env(\.[^/]*)?$", re.I), "Environment variables — secrets, keys, settings"),

    # Git
    (re.compile(r"(^|/)\.gitignore$", re.I), "Git ignore — files excluded from version control"),
    (re.compile(r"(^|/)\.gitattributes$", re.I), "Git attributes — line endings, diff settings"),

    # Build & automation
    (re.compile(r"(^|/)Makefile$", re.I), "Makefile — build/automation commands"),
    (re.compile(r"(^|/)Procfile$", re.I), "Procfile — how app runs in production"),

    # Config
    (re.compile(r"(^|/)nginx.*\.conf$", re.I), "Nginx web server config"),
    (re.compile(r"(^|/)\.eslintrc", re.I), "ESLint config — JS code style rules"),
    (re.compile(r"(^|/)\.prettierrc", re.I), "Prettier config — code formatting rules"),
    (re.compile(r"(^|/)CLAUDE\.md$", re.I), "Claude Code instructions — AI assistant config"),

    # Terraform / IaC
    (re.compile(r"\.tf$", re.I), "Terraform — infrastructure as code"),
    (re.compile(r"(^|/)terraform\.tfvars", re.I), "Terraform variables"),

    # Kubernetes
    (re.compile(r"(^|/)k8s/.*\.ya?ml$", re.I), "Kubernetes config"),
    (re.compile(r"(^|/)helm/.*\.ya?ml$", re.I), "Helm chart — Kubernetes package config"),
]

# Extension-based fallback (less specific)
_EXT_MAP: dict[str, str] = {
    ".py": "Python source code",
    ".js": "JavaScript source code",
    ".ts": "TypeScript source code",
    ".jsx": "React component (JSX)",
    ".tsx": "React component (TypeScript)",
    ".vue": "Vue.js component",
    ".svelte": "Svelte component",
    ".html": "HTML page",
    ".css": "Stylesheet",
    ".scss": "SASS stylesheet",
    ".sql": "SQL query/script",
    ".sh": "Shell script",
    ".bash": "Bash script",
    ".ps1": "PowerShell script",
    ".bat": "Windows batch script",
    ".cmd": "Windows command script",
    ".md": "Documentation (Markdown)",
    ".rst": "Documentation (reStructuredText)",
    ".json": "JSON data/config",
    ".yaml": "YAML config",
    ".yml": "YAML config",
    ".toml": "TOML config",
    ".ini": "INI config",
    ".cfg": "Config file",
    ".xml": "XML data/config",
    ".go": "Go source code",
    ".rs": "Rust source code",
    ".java": "Java source code",
    ".kt": "Kotlin source code",
    ".rb": "Ruby source code",
    ".php": "PHP source code",
    ".c": "C source code",
    ".cpp": "C++ source code",
    ".h": "C/C++ header file",
    ".cs": "C# source code",
    ".swift": "Swift source code",
    ".r": "R script",
    ".dart": "Dart source code",
    ".lua": "Lua script",
    ".ex": "Elixir source code",
    ".erl": "Erlang source code",
}


def explain_file(path: str) -> str:
    """Return human-readable explanation for a file path.

    Checks specific patterns first, then falls back to extension mapping.
    Always returns a non-empty string.
    """
    # Normalise separators (Windows backslashes → forward slashes)
    normalised = path.replace("\\", "/")

    # Try specific patterns first
    for pattern, explanation in _PATTERNS:
        if pattern.search(normalised):
            return explanation

    # Extension fallback
    suffix = PurePosixPath(normalised).suffix.lower()
    if suffix in _EXT_MAP:
        return _EXT_MAP[suffix]

    # Last resort
    return "Project file"
