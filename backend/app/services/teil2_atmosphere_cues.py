"""Inject atmosphere video cues (Ohne Avatare) into Teil-2 sentence dramaturgy."""

from __future__ import annotations

from app.director.cues.cue_models import CuePoint, DramaturgyDecision, VisualCue, VisualOutputAssignment
from app.schemas.inszenierung import AnarchyCurve, AvatarTextSegment
from app.services.teil2_projector_assignment import pick_atmosphere_projectors
from app.services.video_scope import _clip_ids_for_scope

# Prefer clips that read clearly as B-roll on side beamers.
_PREFERRED_ATMOSPHERE_CLIPS: tuple[str, ...] = (
    "clyde",
    "strand",
    "affenslowodysee2001",
    "bitcoinfahrt",
    "derhaseverlaesstdiebuehne",
    "esellaeuft2705",
    "fischundwassergewaechs",
    "gehirn",
    "hierunterdererde",
    "kuscheltierschlachtung",
    "mehlwuermerlangsam",
    "wasserfahrt",
    "black",
)


def _anarchy_at(sentence_index: int, total: int, curve: AnarchyCurve) -> float:
    if total <= 1:
        return curve.end
    t = sentence_index / (total - 1)
    return curve.start + (curve.end - curve.start) * t


def _atmosphere_clip_pool(*, avatar_clip_ids: set[str]) -> list[str]:
    allowed = _clip_ids_for_scope("part1")
    ordered: list[str] = []
    for clip_id in _PREFERRED_ATMOSPHERE_CLIPS:
        if clip_id in allowed and clip_id not in avatar_clip_ids:
            ordered.append(clip_id)
    for clip_id in sorted(allowed):
        if clip_id not in avatar_clip_ids and clip_id not in ordered:
            ordered.append(clip_id)
    return ordered


def _reserved_projectors_at_sentence(
    segments: list[AvatarTextSegment],
    sentence_index: int,
) -> set[str]:
    reserved: set[str] = set()
    for segment in segments:
        if segment.start_sentence_index != sentence_index:
            continue
        for layer in segment.avatar_layers:
            if layer.projector:
                reserved.add(layer.projector)
            for output in layer.outputs or []:
                reserved.add(output.output_id)
    return reserved


def _assign_atmosphere_visual(clip_id: str, projector: str) -> VisualCue:
    return VisualCue(
        clip_id=clip_id,
        video_type="atmosphere",
        projector=projector,  # type: ignore[arg-type]
        blend_mode="layer",
        lock_until_finished=False,
        can_be_interrupted=True,
        outputs=[VisualOutputAssignment(output_id=projector, clip_id=clip_id)],
    )


def inject_atmosphere_visuals(
    decision: DramaturgyDecision,
    *,
    sentences: list[str],
    segments: list[AvatarTextSegment],
    curve: AnarchyCurve,
    avatar_clip_ids: set[str],
    every_n_sentences: int = 2,
) -> DramaturgyDecision:
    """Add B-roll visuals from OSCBefehllisteOhneAvatare on free beamers."""
    pool = _atmosphere_clip_pool(avatar_clip_ids=avatar_clip_ids)
    if decision.visual and decision.visual.clip_id in avatar_clip_ids:
        decision.visual = None

    if not pool or not decision.cue_points:
        return decision

    total = len(sentences)
    clip_index = 0
    for point in decision.cue_points:
        if point.visual and point.visual.clip_id:
            continue
        sentence_index = point.sentence_index
        if sentence_index is None or sentence_index >= total:
            continue
        anarchy = _anarchy_at(sentence_index, total, curve)
        if anarchy < 0.2:
            continue
        if sentence_index % every_n_sentences != 1:
            continue
        reserved = _reserved_projectors_at_sentence(segments, sentence_index)
        projector = pick_atmosphere_projectors(1, reserved=reserved, seed=sentence_index)[0]
        clip_id = pool[clip_index % len(pool)]
        clip_index += 1
        point.visual = _assign_atmosphere_visual(clip_id, projector)

    return decision
