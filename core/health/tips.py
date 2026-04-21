"""Tip generation for health check results."""

from __future__ import annotations


def tip_file_tree(total_files: int, top_ext: str, top_count: int) -> str:
    return (
        f"In your project: {total_files} files. "
        f"Most common: .{top_ext} ({top_count}). "
        f"This is just context — now you know what's inside."
    )


def tip_entry_points(count: int) -> str:
    if count == 0:
        return (
            "No entry points found. "
            "An entry point is where your app starts — like a front door. "
            "Usually main.py, index.js, or a package.json script."
        )
    return (
        f"Entry point = the file where everything starts. Like doors to a building. "
        f"You have {count}."
    )


def tip_hub_module(path: str, count: int) -> str:
    return (
        f"{path} is imported by {count} files. "
        f"This is your most important module. Break it — break everything."
    )


def tip_circular(a: str, b: str) -> str:
    return (
        f"{a} imports {b}, and {b} imports {a}. "
        f"A circular dependency — can break during refactoring."
    )


def tip_orphan(path: str) -> str:
    return (
        f"{path} — nobody imports it, not an entry point. "
        f"If you need it — move to archive/. If not — delete."
    )


def tip_monster(path: str, lines: int, functions: int) -> str:
    if lines > 3000:
        tone = "This isn't a file, it's a novel."
    elif lines > 1000:
        tone = "This file needs splitting."
    else:
        tone = "Getting big."
    return (
        f"{path} — {lines} lines, {functions} functions. "
        f"{tone} One file = one responsibility."
    )


def tip_env_files(count: int) -> str:
    if count > 1:
        return (
            f"You have {count} .env files in different directories. "
            f"That's chaos. Usually one .env in root is enough."
        )
    return "One .env file — that's clean."


def tip_unused_import(name: str, path: str, line: int) -> str:
    return (
        f"{name} imported in {path}:{line} but never used. "
        f"Unused import — like buying groceries and leaving them in the trunk. "
        f"Remove it, nothing will break."
    )


def tip_unused_function(name: str, path: str) -> str:
    return (
        f"{name}() in {path} — defined but never called anywhere in the project. "
        f"Dead code. Delete or use it."
    )


def tip_unused_class(name: str, path: str) -> str:
    return (
        f"class {name} in {path} — exists but nobody uses it. Dead weight. "
        f"Delete or use it."
    )


def tip_commented_code(path: str, start: int, count: int) -> str:
    return (
        f"{count} lines of commented-out code in {path}:{start}. "
        f"That's not backup — git is your backup. Delete it."
    )


# ---------------------------------------------------------------------------
# Phase 7 — UI/UX Design Quality tips
# ---------------------------------------------------------------------------

def tip_install_node() -> str:
    return (
        "Node.js not found — it's needed for design quality checks. "
        "AI slop detection, CSS linting, accessibility — all run through npx. "
        "Install: https://nodejs.org/ (npx comes bundled). "
        "If your project has frontend files, you probably need Node anyway."
    )


def tip_impeccable(rule: str, description: str, is_slop: bool) -> str:
    if is_slop:
        return (
            f"{description} "
            f"Every LLM generates the same templates — Inter font, purple gradients, "
            f"cards inside cards. Your users can tell."
        )
    return (
        f"{description} "
        f"Design detail that affects how professional your UI looks."
    )


def tip_stylelint(errors: int, warnings: int) -> str:
    total = errors + warnings
    if errors > 10:
        return (
            f"Your CSS has {errors} errors and {warnings} warnings. "
            f"That's a mess — duplicates, deprecated properties, invalid values. "
            f"Run: npx stylelint --fix '**/*.css' to auto-fix what's fixable."
        )
    if total > 0:
        return (
            f"{errors} errors, {warnings} warnings in your CSS. "
            f"Not critical, but messy CSS becomes unmaintainable fast."
        )
    return "CSS is clean. No issues found."


def tip_lighthouse_available() -> str:
    return (
        "Lighthouse can check performance, accessibility, SEO — "
        "start your dev server and run: "
        "npx lighthouse http://localhost:3000 --output=json --chrome-flags='--headless'"
    )


def tip_pa11y_available() -> str:
    return (
        "pa11y checks WCAG accessibility — blind users, screen readers, keyboard nav. "
        "Start your dev server and run: npx pa11y http://localhost:3000 --reporter json"
    )


# QSS (Qt StyleSheet) scanner tips

def tip_qss_slop(rule_id: str, description: str, file: str, line: int) -> str:
    return (
        f"{description}. "
        f"In {file}:{line}. "
        f"AI loves generating this — your users will notice."
    )


def tip_qss_quality(rule_id: str, description: str, file: str, line: int) -> str:
    return (
        f"{description}. "
        f"In {file}:{line}. "
        f"Small detail, but adds up — polished UI wins trust."
    )


def tip_qss_summary(slop_count: int, quality_count: int) -> str:
    parts = []
    if slop_count:
        parts.append(
            f"{slop_count} AI slop pattern{'s' if slop_count != 1 else ''} — "
            f"things every LLM generates the same way"
        )
    if quality_count:
        parts.append(
            f"{quality_count} design quality issue{'s' if quality_count != 1 else ''} — "
            f"cramped padding, tiny fonts, !important abuse"
        )
    return ". ".join(parts) + "."
