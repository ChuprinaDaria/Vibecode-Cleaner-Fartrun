"""Turn a vibe-coder's messy one-liner into a structured prompt.

Pipeline:
  1. Detect language (UA vs EN).
  2. Ask Haiku for tech keywords + clean English intent.
  3. Run a dumb keyword search over the project.
  4. Detect the stack (package.json etc.) + pick docs-worthy libraries.
  5. Pull frozen files so we can tell Claude to preserve them.
  6. Ask Haiku to synthesise a final prompt in the user's language,
     embedding file hits + a ``use context7`` directive for the libs.

No Haiku? We still return a fallback prompt so the feature degrades
gracefully instead of showing an empty box.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.code_searcher import CodeMatch, search_codebase
from core.context7_mcp import build_context7_directive
from core.lang_detect import detect_lang
from core.stack_detector import DetectedLib, detect_stack, docs_worthy

log = logging.getLogger(__name__)

_MAX_KEYWORDS = 7
_MAX_MATCHES_IN_PROMPT = 8


@dataclass
class PromptBuildResult:
    final_prompt: str
    language: str
    keywords: list[str] = field(default_factory=list)
    intent: str = ""
    matches: list[CodeMatch] = field(default_factory=list)
    stack: list[DetectedLib] = field(default_factory=list)
    context7_libs: list[str] = field(default_factory=list)
    used_ai: bool = False


# ---------------------------------------------------------------- Haiku #1

def _translate_to_keywords(
    user_text: str, language: str, haiku_client,
) -> tuple[list[str], str]:
    """Ask Haiku for search keywords + clean English intent."""
    if haiku_client is None or not haiku_client.is_available():
        return _fallback_keywords(user_text), user_text

    prompt = (
        "You are translating a non-technical developer's request into "
        "search terms for their own codebase.\n\n"
        f"User said ({language}): \"{user_text}\"\n\n"
        "Return ONLY valid JSON with this schema:\n"
        '{"keywords": ["lowercase english words likely to appear in code, '
        'max 7"], "intent": "one sentence in English describing what they '
        'want"}\n'
        "Use words a programmer would actually name variables/functions "
        "after (e.g. 'button', 'label', 'render', 'click', 'onClick'). "
        "No prose outside the JSON."
    )
    raw = haiku_client.ask(prompt, max_tokens=300)
    if not raw:
        return _fallback_keywords(user_text), user_text

    clean = raw.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean, flags=re.DOTALL)

    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        return _fallback_keywords(user_text), user_text

    keywords = data.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = []
    keywords = [str(k).strip().lower() for k in keywords if k][:_MAX_KEYWORDS]
    intent = str(data.get("intent") or user_text).strip()
    return keywords, intent


def _fallback_keywords(text: str) -> list[str]:
    """Heuristic: pull decent-looking words when we can't call Haiku."""
    # Anything longer than 2 chars, alnum, lowercased
    words = re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text)
    return [w.lower() for w in words][:_MAX_KEYWORDS]


# ---------------------------------------------------------------- Haiku #2

def _synthesize_prompt(
    user_text: str,
    intent: str,
    language: str,
    matches: list[CodeMatch],
    stack: list[DetectedLib],
    context7_libs: list[str],
    frozen_paths: list[str],
    haiku_client,
) -> tuple[str, bool]:
    """Return (final_prompt, used_ai)."""
    hits_block = "\n".join(
        f"- {m.path}:{m.line_number}  {m.snippet}"
        for m in matches[:_MAX_MATCHES_IN_PROMPT]
    ) or "(no code matches found)"

    frozen_block = "\n".join(f"- {p}" for p in frozen_paths) or "(none)"

    stack_block = "\n".join(
        f"- {lib.name}" + (f" ({lib.version})" if lib.version else "")
        for lib in stack[:10]
    ) or "(unknown)"

    context7_directive = build_context7_directive(context7_libs)

    if haiku_client is None or not haiku_client.is_available():
        return _fallback_synth(
            user_text, intent, language, hits_block, stack_block,
            frozen_block, context7_directive,
        ), False

    instruction = (
        "You are writing a clear, well-structured prompt that a "
        "non-technical developer will paste into Claude Code. The "
        "developer's own words were vague, so we added the project "
        "context below. Keep the final prompt concise (under 200 words).\n"
        "Rules:\n"
        f"- Write the final prompt in {'Ukrainian' if language == 'uk' else 'English'}.\n"
        "- Start with a one-line goal.\n"
        "- Point Claude at the concrete files/lines we found.\n"
        "- Include the Context7 directive verbatim if present.\n"
        "- Tell Claude not to touch the frozen files.\n"
        "- No markdown code fences, no preamble.\n\n"
        f"Developer said: \"{user_text}\"\n"
        f"Parsed intent (EN): {intent}\n\n"
        f"Likely places in code:\n{hits_block}\n\n"
        f"Project stack:\n{stack_block}\n\n"
        f"Frozen files (must not change):\n{frozen_block}\n\n"
        f"Context7 directive: {context7_directive or '(none)'}\n\n"
        "Output only the final prompt."
    )

    result = haiku_client.ask(instruction, max_tokens=700)
    if not result:
        return _fallback_synth(
            user_text, intent, language, hits_block, stack_block,
            frozen_block, context7_directive,
        ), False
    return result.strip(), True


def _fallback_synth(user_text, intent, language, hits_block, stack_block,
                    frozen_block, context7_directive) -> str:
    """Template-based prompt when Haiku isn't available."""
    if language == "uk":
        return (
            f"Задача: {user_text}\n\n"
            f"Зрозуміла мета: {intent}\n\n"
            f"Ймовірні місця в коді:\n{hits_block}\n\n"
            f"Стек проєкту:\n{stack_block}\n\n"
            f"Заморожені файли (НЕ чіпати):\n{frozen_block}\n\n"
            f"{context7_directive}"
        ).strip()
    return (
        f"Task: {user_text}\n\n"
        f"Parsed intent: {intent}\n\n"
        f"Likely places in code:\n{hits_block}\n\n"
        f"Project stack:\n{stack_block}\n\n"
        f"Frozen files (do NOT modify):\n{frozen_block}\n\n"
        f"{context7_directive}"
    ).strip()


# ---------------------------------------------------------------- Public API

def build_prompt(
    user_text: str,
    project_dir: str,
    frozen_paths: list[str] | None = None,
    haiku_client=None,
    language: str | None = None,
) -> PromptBuildResult:
    """Run the full pipeline. Works without Haiku (degraded)."""
    frozen_paths = frozen_paths or []
    language = language or detect_lang(user_text)

    keywords, intent = _translate_to_keywords(user_text, language, haiku_client)
    matches = search_codebase(project_dir, keywords) if keywords else []

    stack = detect_stack(project_dir)
    worthy = docs_worthy(stack)
    context7_libs = [lib.name for lib in worthy]

    final_prompt, used_ai = _synthesize_prompt(
        user_text=user_text,
        intent=intent,
        language=language,
        matches=matches,
        stack=stack,
        context7_libs=context7_libs,
        frozen_paths=frozen_paths,
        haiku_client=haiku_client,
    )

    return PromptBuildResult(
        final_prompt=final_prompt,
        language=language,
        keywords=keywords,
        intent=intent,
        matches=matches,
        stack=stack,
        context7_libs=context7_libs,
        used_ai=used_ai,
    )
