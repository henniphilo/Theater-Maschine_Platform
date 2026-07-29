"""Build script + cue overview for Teil 2 performance plans."""

from __future__ import annotations

from app.director.cues.cue_models import CuePoint, CuePointTrigger, DramaturgyDecision
from app.schemas.inszenierung import (
    AvatarTextSegment,
    CueAnnotation,
    ScriptCueOverview,
    ScriptCueRow,
    Teil2PerformancePlan,
)
from app.services.teil2_anarchy_cues import find_sentence_index_for_keyword


def _visual_label(visual) -> tuple[str, str | None]:
    if visual is None:
        return "", None
    clip_id = visual.clip_id or ""
    projector = visual.projector
    if not projector and visual.outputs:
        projector = visual.outputs[0].output_id
    return clip_id, projector


def _sound_label(sound) -> str:
    if sound is None:
        return ""
    return sound.cue_id or ""


def _light_label(light) -> str:
    if light is None:
        return ""
    if light.scene_ids:
        return "+".join(light.scene_ids)
    return light.scene_id or ""


def _annotation_reason(
    point: CuePoint,
    *,
    fallback: str | None = None,
    reason_short: str | None = None,
) -> str | None:
    if reason_short:
        return reason_short
    parts: list[str] = []
    if point.trigger == CuePointTrigger.KEYWORD and point.keyword:
        parts.append(f"Stichwort: {point.keyword}")
    if point.function:
        parts.append(point.function)
    if parts:
        return " · ".join(parts)
    return fallback


def _annotations_from_cue_point(
    point: CuePoint,
    *,
    reason: str | None = None,
    reason_short: str | None = None,
) -> list[CueAnnotation]:
    cue_reason = _annotation_reason(point, fallback=reason, reason_short=reason_short)
    annotations: list[CueAnnotation] = []
    clip_id, projector = _visual_label(point.visual)
    if clip_id:
        annotations.append(
            CueAnnotation(
                kind="video",
                label=clip_id,
                projector=projector,
                time_sec=point.time_offset_sec if point.trigger == CuePointTrigger.TIME else None,
                sentence_index=point.sentence_index,
                reason=cue_reason,
            )
        )
    sound_id = _sound_label(point.sound)
    if sound_id:
        annotations.append(
            CueAnnotation(
                kind="sound",
                label=sound_id,
                time_sec=point.time_offset_sec if point.trigger == CuePointTrigger.TIME else None,
                sentence_index=point.sentence_index,
                reason=cue_reason,
            )
        )
    light_id = _light_label(point.light)
    if light_id:
        annotations.append(
            CueAnnotation(
                kind="light",
                label=light_id,
                time_sec=point.time_offset_sec if point.trigger == CuePointTrigger.TIME else None,
                sentence_index=point.sentence_index,
                reason=cue_reason,
            )
        )
    return annotations


def _avatar_annotations_for_sentence(
    sentence_index: int,
    segments: list[AvatarTextSegment],
) -> list[CueAnnotation]:
    annotations: list[CueAnnotation] = []
    for segment in segments:
        if segment.start_sentence_index != sentence_index:
            continue
        for layer in segment.avatar_layers:
            projector = layer.projector
            if not projector and layer.outputs:
                projector = layer.outputs[0].output_id
            annotations.append(
                CueAnnotation(
                    kind="avatar",
                    label=f"{layer.avatar}:{layer.video_clip_id}",
                    projector=projector,
                    sentence_index=sentence_index,
                    reason=segment.text_excerpt[:80] if segment.text_excerpt else None,
                )
            )
    return annotations


def _sentence_index_for_point(
    point: CuePoint,
    sentences: list[str],
) -> int | None:
    if point.sentence_index is not None:
        return point.sentence_index
    if point.trigger == CuePointTrigger.KEYWORD and point.keyword:
        return find_sentence_index_for_keyword(point.keyword, sentences)
    return None


def build_cue_overview(
    sentences: list[str],
    dramaturgy: DramaturgyDecision,
    avatar_segments: list[AvatarTextSegment],
    atmosphere_cue_points: list[CuePoint],
    *,
    dramaturgy_reason: str | None = None,
) -> ScriptCueOverview:
    by_sentence: dict[int, list[CueAnnotation]] = {index: [] for index in range(len(sentences))}

    for point in dramaturgy.cue_points:
        if point.trigger == CuePointTrigger.TIME:
            continue
        index = _sentence_index_for_point(point, sentences)
        if index is None or index < 0 or index >= len(sentences):
            continue
        by_sentence[index].extend(
            _annotations_from_cue_point(
                point,
                reason=dramaturgy_reason or dramaturgy.reason,
                reason_short=dramaturgy.reason_short or None,
            )
        )

    for index in range(len(sentences)):
        by_sentence[index].extend(_avatar_annotations_for_sentence(index, avatar_segments))

    rows = [
        ScriptCueRow(
            sentence_index=index,
            text=sentences[index],
            annotations=by_sentence.get(index, []),
        )
        for index in range(len(sentences))
    ]

    atmosphere_timeline: list[CueAnnotation] = []
    for point in atmosphere_cue_points:
        atmosphere_timeline.extend(
            _annotations_from_cue_point(point, reason="Atmosphäre (parallel)")
        )

    atmosphere_timeline.sort(key=lambda item: item.time_sec or 0.0)

    return ScriptCueOverview(rows=rows, atmosphere_timeline=atmosphere_timeline)


def build_overview_for_plan(plan: Teil2PerformancePlan) -> ScriptCueOverview:
    return build_cue_overview(
        plan.sentences,
        plan.dramaturgy,
        plan.avatar_segments,
        plan.atmosphere_cue_points,
        dramaturgy_reason=plan.dramaturgy.reason,
    )
