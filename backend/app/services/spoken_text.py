"""Text sanitization for TTS — discussion turns must not pass shell flags to macOS say."""

import re

_ID_MEDIA_BULLET_RE = re.compile(
    r"^\s*-\s+[`']?[a-z][a-z0-9_]*[`']?\s*[—–-]\s*.+$",
    re.MULTILINE | re.IGNORECASE,
)
_MEDIA_HEADER_RE = re.compile(r"^\s*\*\*[^*]+\*\*\s*$", re.MULTILINE)


def _is_id_media_bullet_line(line: str) -> bool:
    """Catalog-ID bullet lines (old format) — not mood+keyword lines."""
    return bool(_ID_MEDIA_BULLET_RE.match(line.strip()))


def _strip_json_blocks(text: str) -> str:
    text = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", text, flags=re.DOTALL).strip()
    return re.sub(r"\{[^{}]*\"sounds\"[^{}]*\}", "", text, flags=re.DOTALL).strip()


def _intro_before_id_bullets(raw: str) -> str:
    match = _ID_MEDIA_BULLET_RE.search(raw)
    if not match:
        return ""
    intro = _strip_json_blocks(raw[: match.start()]).strip()
    intro = _MEDIA_HEADER_RE.sub("", intro).strip()
    intro = re.sub(r"\n{3,}", "\n\n", intro).strip()
    return intro


def _media_list_fallback() -> str:
    return (
        "Hier ist unser vereinbartes Medienpaket — Sounds, Musik, Videos und Licht. "
        "Die einzelnen Begründungen stehen im Chat."
    )


def needs_discussion_sanitization(raw: str) -> bool:
    """True when raw LLM output still has catalog-ID bullets or JSON — skip for pre-built TTS."""
    if not raw.strip():
        return False
    if _ID_MEDIA_BULLET_RE.search(raw):
        return True
    if '"sounds"' in raw or "```json" in raw.lower():
        return True
    return False


def spoken_discussion_text(raw: str) -> str:
    """Spoken version for TTS: no JSON, no catalog-ID bullet lines; mood lines kept."""
    if not raw.strip():
        return ""

    had_id_bullets = bool(_ID_MEDIA_BULLET_RE.search(raw))
    text = _strip_json_blocks(raw)

    kept_lines: list[str] = []
    for line in text.splitlines():
        if _is_id_media_bullet_line(line):
            continue
        if _MEDIA_HEADER_RE.match(line):
            continue
        kept_lines.append(line)

    text = "\n".join(kept_lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) < 30 and had_id_bullets:
        intro = _intro_before_id_bullets(raw)
        if len(intro) >= 20:
            return intro
        return _media_list_fallback()

    return text or raw[:500]
