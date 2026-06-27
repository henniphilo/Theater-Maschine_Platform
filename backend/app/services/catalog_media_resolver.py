"""Map dramaturg descriptions and invented labels to real catalog media IDs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from app.director.media.database import MediaDatabase
from app.schemas.part1_selection import MediaSelectionLists
from app.schemas.sound_cues import SoundCueEntry
from app.services.sound_cue_catalog import get_sound_cue_catalog_service
from app.services.video_cue_catalog import get_video_cue_catalog_service

_TOKEN_RE = re.compile(r"[a-zäöüß]{3,}", re.IGNORECASE)
_MUSIC_TAGS = frozenset({"musik", "music"})
_BED_TAGS = frozenset({"drone", "grundton", "dauer", "ambient", "atmo", "pad"})
_HINT_EXPANSIONS: dict[str, list[str]] = {
    "drone": ["grundader", "grundton", "maschinen"],
    "hum": ["grundader", "rauschen", "archiv"],
    "office": ["maschinen", "archiv"],
    "growl": ["tier", "tierstimme", "knurr"],
    "knurr": ["tierstimme", "tier"],
    "kalt": ["kaefig", "metall", "buehne"],
    "kühl": ["kalt", "kaefig"],
    "cold": ["kalt", "kaefig"],
    "crowd": ["chor", "stimmen", "masse"],
    "murmur": ["chor", "summen"],
    "static": ["rauschen", "archiv", "glitch"],
    "noise": ["rauschen", "archiv"],
    "ticker": ["glitch", "digital"],
    "click": ["glitch", "metall"],
    "flicker": ["blendung", "flacker"],
    "beam": ["seitenlicht", "spot"],
    "spot": ["spot", "tisch"],
    "isolated": ["spot", "tisch"],
    "fade": ["blendung"],
    "tension": ["hart", "seitenlicht"],
    "pulse": ["herz", "puls"],
}


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    return (
        lowered.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _tokens(text: str) -> set[str]:
    base = {_normalize_text(token) for token in _TOKEN_RE.findall(text)}
    expanded = set(base)
    for token in base:
        for hint in _HINT_EXPANSIONS.get(token, []):
            expanded.add(_normalize_text(hint))
    return expanded


def _is_music_cue(entry: SoundCueEntry) -> bool:
    tags = {t.lower() for t in entry.tags}
    return bool(tags & _MUSIC_TAGS)


def _is_sound_cue(entry: SoundCueEntry) -> bool:
    tags = {t.lower() for t in entry.tags}
    if tags & _BED_TAGS:
        return True
    return not _is_music_cue(entry)


def _score_match(
    query: str,
    *,
    item_id: str,
    tags: list[str],
    moods: list[str],
    description: str = "",
    label: str = "",
) -> float:
    normalized_query = _normalize_text(query)
    query_tokens = _tokens(query)
    score = 0.0

    if item_id in normalized_query.replace(" ", "_") or item_id.replace("_", " ") in normalized_query:
        score += 8.0

    for tag in tags:
        tag_norm = _normalize_text(tag)
        if tag_norm in normalized_query:
            score += 4.0
        if tag_norm in query_tokens:
            score += 3.0

    for mood in moods:
        mood_norm = _normalize_text(mood)
        if mood_norm in normalized_query:
            score += 3.0
        if mood_norm in query_tokens:
            score += 2.0

    for field in (description, label, item_id.replace("_", " ")):
        for token in _tokens(field):
            if token in query_tokens:
                score += 1.25

    for part in item_id.split("_"):
        if len(part) >= 4 and part in normalized_query:
            score += 1.5

    return score


@dataclass
class CatalogMediaMatcher:
    sound_play: tuple[SoundCueEntry, ...]
    videos: tuple[dict, ...]
    lights: tuple[dict, ...]

    @classmethod
    def load(cls) -> CatalogMediaMatcher:
        catalog = get_sound_cue_catalog_service().load()
        db = MediaDatabase()
        return cls(
            sound_play=tuple(c for c in catalog.cues if c.action == "play"),
            videos=tuple(
                {"id": v.id, "tags": v.tags, "moods": v.moods, "description": getattr(v, "description", "")}
                for v in db.videos
            ),
            lights=tuple(
                {
                    "id": s.id,
                    "tags": list(getattr(s, "channels", []) or []),
                    "moods": s.moods,
                    "description": s.description,
                }
                for s in db.light_scenes
                if s.id != "blackout"
            ),
        )

    def best_sound(self, query: str, *, music: bool = False, exclude: set[str] | None = None) -> str | None:
        blocked = exclude or set()
        best_id: str | None = None
        best_score = 0.0
        for entry in self.sound_play:
            if entry.id in blocked:
                continue
            if music and not _is_music_cue(entry):
                continue
            if not music and not _is_sound_cue(entry):
                continue
            score = _score_match(
                query,
                item_id=entry.id,
                tags=entry.tags,
                moods=entry.moods,
                description=entry.description,
                label=entry.soundname or entry.label,
            )
            if score > best_score:
                best_score = score
                best_id = entry.id
        return best_id if best_score >= 2.0 else None

    def best_video(self, query: str, *, exclude: set[str] | None = None) -> str | None:
        blocked = exclude or set()
        best_id: str | None = None
        best_score = 0.0
        for item in self.videos:
            item_id = str(item["id"])
            if item_id in blocked:
                continue
            score = _score_match(
                query,
                item_id=item_id,
                tags=list(item.get("tags", [])),
                moods=list(item.get("moods", [])),
                description=str(item.get("description", "")),
                label=item_id,
            )
            if score > best_score:
                best_score = score
                best_id = item_id
        return best_id if best_score >= 2.0 else None

    def best_light(self, query: str, *, exclude: set[str] | None = None) -> str | None:
        blocked = exclude or set()
        best_id: str | None = None
        best_score = 0.0
        for item in self.lights:
            item_id = str(item["id"])
            if item_id in blocked:
                continue
            score = _score_match(
                query,
                item_id=item_id,
                tags=list(item.get("tags", [])),
                moods=list(item.get("moods", [])),
                description=str(item.get("description", "")),
                label=item_id,
            )
            if score > best_score:
                best_score = score
                best_id = item_id
        return best_id if best_score >= 2.0 else None

    def resolve_invented(
        self,
        candidate: str,
        context: str,
        *,
        medium_hint: str | None = None,
        exclude: set[str] | None = None,
    ) -> tuple[str, str] | None:
        """Return (catalog_id, medium) for an invented label + description."""
        query = f"{candidate} {context}".strip()
        if medium_hint == "music":
            sound_id = self.best_sound(query, music=True, exclude=exclude)
            return (sound_id, "music") if sound_id else None
        if medium_hint == "sound":
            sound_id = self.best_sound(query, music=False, exclude=exclude)
            return (sound_id, "sound") if sound_id else None
        if medium_hint == "video":
            video_id = self.best_video(query, exclude=exclude)
            return (video_id, "video") if video_id else None
        if medium_hint == "light":
            light_id = self.best_light(query, exclude=exclude)
            return (light_id, "light") if light_id else None

        candidates: list[tuple[float, str, str]] = []
        for music in (False, True):
            sound_id = self.best_sound(query, music=music, exclude=exclude)
            if sound_id:
                medium = "music" if music else "sound"
                score = _score_match(query, item_id=sound_id, tags=[], moods=[])
                candidates.append((score, sound_id, medium))
        video_id = self.best_video(query, exclude=exclude)
        if video_id:
            candidates.append((_score_match(query, item_id=video_id, tags=[], moods=[]), video_id, "video"))
        light_id = self.best_light(query, exclude=exclude)
        if light_id:
            candidates.append((_score_match(query, item_id=light_id, tags=[], moods=[]), light_id, "light"))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        _, media_id, medium = candidates[0]
        return media_id, medium


@lru_cache(maxsize=1)
def get_catalog_media_matcher() -> CatalogMediaMatcher:
    return CatalogMediaMatcher.load()


def _remap_ids(
    ids: list[str],
    valid: set[str],
    remap_fn,
) -> list[str]:
    result: list[str] = []
    used: set[str] = set()
    for item_id in ids:
        if item_id in valid and item_id not in used:
            result.append(item_id)
            used.add(item_id)
            continue
        matched = remap_fn(item_id, used)
        if matched and matched not in used:
            result.append(matched)
            used.add(matched)
    return result


def _next_unused(pool: list[str], used: set[str]) -> str | None:
    for item_id in pool:
        if item_id not in used:
            return item_id
    return None


def normalize_media_lists(
    lists: MediaSelectionLists,
    *,
    video_scope: str = "part1",
) -> MediaSelectionLists:
    """Replace invented/unknown IDs with best catalog match from the label text."""
    matcher = get_catalog_media_matcher()
    catalog = get_sound_cue_catalog_service().load()
    play_by_id = {c.id: c for c in catalog.cues if c.action == "play"}
    music_ids = {c.id for c in play_by_id.values() if _is_music_cue(c)}
    video_ids = {c.id for c in get_video_cue_catalog_service().load(video_scope).clips}  # type: ignore[arg-type]
    light_ids = {s.id for s in MediaDatabase().light_scenes if s.id != "blackout"}

    sound_pool = sorted(item_id for item_id, entry in play_by_id.items() if _is_sound_cue(entry))
    music_pool = sorted(music_ids)
    video_pool = sorted(video_ids)
    light_pool = sorted(light_ids)

    used_sounds: set[str] = set()
    used_music: set[str] = set()

    def remap_sound(item_id: str, used: set[str]) -> str | None:
        matched = matcher.best_sound(item_id, music=False, exclude=used)
        return matched or _next_unused(sound_pool, used)

    def remap_music(item_id: str, used: set[str]) -> str | None:
        matched = matcher.best_sound(item_id, music=True, exclude=used)
        if matched:
            return matched
        matched = matcher.best_sound(item_id, music=False, exclude=used)
        return matched or _next_unused(music_pool, used) or _next_unused(sound_pool, used)

    def remap_video(item_id: str, used: set[str]) -> str | None:
        matched = matcher.best_video(item_id, exclude=used)
        return matched or _next_unused(video_pool, used)

    def remap_light(item_id: str, used: set[str]) -> str | None:
        matched = matcher.best_light(item_id, exclude=used)
        return matched or _next_unused(light_pool, used)

    sounds: list[str] = []
    for item_id in lists.sounds:
        entry = play_by_id.get(item_id)
        if entry and _is_sound_cue(entry) and item_id not in used_sounds:
            sounds.append(item_id)
            used_sounds.add(item_id)
            continue
        matched = remap_sound(item_id, used_sounds)
        if matched and matched not in used_sounds:
            sounds.append(matched)
            used_sounds.add(matched)

    music: list[str] = []
    for item_id in lists.music:
        if item_id in music_ids and item_id not in used_music:
            music.append(item_id)
            used_music.add(item_id)
            continue
        matched = remap_music(item_id, used_music)
        if matched and matched not in used_music:
            music.append(matched)
            used_music.add(matched)

    videos = _remap_ids(lists.videos, video_ids, lambda item_id, used: remap_video(item_id, used))
    lights = _remap_ids(lists.lights, light_ids, lambda item_id, used: remap_light(item_id, used))

    return MediaSelectionLists(sounds=sounds, music=music, videos=videos, lights=lights)
