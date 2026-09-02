"""Anarchy-driven, mood-independent cue selection for Teil 2."""

from __future__ import annotations

import re
import unicodedata

from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    LightCue,
    SoundAction,
    SoundCue,
)
from app.director.media.database import MediaDatabase
from app.schemas.inszenierung import AnarchyCurve
from app.services.part2_cue_density import light_fade_seconds

# Soft base looks for the opening; harsh/cut looks only once chaos rises.
_LIGHT_EARLY_IDS = frozenset(
    {
        "gegenlicht_weich",
        "warme_buehnenflaeche",
        "luster_treppen",
        "saallicht",
        "wolkenprospekt_boden",
        "teppich_rot",
        "gegenlicht_lichteinfall",
    }
)
_LIGHT_HARSH_IDS = frozenset(
    {
        "seitenlicht_hart",
        "buehne_kalt_hart",
        "blendung_magenta",
        "blendung_zuschauerraum",
        "vorbuehnenzug",
    }
)
_PLAY_SOUND_ACTIONS = frozenset({"play"})
_STOP_SOUND_SUFFIXES = ("_out", "_fade_out")


def playable_dramaturgy_sounds(sounds: list) -> list:
    """Start cues only — fade_out / out / cut_all make Teil 2 feel silent."""
    return [sound for sound in sounds if getattr(sound, "action", "play") in _PLAY_SOUND_ACTIONS]


def is_playable_sound_id(cue_id: str | None) -> bool:
    if not cue_id:
        return False
    if cue_id == "alle_sounds_cut":
        return False
    return not cue_id.endswith(_STOP_SOUND_SUFFIXES)


def sound_volume_for_anarchy(anarchy: float) -> float:
    level = max(0.0, min(1.0, anarchy))
    return round(min(1.0, 0.58 + level * 0.42), 2)


_LIGHT_FAMILY: dict[str, str] = {
    "warme_buehnenflaeche": "warm",
    "teppich_rot": "warm",
    "luster_treppen": "warm",
    "saallicht": "warm",
    "gegenlicht_weich": "soft",
    "gegenlicht_lichteinfall": "soft",
    "wolkenprospekt_boden": "soft",
    "klavier": "focus",
    "klaviertasten": "focus",
    "fluegel": "focus",
    "musiker": "focus",
    "spot_tisch": "focus",
    "zwei_spots": "focus",
    "seitenlicht_hart": "harsh",
    "buehne_kalt_hart": "harsh",
    "blendung_magenta": "harsh",
    "blendung_zuschauerraum": "harsh",
    "vorbuehnenzug": "harsh",
    "palmen": "accent",
    "lautsprecher_buehne": "accent",
}


def _normalize(text: str) -> str:
    cleaned = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in cleaned if not unicodedata.combining(c))


def anarchy_at(sentence_index: int, total: int, curve: AnarchyCurve) -> float:
    if total <= 1:
        return curve.end
    t = sentence_index / (total - 1)
    return curve.start + (curve.end - curve.start) * t


def anarchy_for_char_offset(char_offset: int, script_len: int, curve: AnarchyCurve) -> float:
    if script_len <= 1:
        return curve.end
    t = max(0.0, min(1.0, char_offset / (script_len - 1)))
    return curve.start + (curve.end - curve.start) * t


def anarchy_function(anarchy: float) -> str:
    if anarchy < 0.45:
        return "verstärken"
    if anarchy < 0.7:
        return "überlagern"
    if anarchy < 0.85:
        return "entfremden"
    return "desorientieren"


def find_sentence_index_for_keyword(keyword: str, sentences: list[str]) -> int | None:
    needle = _normalize(keyword)
    if not needle:
        return None
    for index, sentence in enumerate(sentences):
        if needle in _normalize(sentence):
            return index
    return None


