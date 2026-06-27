"""Parse dramaturg discussion text for media IDs and build preview/live decisions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.director.cues.cue_models import DramaturgyDecision, LightCue, SoundCue, VisualCue
from app.schemas.media_mentions import MediaMention, MediaMentionMedium

_MENTION_LINE = re.compile(
    r"^[\s]*[-*•]\s*(?P<id>[a-z][a-z0-9_]*)\s*(?:[—\-–:]|\s+)\s*(?P<rest>.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_BACKTICK_BULLET_RE = re.compile(
    r"^[\s]*[-*•]\s*`(?P<id>[a-z][a-z0-9_]*)`(?:\s*[:—–-]\s*(?P<rest>.*))?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_BACKTICK_INLINE_RE = re.compile(r"`([a-z][a-z0-9_]*)`")
_QUOTE_RE = re.compile(r"«([^»]{2,80})»")
_THEMA_RE = re.compile(r"Thema:\s*([^/\n«]{2,80})", re.IGNORECASE)
_JSON_LINE_RE = re.compile(r'^\s*\{[^{}]*"sounds"')
_MOOD_KEYWORD_LINE = re.compile(r"«([^»]{2,80})»")
_MEDIUM_IN_PARENS_RE = re.compile(
    r"\((?P<medium>Sounds?|Musik|Videos?|Licht(?:stimmungen)?)\)",
    re.IGNORECASE,
)
_MEDIUM_LABEL_RE = re.compile(
    r"(?P<medium>Sounds?|Musik|Videos?|Licht(?:stimmungen)?)\s*:\s*(?P<mood>[^;«]+)",
    re.IGNORECASE,
)
_ID_BULLET_RE = re.compile(
    r"^[\s]*[-*•]\s*(?:`(?P<id>[a-z][a-z0-9_]*)`|(?P<id2>[a-z][a-z0-9_]*))\s*(?:[—\-–:]|\s+)",
    re.IGNORECASE,
)
_MEDIUM_LABEL: dict[MediaMentionMedium, str] = {
    "sound": "Sound",
    "music": "Musik",
    "video": "Video",
    "light": "Licht",
}


@dataclass(frozen=True)
class MediaAllowlist:
    sounds: frozenset[str]
    music: frozenset[str]
    videos: frozenset[str]
    lights: frozenset[str]

    def classify(self, media_id: str) -> MediaMentionMedium | None:
        if media_id in self.music:
            return "music"
        if media_id in self.sounds:
            return "sound"
        if media_id in self.videos:
            return "video"
        if media_id in self.lights:
            return "light"
        return None


def build_media_alias_index(compact_catalog: dict[str, Any]) -> dict[str, tuple[str, MediaMentionMedium]]:
    index: dict[str, tuple[str, MediaMentionMedium]] = {}
    music_tags = {"musik", "music"}

    for item in compact_catalog.get("sounds", []):
        sound_id = str(item["id"])
        tags = {str(tag).lower() for tag in item.get("tags", [])}
        medium: MediaMentionMedium = "music" if tags & music_tags else "sound"
        index[sound_id] = (sound_id, medium)
        for tag in tags:
            index[tag] = (sound_id, medium)
        for part in sound_id.split("_"):
            if len(part) >= 4:
                index.setdefault(part, (sound_id, medium))

    for item in compact_catalog.get("videos", []):
        video_id = str(item["id"])
        index[video_id] = (video_id, "video")
        for tag in item.get("tags", []):
            index[str(tag).lower()] = (video_id, "video")

    for item in compact_catalog.get("lights", []):
        light_id = str(item["id"])
        index[light_id] = (light_id, "light")
        for mood in item.get("moods", []):
            index[str(mood).lower()] = (light_id, "light")

    return index


def resolve_media_id(
    candidate: str,
    allowlist: MediaAllowlist,
    alias_index: dict[str, tuple[str, MediaMentionMedium]],
    *,
    context: str = "",
    medium_hint: MediaMentionMedium | None = None,
) -> tuple[str, MediaMentionMedium] | None:
    normalized = candidate.lower().strip()
    direct = allowlist.classify(normalized)
    if direct:
        return normalized, direct

    if normalized in alias_index and normalized in (
        *allowlist.sounds,
        *allowlist.music,
        *allowlist.videos,
        *allowlist.lights,
    ):
        return alias_index[normalized]

    from app.services.catalog_media_resolver import get_catalog_media_matcher

    matcher = get_catalog_media_matcher()
    invented = matcher.resolve_invented(
        normalized,
        context,
        medium_hint=medium_hint,
    )
    if invented:
        media_id, medium = invented
        if allowlist.classify(media_id):
            return media_id, medium
    return None


def _medium_from_label(label: str) -> MediaMentionMedium:
    lowered = label.lower()
    if lowered.startswith("sound"):
        return "sound"
    if lowered == "musik":
        return "music"
    if lowered.startswith("video"):
        return "video"
    return "light"


def _resolve_mood_to_media(
    mood_text: str,
    medium: MediaMentionMedium,
    allowlist: MediaAllowlist,
) -> tuple[str, MediaMentionMedium] | None:
    from app.services.catalog_media_resolver import get_catalog_media_matcher

    matcher = get_catalog_media_matcher()
    query = mood_text.strip()
    if not query:
        return None
    if medium == "music":
        media_id = matcher.best_sound(query, music=True)
        if media_id and allowlist.classify(media_id):
            return media_id, "music"
        return None
    if medium == "sound":
        media_id = matcher.best_sound(query, music=False)
        if media_id and allowlist.classify(media_id):
            return media_id, "sound"
        return None
    if medium == "video":
        media_id = matcher.best_video(query)
        if media_id and allowlist.classify(media_id):
            return media_id, "video"
        return None
    media_id = matcher.best_light(query)
    if media_id and allowlist.classify(media_id):
        return media_id, "light"
    return None


def _parse_mood_segments(line: str) -> list[tuple[MediaMentionMedium, str]]:
    segments: list[tuple[MediaMentionMedium, str]] = []
    for match in _MEDIUM_LABEL_RE.finditer(line):
        segments.append((_medium_from_label(match.group("medium")), match.group("mood").strip()))

    for match in _MEDIUM_IN_PARENS_RE.finditer(line):
        medium = _medium_from_label(match.group("medium"))
        before = line[: match.start()]
        if "»" in before:
            before = before.split("»", 1)[-1]
        mood = before.strip(" —–-;,.:")
        if mood:
            segments.append((medium, mood))

    if segments:
        return segments

    quote_end = line.find("»")
    if quote_end >= 0:
        fallback = line[quote_end + 1 :].strip(" —–-;,.:")
        if fallback:
            segments.append(("sound", fallback))
    return segments


def _is_id_bullet_line(line: str) -> bool:
    return bool(_ID_BULLET_RE.match(line.strip()))


def extract_mood_keyword_mentions(
    text: str,
    allowlist: MediaAllowlist,
    *,
    base_offset: int = 0,
) -> list[MediaMention]:
    mentions: list[MediaMention] = []
    seen: set[tuple[str, int]] = set()
    offset = base_offset
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("```") or _JSON_LINE_RE.match(stripped):
            continue
        if _is_id_bullet_line(stripped):
            offset += len(line) + 1
            continue
        keyword_match = _MOOD_KEYWORD_LINE.search(line)
        if not keyword_match:
            offset += len(line) + 1
            continue
        keyword = keyword_match.group(1).strip()
        segments = _parse_mood_segments(line)
        if not segments:
            offset += len(line) + 1
            continue
        line_start = offset
        for medium, mood_text in segments:
            resolved = _resolve_mood_to_media(mood_text, medium, allowlist)
            if resolved is None:
                continue
            media_id, resolved_medium = resolved
            _append_mention(
                mentions,
                seen,
                medium=resolved_medium,
                media_id=media_id,
                char_offset=line_start,
                keyword=keyword,
            )
        offset += len(line) + 1
    return mentions


def _spoken_phrase_for_mood(keyword: str, medium: MediaMentionMedium, mood_text: str) -> str:
    label = _MEDIUM_LABEL[medium]
    clean_mood = re.sub(r"[*_`]", "", mood_text).strip().rstrip(".,;")
    return f"Beim Stichwort «{keyword}»: {clean_mood} ({label})."


def _keyword_from_rest(rest: str) -> str | None:
    quote = _QUOTE_RE.search(rest)
    if quote:
        return quote.group(1).strip()[:80]
    thema = _THEMA_RE.search(rest)
    if thema:
        return thema.group(1).strip()[:80]
    paren = re.search(r"\(([^)]{2,80})\)", rest)
    if paren:
        return paren.group(1).strip()[:80]
    return None


def _append_mention(
    mentions: list[MediaMention],
    seen: set[tuple[str, int]],
    *,
    medium: MediaMentionMedium,
    media_id: str,
    char_offset: int,
    keyword: str | None,
) -> None:
    key = (media_id, char_offset)
    if key in seen:
        return
    seen.add(key)
    mentions.append(
        MediaMention(
            medium=medium,
            media_id=media_id,
            keyword=keyword,
            char_offset=char_offset,
        )
    )


def _medium_from_section(line: str) -> MediaMentionMedium | None:
    match = re.search(r"\*\*(Sounds?|Musik|Videos?|Licht(?:stimmungen)?)\*\*", line, re.IGNORECASE)
    if not match:
        return None
    label = match.group(1).lower()
    if label.startswith("sound"):
        return "sound"
    if label == "musik":
        return "music"
    if label.startswith("video"):
        return "video"
    return "light"


def _section_hint_at(text: str, position: int) -> MediaMentionMedium | None:
    hint: MediaMentionMedium | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        hint = _medium_from_section(line) or hint
        offset += len(line)
        if offset > position:
            break
    return hint


def extract_media_mentions(
    text: str,
    allowlist: MediaAllowlist,
    alias_index: dict[str, tuple[str, MediaMentionMedium]] | None = None,
) -> list[MediaMention]:
    alias_index = alias_index or {}
    mentions: list[MediaMention] = []
    seen: set[tuple[str, int]] = set()

    for match in _BACKTICK_BULLET_RE.finditer(text):
        resolved = resolve_media_id(
            match.group("id"),
            allowlist,
            alias_index,
            context=match.group("rest") or "",
            medium_hint=_section_hint_at(text, match.start()),
        )
        if resolved is None:
            continue
        media_id, medium = resolved
        _append_mention(
            mentions,
            seen,
            medium=medium,
            media_id=media_id,
            char_offset=match.start(),
            keyword=_keyword_from_rest(match.group("rest") or ""),
        )

    for match in _MENTION_LINE.finditer(text):
        resolved = resolve_media_id(
            match.group("id"),
            allowlist,
            alias_index,
            context=match.group("rest"),
            medium_hint=_section_hint_at(text, match.start()),
        )
        if resolved is None:
            continue
        media_id, medium = resolved
        _append_mention(
            mentions,
            seen,
            medium=medium,
            media_id=media_id,
            char_offset=match.start(),
            keyword=_keyword_from_rest(match.group("rest")),
        )

    for match in _BACKTICK_INLINE_RE.finditer(text):
        resolved = resolve_media_id(
            match.group(1),
            allowlist,
            alias_index,
            context=text[max(0, match.start() - 40) : match.end() + 80],
            medium_hint=_section_hint_at(text, match.start()),
        )
        if resolved is None:
            continue
        media_id, medium = resolved
        if any(m.media_id == media_id and abs(m.char_offset - match.start()) < 40 for m in mentions):
            continue
        _append_mention(
            mentions,
            seen,
            medium=medium,
            media_id=media_id,
            char_offset=match.start(),
            keyword=None,
        )

    mood_mentions = extract_mood_keyword_mentions(text, allowlist)
    for mention in mood_mentions:
        _append_mention(
            mentions,
            seen,
            medium=mention.medium,
            media_id=mention.media_id,
            char_offset=mention.char_offset,
            keyword=mention.keyword,
        )

    mentions.sort(key=lambda item: item.char_offset)
    return mentions


def build_spoken_playback_with_mentions(
    raw: str,
    allowlist: MediaAllowlist,
    alias_index: dict[str, tuple[str, MediaMentionMedium]],
) -> tuple[str, list[MediaMention]]:
    """TTS text with mood descriptions + offsets aligned for OSC sync."""
    spoken_lines: list[str] = []
    mentions: list[MediaMention] = []
    seen: set[tuple[str, int]] = set()
    offset = 0
    section_hint: MediaMentionMedium | None = None

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("```") or _JSON_LINE_RE.match(stripped):
            continue

        section_hint = _medium_from_section(line) or section_hint

        keyword_match = _MOOD_KEYWORD_LINE.search(line)
        mood_segments = _parse_mood_segments(line) if keyword_match else []
        if keyword_match and mood_segments and not _is_id_bullet_line(stripped):
            keyword = keyword_match.group(1).strip()
            line_start = offset
            for medium, mood_text in mood_segments:
                resolved = _resolve_mood_to_media(mood_text, medium, allowlist)
                if resolved is None:
                    continue
                media_id, resolved_medium = resolved
                phrase = _spoken_phrase_for_mood(keyword, resolved_medium, mood_text)
                _append_mention(
                    mentions,
                    seen,
                    medium=resolved_medium,
                    media_id=media_id,
                    char_offset=line_start,
                    keyword=keyword,
                )
                spoken_lines.append(phrase)
                offset += len(phrase) + 1
            continue

        bullet = _BACKTICK_BULLET_RE.match(line) or _MENTION_LINE.match(line)
        if bullet:
            rest = bullet.groupdict().get("rest") or ""
            resolved = resolve_media_id(
                bullet.group("id"),
                allowlist,
                alias_index,
                context=rest,
                medium_hint=section_hint,
            )
            if resolved:
                media_id, medium = resolved
                label = _MEDIUM_LABEL[medium]
                phrase = f"{label} {media_id.replace('_', ' ')}."
                keyword = _keyword_from_rest(rest)
                if rest.strip():
                    short = re.sub(r"[*_`]", "", rest.strip())[:90].rstrip(".,;")
                    if short:
                        phrase += f" {short}."
                _append_mention(
                    mentions,
                    seen,
                    medium=medium,
                    media_id=media_id,
                    char_offset=offset,
                    keyword=keyword,
                )
                spoken_lines.append(phrase)
                offset += len(phrase) + 1
                continue

        inline_ids = list(_BACKTICK_INLINE_RE.finditer(line))
        if inline_ids and (":" in line or "**" in line):
            for match in inline_ids:
                resolved = resolve_media_id(
                    match.group(1),
                    allowlist,
                    alias_index,
                    context=line,
                    medium_hint=section_hint,
                )
                if resolved is None:
                    continue
                media_id, medium = resolved
                label = _MEDIUM_LABEL[medium]
                phrase = f"{label} {media_id.replace('_', ' ')}."
                _append_mention(
                    mentions,
                    seen,
                    medium=medium,
                    media_id=media_id,
                    char_offset=offset,
                    keyword=None,
                )
                spoken_lines.append(phrase)
                offset += len(phrase) + 1
            continue

        if re.match(r"^\s*\*\*[^*]+\*\*\s*$", line):
            header = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
            spoken_lines.append(header + ".")
            offset += len(header) + 2
            continue

        clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", line).strip()
        clean = re.sub(r"`([^`]+)`", r"\1", clean)
        if clean:
            spoken_lines.append(clean)
            offset += len(clean) + 1

    spoken = "\n".join(spoken_lines).strip()
    if not spoken:
        from app.services.spoken_text import spoken_discussion_text

        spoken = spoken_discussion_text(raw)
        mentions = extract_media_mentions(raw, allowlist, alias_index)
    return spoken, mentions


def decision_for_media_mention(mention: MediaMention) -> DramaturgyDecision:
    if mention.medium in ("sound", "music"):
        return DramaturgyDecision(
            sound=SoundCue(cue_id=mention.media_id, volume=0.65),
            reason=f"Dramaturgen nennen {mention.media_id}",
        )
    if mention.medium == "video":
        return DramaturgyDecision(
            visual=VisualCue(clip_id=mention.media_id),
            reason=f"Dramaturgen nennen {mention.media_id}",
        )
    return DramaturgyDecision(
        light=LightCue(scene_id=mention.media_id, intensity=0.55),
        reason=f"Dramaturgen nennen {mention.media_id}",
    )


def keywords_for_performance(mentions: list[MediaMention], scene_text: str) -> list[MediaMention]:
    lowered = scene_text.lower()
    result: list[MediaMention] = []
    seen_keywords: set[str] = set()
    for mention in mentions:
        if not mention.keyword:
            continue
        keyword = mention.keyword.strip()
        if len(keyword) < 3:
            continue
        key = keyword.lower()
        if key in seen_keywords:
            continue
        if key not in lowered:
            continue
        seen_keywords.add(key)
        result.append(mention)
    return result
