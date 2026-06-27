"""Shared text utilities for dramaturgy workshop turns."""

from __future__ import annotations

import re

from app.core.config import settings

_LIMIT_COMPLAINT_RE = re.compile(
    r"(?:450|zeichen.?grenze|zeichenlimit|widersetze|hebe.*grenze|braucht mehr raum)",
    re.IGNORECASE,
)


def clamp_statement(text: str, max_chars: int | None = None) -> str:
    limit = max_chars if max_chars is not None else settings.dramaturgy_statement_max_chars
    trimmed = text.strip()
    if len(trimmed) <= limit:
        return trimmed
    cut = trimmed[:limit]
    for sep in (". ", "! ", "? ", "… "):
        idx = cut.rfind(sep)
        if idx >= limit // 2:
            return cut[: idx + 1].strip()
    last_space = cut.rfind(" ")
    if last_space >= limit // 2:
        return cut[:last_space].strip()
    return cut.strip()


def strip_limit_complaints(text: str) -> str:
    """Remove lines where the model complains about character limits."""
    kept: list[str] = []
    for line in text.splitlines():
        if _LIMIT_COMPLAINT_RE.search(line):
            continue
        kept.append(line)
    return "\n".join(kept).strip()
