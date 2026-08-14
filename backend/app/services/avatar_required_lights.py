"""Hard staging rules: some avatar clips require a light scene to stay on."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    DramaturgyDecision,
    LightAction,
    LightCue,
    resolve_light_scene_ids,
)
from app.director.cues.projector_state import ProjectorState
from app.director.outputs.light_scene_tracker import active_light_scene_ids
from app.schemas.inszenierung import AvatarTextSegment

# Pixera scene_ref / catalog clip_id → light scene_ids that must remain on.
AVATAR_REQUIRED_LIGHT_SCENES: dict[str, tuple[str, ...]] = {
    "sch4_thomas": ("klaviertasten",),
    "wo2_branko": ("klaviertasten",),
}


def normalize_avatar_clip_key(clip_id: str | None) -> str:
    if not clip_id:
        return ""
    token = clip_id.strip().split(".")[-1]
    return token.lower().replace("-", "_")


def required_light_scenes_for_clip(clip_id: str | None) -> tuple[str, ...]:
    return AVATAR_REQUIRED_LIGHT_SCENES.get(normalize_avatar_clip_key(clip_id), ())


def required_light_scenes_for_clips(clip_ids: Iterable[str | None]) -> list[str]:
    scenes: list[str] = []
    for clip_id in clip_ids:
        for scene_id in required_light_scenes_for_clip(clip_id):
            if scene_id not in scenes:
                scenes.append(scene_id)
    return scenes


def _clip_ids_from_visual(visual) -> list[str]:
    if visual is None:
        return []
    ids: list[str] = []
    if visual.clip_id:
        ids.append(visual.clip_id)
    for assignment in visual.outputs or []:
        if assignment.clip_id:
            ids.append(assignment.clip_id)
    return ids


def _clip_ids_from_decision(decision: DramaturgyDecision) -> list[str]:
    ids = _clip_ids_from_visual(decision.visual)
    for point in decision.cue_points:
        ids.extend(_clip_ids_from_visual(point.visual))
    return ids


def required_light_scenes_from_locked_avatars(
    projectors: ProjectorState | None,
    *,
    now: datetime | None = None,
) -> list[str]:
    if projectors is None:
        return []
    moment = now or datetime.now(UTC)
    clip_ids: list[str] = []
    for slot in projectors.slots.values():
        if slot.video_type != "avatar" or not slot.active_clip_id:
            continue
        if not slot.is_locked(moment):
            continue
        clip_ids.append(slot.active_clip_id)
    return required_light_scenes_for_clips(clip_ids)


def _is_blackout(light: LightCue | None) -> bool:
    if light is None:
        return False
    action = light.action.value if isinstance(light.action, LightAction) else str(light.action)
    if action == LightAction.FADE_BLACKOUT.value:
        return True
    scenes = resolve_light_scene_ids(light)
    return light.scene_id == "blackout" or scenes == ["blackout"]


def _light_with_scenes(scenes: Sequence[str], *, base: LightCue | None = None) -> LightCue:
    unique = [scene_id for scene_id in scenes if scene_id]
    if base is None:
        return LightCue(
            scene_id=unique[0] if len(unique) == 1 else None,
            scene_ids=list(unique) if len(unique) > 1 else [],
            fade_time=2.0,
            replace_previous=True,
        )
    if len(unique) <= 1:
        return base.model_copy(
            update={"scene_id": unique[0] if unique else base.scene_id, "scene_ids": []}
        )
    return base.model_copy(update={"scene_ids": list(unique), "scene_id": None})


def merge_required_light_scenes(
    light: LightCue | None,
    required: Sequence[str],
    *,
    keep_active: bool = False,
) -> LightCue:
    current = resolve_light_scene_ids(light)
    if keep_active:
        current = list(dict.fromkeys([*active_light_scene_ids(), *current]))
    merged = list(dict.fromkeys([*current, *required]))
    return _light_with_scenes(merged, base=light)


def apply_avatar_required_lights(
    decision: DramaturgyDecision,
    projectors: ProjectorState | None = None,
    *,
    now: datetime | None = None,
) -> DramaturgyDecision:
    """Ensure required lights are attached when piano avatars play or stay locked."""
    from_clips = required_light_scenes_for_clips(_clip_ids_from_decision(decision))
    from_locked = required_light_scenes_from_locked_avatars(projectors, now=now)
    required = list(dict.fromkeys([*from_clips, *from_locked]))
    if not required:
        return decision

    updated = decision.model_copy(deep=True)
    intensity = updated.light.intensity if updated.light is not None else None
    if _is_blackout(updated.light) or (intensity is not None and intensity <= 0.0):
        return updated

    if updated.light is not None:
        updated.light = merge_required_light_scenes(updated.light, required)
    elif from_clips:
        updated.light = merge_required_light_scenes(None, required, keep_active=True)

    if updated.cue_points:
        new_points: list[CuePoint] = []
        for point in updated.cue_points:
            if point.light is None or _is_blackout(point.light):
                new_points.append(point)
                continue
            if (point.light.intensity or 1.0) <= 0.0:
                new_points.append(point)
                continue
            new_points.append(
                point.model_copy(update={"light": merge_required_light_scenes(point.light, required)})
            )
        updated.cue_points = new_points
    return updated


def _segment_required_scenes(segment: AvatarTextSegment) -> list[str]:
    clip_ids = [layer.video_clip_id for layer in segment.avatar_layers]
    clip_ids.extend(segment.csv_cue_ids)
    return required_light_scenes_for_clips(clip_ids)


def apply_required_lights_to_plan(
    decision: DramaturgyDecision,
    segments: Sequence[AvatarTextSegment],
) -> DramaturgyDecision:
    """Merge/inject klaviertasten into overlapping Teil-2 light cues for the overview."""
    updated = decision.model_copy(deep=True)
    points = list(updated.cue_points)
    for segment in segments:
        required = _segment_required_scenes(segment)
        if not required:
            continue
        start = segment.start_sentence_index
        end = segment.end_sentence_index
        matched = False
        for index, point in enumerate(points):
            if point.light is None or _is_blackout(point.light):
                continue
            sentence_index = point.sentence_index
            if sentence_index is None:
                continue
            if start <= sentence_index <= end:
                points[index] = point.model_copy(
                    update={"light": merge_required_light_scenes(point.light, required)}
                )
                matched = True
        if not matched:
            points.append(
                CuePoint(
                    trigger=CuePointTrigger.SENTENCE_END,
                    sentence_index=start,
                    function="halten",
                    intensity=0.7,
                    light=_light_with_scenes(required),
                )
            )
    updated.cue_points = points
    return updated