def find_char_offset_for_keyword(keyword: str, script_text: str) -> int | None:
    hay = _normalize(script_text)
    needle = _normalize(keyword)
    pos = hay.find(needle)
    if pos < 0:
        return None
    return pos


def keyword_in_script(keyword: str, script_text: str) -> bool:
    return find_char_offset_for_keyword(keyword, script_text) is not None


def teil2_cue_allowlist(media_db: MediaDatabase | None = None) -> dict[str, list[dict[str, str]]]:
    db = media_db or MediaDatabase()
    return {
        "sounds": [
            {
                "id": s.id,
                "soundname": s.soundname or s.label,
                "action": s.action,
            }
            for s in playable_dramaturgy_sounds(db.dramaturgy_sounds)
        ],
        "lights": [
            {"id": scene.id, "channels": scene.channels[:6]}
            for scene in db.light_scenes
            if scene.id != "blackout"
        ],
    }


def pick_sound_id(
    slot: int,
    anarchy: float,
    sounds: list,
    *,
    recent: list[str] | None = None,
) -> str | None:
    pool = playable_dramaturgy_sounds(sounds) or list(sounds)
    if not pool:
        return None
    recent_set = set(recent or [])
    seed = slot + int(anarchy * 13)
    for offset in range(len(pool)):
        candidate = pool[(seed + offset) % len(pool)]
        cue_id = candidate.id
        if cue_id not in recent_set and is_playable_sound_id(cue_id):
            return cue_id
    fallback = pool[seed % len(pool)].id
    if is_playable_sound_id(fallback):
        return fallback
    for item in pool:
        if is_playable_sound_id(item.id):
            return item.id
    return None


def _light_pool_for_anarchy(scenes: list, anarchy: float) -> list:
    playable = [scene for scene in scenes if scene.id != "blackout"]
    if not playable:
        return []
    in_range = [
        scene
        for scene in playable
        if scene.intensity_min <= anarchy <= scene.intensity_max
    ]
    pool = in_range or playable

    if anarchy < 0.45:
        early = [scene for scene in pool if scene.id in _LIGHT_EARLY_IDS]
        return early or [scene for scene in pool if scene.id not in _LIGHT_HARSH_IDS] or pool
    if anarchy < 0.7:
        mid = [scene for scene in pool if scene.id not in _LIGHT_HARSH_IDS]
        return mid or pool
    return pool


def pick_light_scene(
    slot: int,
    anarchy: float,
    scenes: list,
    *,
    recent: list[str] | None = None,
):
    """Prefer coherent looks early; allow harsh jumps only when anarchy is high."""
    pool = _light_pool_for_anarchy(scenes, anarchy)
    if not pool:
        return None

    recent_list = list(recent or [])
    recent_set = set(recent_list)
    last_id = recent_list[-1] if recent_list else None
    last_family = _LIGHT_FAMILY.get(last_id or "", "")

    # Early/mid: evolve within the same lighting family when possible.
    if anarchy < 0.75 and last_family:
        family_pool = [
            scene
            for scene in pool
            if _LIGHT_FAMILY.get(scene.id) == last_family and scene.id not in recent_set
        ]
        if family_pool:
            pool = family_pool

    seed = slot * 3 + int(anarchy * 7)
    for offset in range(len(pool)):
        candidate = pool[(seed + offset) % len(pool)]
        if candidate.id not in recent_set:
            return candidate
    return pool[seed % len(pool)]


