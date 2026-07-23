"""Content-based MIME sniffing — do not trust client extension alone."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.models.asset import AssetType

# Default allowlist (overridable via settings).
DEFAULT_ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "video/mp4",
        "video/quicktime",
        "video/webm",
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/aiff",
        "audio/x-aiff",
        "image/png",
        "image/jpeg",
        "image/webp",
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
        "application/csv",
        "text/x-markdown",
    }
)

_MIME_TO_EXTENSION: dict[str, str] = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/webm": "webm",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/aiff": "aiff",
    "audio/x-aiff": "aiff",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/x-markdown": "md",
    "text/csv": "csv",
    "application/csv": "csv",
    "application/json": "json",
}

_MIME_TO_ASSET_TYPE: dict[str, AssetType] = {
    "video/mp4": AssetType.VIDEO,
    "video/quicktime": AssetType.VIDEO,
    "video/webm": AssetType.VIDEO,
    "audio/wav": AssetType.AUDIO,
    "audio/x-wav": AssetType.AUDIO,
    "audio/mpeg": AssetType.AUDIO,
    "audio/mp3": AssetType.AUDIO,
    "audio/aiff": AssetType.AUDIO,
    "audio/x-aiff": AssetType.AUDIO,
    "image/png": AssetType.IMAGE,
    "image/jpeg": AssetType.IMAGE,
    "image/webp": AssetType.IMAGE,
    "text/plain": AssetType.TEXT,
    "text/markdown": AssetType.TEXT,
    "text/x-markdown": AssetType.TEXT,
    "text/csv": AssetType.DATA,
    "application/csv": AssetType.DATA,
    "application/json": AssetType.DATA,
}

_EXT_HINT: dict[str, str] = {
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "aiff": "audio/aiff",
    "aif": "audio/aiff",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "txt": "text/plain",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "csv": "text/csv",
    "json": "application/json",
}


@dataclass(frozen=True)
class DetectedContent:
    mime_type: str
    extension: str
    asset_type: AssetType


class MimeDetectionError(ValueError):
    pass


def extension_for_mime(mime_type: str) -> str:
    return _MIME_TO_EXTENSION.get(mime_type, "bin")


def asset_type_for_mime(mime_type: str) -> AssetType:
    return _MIME_TO_ASSET_TYPE.get(mime_type, AssetType.OTHER)


def canonical_mime(mime_type: str) -> str:
    """Normalize synonyms to a single stored MIME."""
    aliases = {
        "audio/x-wav": "audio/wav",
        "audio/mp3": "audio/mpeg",
        "audio/x-aiff": "audio/aiff",
        "text/x-markdown": "text/markdown",
        "application/csv": "text/csv",
    }
    return aliases.get(mime_type, mime_type)


def _looks_like_utf8_text(sample: bytes) -> bool:
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _sniff_binary(sample: bytes) -> str | None:
    if sample.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if sample.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(sample) >= 12 and sample.startswith(b"RIFF") and sample[8:12] == b"WEBP":
        return "image/webp"
    if len(sample) >= 12 and sample.startswith(b"RIFF") and sample[8:12] == b"WAVE":
        return "audio/wav"
    if sample.startswith(b"FORM") and len(sample) >= 12 and sample[8:12] in (b"AIFF", b"AIFC"):
        return "audio/aiff"
    if sample.startswith(b"ID3") or (
        len(sample) >= 2 and sample[0] == 0xFF and (sample[1] & 0xE0) == 0xE0
    ):
        # MPEG frame sync — treat as mp3 when extension/hint agrees later
        return "audio/mpeg"
    if sample.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    # ISO BMFF (mp4 / mov / m4a): ftyp box at offset 4
    if len(sample) >= 12 and sample[4:8] == b"ftyp":
        brand = sample[8:12]
        if brand in (b"qt  ", b"havu"):
            return "video/quicktime"
        return "video/mp4"
    return None


def detect_content(
    *,
    sample: bytes,
    filename: str,
    claimed_content_type: str | None,
    allowed_mime_types: frozenset[str],
) -> DetectedContent:
    """Detect MIME from bytes; use filename only as a disambiguation hint."""
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()

    sniffed = _sniff_binary(sample)
    hint = _EXT_HINT.get(ext)
    claimed = (claimed_content_type or "").split(";")[0].strip().lower() or None

    mime: str | None = None

    if sniffed:
        mime = sniffed
        # mp3 sniff is weak — require matching hint or claim when ambiguous
        if sniffed == "audio/mpeg" and hint not in (None, "audio/mpeg") and claimed not in (
            None,
            "audio/mpeg",
            "audio/mp3",
        ):
            if hint and hint.startswith("audio/"):
                mime = hint
    elif _looks_like_utf8_text(sample):
        text = sample.decode("utf-8", errors="replace").lstrip("\ufeff")
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                json.loads(text)
                mime = "application/json"
            except json.JSONDecodeError:
                mime = hint or "text/plain"
        elif hint == "text/csv" or (
            hint is None and "," in text and re.search(r"[\r\n]", text)
        ):
            mime = "text/csv"
        elif hint in ("text/markdown", "text/plain"):
            mime = hint
        elif claimed in ("text/markdown", "text/plain", "text/csv", "application/json"):
            mime = claimed
        else:
            mime = hint or "text/plain"
    else:
        raise MimeDetectionError("unrecognized or binary content type")

    mime = canonical_mime(mime)
    allowed_canonical = {canonical_mime(m) for m in allowed_mime_types}
    if mime not in allowed_canonical and mime not in allowed_mime_types:
        raise MimeDetectionError(f"mime type not allowed: {mime}")

    # Extension must not contradict a strong binary sniff
    if sniffed and hint and canonical_mime(hint) != mime:
        # Allow wav/x-wav style aliases only
        if canonical_mime(hint) != canonical_mime(mime):
            raise MimeDetectionError(
                f"content type {mime} does not match filename extension .{ext}"
            )

    return DetectedContent(
        mime_type=mime,
        extension=extension_for_mime(mime),
        asset_type=asset_type_for_mime(mime),
    )
