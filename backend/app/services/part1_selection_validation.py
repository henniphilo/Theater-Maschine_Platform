from __future__ import annotations

from app.director.media.database import MediaDatabase
from app.schemas.part1_selection import (
    MIN_FINAL_LIGHTS,
    MIN_FINAL_MUSIC,
    MIN_FINAL_SOUNDS,
    MIN_FINAL_VIDEOS,
    MediaSelectionLists,
    Part1BaerenklauSelection,
)
from app.services.sound_cue_catalog import get_sound_cue_catalog_service
from app.services.video_cue_catalog import get_video_cue_catalog_service


class Part1SelectionValidationError(ValueError):
    pass


def _music_cue_ids() -> set[str]:
    catalog = get_sound_cue_catalog_service().load()
    ids: set[str] = set()
    for cue in catalog.cues:
        tags = {t.lower() for t in cue.tags}
        if "musik" in tags or "music" in tags:
            ids.add(cue.id)
    return ids


def _play_sound_ids() -> set[str]:
    catalog = get_sound_cue_catalog_service().load()
    return {c.id for c in catalog.cues if c.action == "play"}


def _video_clip_ids() -> set[str]:
    catalog = get_video_cue_catalog_service().load()
    return {c.id for c in catalog.clips}


def _light_scene_ids() -> set[str]:
    return {s.id for s in MediaDatabase().light_scenes}


def validate_media_lists(lists: MediaSelectionLists, *, require_minimums: bool = True) -> MediaSelectionLists:
    play_sounds = _play_sound_ids()
    music_ids = _music_cue_ids()
    video_ids = _video_clip_ids()
    light_ids = _light_scene_ids()

    unknown_sounds = [s for s in lists.sounds if s not in play_sounds]
    unknown_music = [m for m in lists.music if m not in play_sounds]
    unknown_videos = [v for v in lists.videos if v not in video_ids]
    unknown_lights = [l for l in lists.lights if l not in light_ids]

    errors: list[str] = []
    if unknown_sounds:
        errors.append(f"Unbekannte Sounds: {unknown_sounds}")
    if unknown_music:
        errors.append(f"Unbekannte Musik-Cues: {unknown_music}")
    if unknown_videos:
        errors.append(f"Unbekannte Videos: {unknown_videos}")
    if unknown_lights:
        errors.append(f"Unbekannte Lichtstimmungen: {unknown_lights}")

    if music_ids:
        non_music = [m for m in lists.music if m not in music_ids]
        if non_music:
            errors.append(f"Musik-Cues müssen Tag musik/music haben: {non_music}")

    if require_minimums:
        if len(lists.sounds) < MIN_FINAL_SOUNDS:
            errors.append(f"Mindestens {MIN_FINAL_SOUNDS} Sounds erforderlich")
        if len(lists.music) < MIN_FINAL_MUSIC:
            errors.append(f"Mindestens {MIN_FINAL_MUSIC} Musik-Cue erforderlich")
        if len(lists.videos) < MIN_FINAL_VIDEOS:
            errors.append(f"Mindestens {MIN_FINAL_VIDEOS} Videos erforderlich")
        if len(lists.lights) < MIN_FINAL_LIGHTS:
            errors.append(f"Mindestens {MIN_FINAL_LIGHTS} Lichtstimmungen erforderlich")

    if errors:
        raise Part1SelectionValidationError("; ".join(errors))

    return lists


def validate_part1_selection(selection: Part1BaerenklauSelection) -> Part1BaerenklauSelection:
    validate_media_lists(
        MediaSelectionLists(
            sounds=selection.final_sounds,
            music=selection.final_music,
            videos=selection.final_videos,
            lights=selection.final_lights,
        )
    )
    return selection