def extract_text_fallback_keywords(
    script_text: str,
    sentences: list[str],
    curve: AnarchyCurve,
    *,
    min_keywords: int = 20,
    max_keywords: int = 140,
) -> list[tuple[str, int, float]]:
    """Structural fallback when LLM is unavailable — no predefined theme lists."""
    script_len = max(1, len(script_text))
    seen: set[str] = set()
    candidates: list[tuple[int, str, int, float]] = []

    def add(keyword: str) -> None:
        key = keyword.strip()
        if len(key) < 3:
            return
        norm = _normalize(key)
        if norm in seen or not keyword_in_script(key, script_text):
            return
        offset = find_char_offset_for_keyword(key, script_text) or 0
        sentence_index = find_sentence_index_for_keyword(key, sentences)
        if sentence_index is None:
            return
        seen.add(norm)
        anarchy = anarchy_for_char_offset(offset, script_len, curve)
        candidates.append((offset, key, sentence_index, anarchy))

    for match in re.finditer(r"\b(\d{1,3})\.\s+([A-ZÄÖÜ][a-zäöüß]+)", script_text):
        add(match.group(2))

    for match in re.finditer(r"\b([A-ZÄÖÜ][a-zäöüß]{4,})\b", script_text):
        add(match.group(1))

    for match in re.finditer(r"([!?]{1,2})", script_text):
        start = max(0, match.start() - 24)
        fragment = script_text[start : match.start()].strip()
        words = re.findall(r"[A-Za-zÄÖÜäöüß]{4,}", fragment)
        if words:
            add(words[-1])

    candidates.sort(key=lambda item: item[0])

    if len(candidates) > max_keywords:
        step = len(candidates) / max_keywords
        thinned: list[tuple[int, str, int, float]] = []
        for index in range(max_keywords):
            thinned.append(candidates[int(index * step)])
        candidates = thinned

    result = [(key, sent_idx, anarchy) for _, key, sent_idx, anarchy in candidates]

    slot = 0
    while len(result) < min_keywords and slot < len(sentences):
        sentence = sentences[slot]
        tokens = re.findall(r"[A-Za-zÄÖÜäöüß]{5,}", sentence)
        for token in tokens[:2]:
            if len(result) >= min_keywords:
                break
            before = len(candidates)
            add(token)
            if len(candidates) > before:
                candidates.sort(key=lambda item: item[0])
                result = [(key, sent_idx, anarchy) for _, key, sent_idx, anarchy in candidates]
                break
        slot += 1

    return result


def build_keyword_cue_point(
    keyword: str,
    sentence_index: int,
    anarchy: float,
    media_db: MediaDatabase | None = None,
    *,
    slot: int = 0,
    recent_sound_ids: list[str] | None = None,
    recent_light_ids: list[str] | None = None,
) -> CuePoint:
    db = media_db or MediaDatabase()
    fn = anarchy_function(anarchy)
    sound_id = pick_sound_id(slot, anarchy, db.dramaturgy_sounds, recent=recent_sound_ids)
    light_scene = pick_light_scene(slot, anarchy, db.light_scenes, recent=recent_light_ids)
    if sound_id and recent_sound_ids is not None:
        recent_sound_ids.append(sound_id)
    if light_scene and recent_light_ids is not None:
        recent_light_ids.append(light_scene.id)
    return CuePoint(
        trigger=CuePointTrigger.KEYWORD,
        keyword=keyword,
        sentence_index=sentence_index,
        function=fn,
        intensity=round(anarchy, 3),
        sound=(
            SoundCue(
                action=SoundAction.TRIGGER_CUE,
                cue_id=sound_id,
                volume=sound_volume_for_anarchy(anarchy),
            )
            if sound_id
            else None
        ),
        light=(
            LightCue(
                scene_id=light_scene.id,
                fade_time=light_fade_seconds(light_scene.fade_time, anarchy),
                intensity=round(0.25 + anarchy * 0.75, 2),
            )
            if light_scene
            else None
        ),
    )


