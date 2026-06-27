"""Build Part 1 media selection from dramaturg discussion mentions."""

from __future__ import annotations

from app.schemas.discussion import DiscussionTurn
from app.schemas.media_mentions import MediaMention
from app.schemas.part1_selection import (
    MIN_FINAL_LIGHTS,
    MIN_FINAL_MUSIC,
    MIN_FINAL_SOUNDS,
    MIN_FINAL_VIDEOS,
    MediaSelectionLists,
)
from app.services.catalog_media_resolver import get_catalog_media_matcher
from app.services.preview_executor import fallback_baerenklau_selection_from_catalog


def _unique_ordered(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in ids:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def collect_mentions_from_turns(turns: list[DiscussionTurn]) -> list[MediaMention]:
    mentions: list[MediaMention] = []
    for turn in turns:
        mentions.extend(turn.media_mentions)
    return mentions


def lists_from_mentions(mentions: list[MediaMention]) -> MediaSelectionLists:
    sounds: list[str] = []
    music: list[str] = []
    videos: list[str] = []
    lights: list[str] = []
    for mention in mentions:
        if mention.medium == "sound":
            sounds.append(mention.media_id)
        elif mention.medium == "music":
            music.append(mention.media_id)
        elif mention.medium == "video":
            videos.append(mention.media_id)
        elif mention.medium == "light":
            lights.append(mention.media_id)
    return MediaSelectionLists(
        sounds=_unique_ordered(sounds),
        music=_unique_ordered(music),
        videos=_unique_ordered(videos),
        lights=_unique_ordered(lights),
    )


def _fill_from_catalog(
    lists: MediaSelectionLists,
    scene_text: str,
    mood_queries: list[str],
) -> MediaSelectionLists:
    matcher = get_catalog_media_matcher()
    sounds = list(lists.sounds)
    music = list(lists.music)
    videos = list(lists.videos)
    lights = list(lists.lights)
    queries = mood_queries + [scene_text[:500]]
    for query in queries:
        if len(sounds) >= MIN_FINAL_SOUNDS and len(music) >= MIN_FINAL_MUSIC:
            if len(videos) >= MIN_FINAL_VIDEOS and len(lights) >= MIN_FINAL_LIGHTS:
                break
        if len(sounds) < MIN_FINAL_SOUNDS:
            sid = matcher.best_sound(query, exclude=set(sounds))
            if sid:
                sounds.append(sid)
        if len(music) < MIN_FINAL_MUSIC:
            mid = matcher.best_sound(query, music=True, exclude=set(music))
            if mid:
                music.append(mid)
        if len(videos) < MIN_FINAL_VIDEOS:
            vid = matcher.best_video(query, exclude=set(videos))
            if vid:
                videos.append(vid)
        if len(lights) < MIN_FINAL_LIGHTS:
            lid = matcher.best_light(query, exclude=set(lights))
            if lid:
                lights.append(lid)
    return MediaSelectionLists(
        sounds=_unique_ordered(sounds),
        music=_unique_ordered(music),
        videos=_unique_ordered(videos),
        lights=_unique_ordered(lights),
    )


def _has_minimums(lists: MediaSelectionLists) -> bool:
    return (
        len(lists.sounds) >= MIN_FINAL_SOUNDS
        and len(lists.music) >= MIN_FINAL_MUSIC
        and len(lists.videos) >= MIN_FINAL_VIDEOS
        and len(lists.lights) >= MIN_FINAL_LIGHTS
    )


def build_selection_from_discussion(
    turns: list[DiscussionTurn],
    scene_text: str,
    *,
    json_fallback: MediaSelectionLists | None = None,
) -> MediaSelectionLists:
    """Derive final media lists from mood mentions, catalog fill, then JSON/fallback."""
    mentions = collect_mentions_from_turns(turns)
    lists = lists_from_mentions(mentions)
    mood_queries = [
        m.keyword or ""
        for m in mentions
        if m.keyword
    ]
    if not _has_minimums(lists):
        lists = _fill_from_catalog(lists, scene_text, mood_queries)

    if json_fallback is not None:
        if len(lists.sounds) < MIN_FINAL_SOUNDS and json_fallback.sounds:
            lists.sounds = _unique_ordered(lists.sounds + json_fallback.sounds)
        if len(lists.music) < MIN_FINAL_MUSIC and json_fallback.music:
            lists.music = _unique_ordered(lists.music + json_fallback.music)
        if len(lists.videos) < MIN_FINAL_VIDEOS and json_fallback.videos:
            lists.videos = _unique_ordered(lists.videos + json_fallback.videos)
        if len(lists.lights) < MIN_FINAL_LIGHTS and json_fallback.lights:
            lists.lights = _unique_ordered(lists.lights + json_fallback.lights)

    if not _has_minimums(lists):
        fb_sounds, fb_music, fb_videos, fb_lights = fallback_baerenklau_selection_from_catalog()
        lists = MediaSelectionLists(
            sounds=_unique_ordered(lists.sounds + fb_sounds),
            music=_unique_ordered(lists.music + fb_music),
            videos=_unique_ordered(lists.videos + fb_videos),
            lights=_unique_ordered(lists.lights + fb_lights),
        )
    return lists