def apply_anarchy_to_keyword_cue_point(
    point: CuePoint,
    keyword: str,
    script_text: str,
    sentences: list[str],
    curve: AnarchyCurve,
    media_db: MediaDatabase | None = None,
    *,
    slot: int = 0,
    recent_sound_ids: list[str] | None = None,
) -> CuePoint | None:
    if not keyword_in_script(keyword, script_text):
        return None
    offset = find_char_offset_for_keyword(keyword, script_text) or 0
    anarchy = anarchy_for_char_offset(offset, len(script_text), curve)
    sentence_index = find_sentence_index_for_keyword(keyword, sentences)
    point = point.model_copy(deep=True)
    point.trigger = CuePointTrigger.KEYWORD
    point.keyword = keyword
    point.sentence_index = sentence_index
    point.intensity = round(anarchy, 3)
    point.function = anarchy_function(anarchy)
    if point.visual:
        point.visual = None
    current_id = point.sound.cue_id if point.sound else None
    if not is_playable_sound_id(current_id):
        db = media_db or MediaDatabase()
        sound_id = pick_sound_id(slot, anarchy, db.dramaturgy_sounds, recent=recent_sound_ids)
        if sound_id:
            point.sound = SoundCue(
                action=SoundAction.TRIGGER_CUE,
                cue_id=sound_id,
                volume=sound_volume_for_anarchy(anarchy),
            )
            if recent_sound_ids is not None:
                recent_sound_ids.append(sound_id)
        else:
            point.sound = None
    elif point.sound:
        point.sound.volume = sound_volume_for_anarchy(anarchy)
        if recent_sound_ids is not None and current_id and current_id not in recent_sound_ids:
            recent_sound_ids.append(current_id)
    if point.light:
        if point.light.intensity is None:
            point.light.intensity = round(0.25 + anarchy * 0.75, 2)
        point.light.fade_time = light_fade_seconds(point.light.fade_time or 4.0, anarchy)
    return point


def min_keyword_cues_for_script(script_text: str) -> int:
    return max(20, min(120, len(script_text) // 180))


def max_keywords_per_chunk(chunk_text: str) -> int:
    return max(10, min(28, len(chunk_text) // 140))


def min_keywords_per_chunk(chunk_text: str) -> int:
    return max(6, min(18, len(chunk_text) // 250))


def _unused_token_from_sentence(sentence: str, used_normalized: set[str]) -> str | None:
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß]{4,}", sentence)
    for token in tokens:
        norm = _normalize(token)
        if len(norm) >= 4 and norm not in used_normalized:
            return token
    return None


def densify_keyword_sound_cues(
    points: list[CuePoint],
    script_text: str,
    sentences: list[str],
    curve: AnarchyCurve,
    media_db: MediaDatabase | None = None,
    *,
    max_gap_sentences: int = 2,
) -> list[CuePoint]:
    """Insert sound-only keyword cues so playable starts are never far apart."""
    if not sentences:
        return points
    db = media_db or MediaDatabase()
    if not playable_dramaturgy_sounds(db.dramaturgy_sounds):
        return points

    used = {_normalize(point.keyword or "") for point in points if point.keyword}
    recent_sounds = [
        point.sound.cue_id
        for point in points
        if point.sound and is_playable_sound_id(point.sound.cue_id)
    ]
    covered = sorted(
        {
            point.sentence_index
            for point in points
            if point.sentence_index is not None
            and point.sound
            and is_playable_sound_id(point.sound.cue_id)
        }
    )
    extras: list[CuePoint] = []
    markers = [-1, *covered, len(sentences)]
    slot = len(points)
    for left, right in zip(markers, markers[1:]):
        idx = left + max_gap_sentences
        while idx < right:
            keyword = _unused_token_from_sentence(sentences[idx], used)
            if keyword and keyword_in_script(keyword, script_text):
                used.add(_normalize(keyword))
                extra = build_keyword_cue_point(
                    keyword,
                    idx,
                    anarchy_at(idx, len(sentences), curve),
                    db,
                    slot=slot,
                    recent_sound_ids=recent_sounds,
                )
                extra.light = None
                extras.append(extra)
                slot += 1
            idx += max_gap_sentences

    merged = [*points, *extras]
    merged.sort(key=lambda point: (point.sentence_index or 0, point.keyword or ""))
    return merged
