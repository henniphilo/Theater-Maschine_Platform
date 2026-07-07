"""Rule-Engine-Dramaturgie pro Skript-Beat (Teil 2)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.director.cues.cue_models import CuePoint, CuePointTrigger, DramaturgyDecision, VisualCue, VisualOutputAssignment
from app.director.dialogue.builder import build_dialogue_event
from app.director.dramaturgy.llm_director import LLMDirector
from app.director.outputs.osc_commands import build_osc_commands
from app.schemas.inszenierung import CompositionMoment, Gesamtkonzept
from app.services.inszenierung_validation import dramaturgy_with_anarchy
from app.services.teil2_projector_assignment import pick_atmosphere_projectors

_ATMOSPHERE_CLIPS = ("clyde", "strand", "black", "maschinen_grundader")


def build_dramaturgy_for_beat(
    moment: CompositionMoment,
    *,
    title: str = "Unter Tieren — Geld",
    gesamtkonzept: Gesamtkonzept | None = None,
    llm_director: LLMDirector | None = None,
) -> DramaturgyDecision:
    director = llm_director or LLMDirector()
    context = gesamtkonzept.discussion_summary if gesamtkonzept else ""
    event = build_dialogue_event(
        speaker="openai",
        text=moment.text_excerpt,
        topic=title,
        created_at=datetime.now(UTC),
    )
    try:
        decision = director.rule_engine.decide(event)
    except Exception:
        decision = DramaturgyDecision(
            reason="Teil-2 Skript-Beat",
            tags=["teil2", "avatar_script"],
            mood="tension",
            intensity=moment.anarchy_level,
        )

    if context:
        decision.reason = f"{decision.reason} — {context[:120]}"

    decision = dramaturgy_with_anarchy(decision, moment.anarchy_level)
    decision.intensity = max(decision.intensity, moment.anarchy_level * 0.9)

    _apply_atmosphere_to_decision(decision, moment)
    _ensure_cue_points(decision, moment)
    _route_dramaturgy_away_from_avatar_projectors(decision, moment)

    build_osc_commands(decision, dry_run=True, video_scope="part2")
    return decision


def _avatar_reserved_projectors(moment: CompositionMoment) -> set[str]:
    reserved: set[str] = set()
    for layer in moment.avatar_layers or []:
        if layer.projector:
            reserved.add(layer.projector)
        for output in layer.outputs or []:
            reserved.add(output.output_id)
    if moment.avatar_video_cue:
        if moment.avatar_video_cue.projector:
            reserved.add(moment.avatar_video_cue.projector)
        for output in moment.avatar_video_cue.outputs or []:
            reserved.add(output.output_id)
    return reserved


def _pick_dramaturgy_projectors(moment: CompositionMoment, count: int) -> list[str]:
    reserved = _avatar_reserved_projectors(moment)
    return pick_atmosphere_projectors(count, reserved=reserved, seed=moment.order)


def _assign_atmosphere_visual(visual: VisualCue, projector: str) -> VisualCue:
    clip_id = visual.clip_id
    return visual.model_copy(
        update={
            "video_type": "atmosphere",
            "projector": projector,  # type: ignore[arg-type]
            "lock_until_finished": False,
            "can_be_interrupted": True,
            "blend_mode": "layer",
            "outputs": [VisualOutputAssignment(output_id=projector, clip_id=clip_id)],
        }
    )


def _route_dramaturgy_away_from_avatar_projectors(
    decision: DramaturgyDecision,
    moment: CompositionMoment,
) -> None:
    """Keep avatar beamers free for avatar clips; route atmosphere/light/sound elsewhere."""
    avatar_clips = {layer.video_clip_id for layer in moment.avatar_layers or []}
    if moment.avatar_video_clip_id:
        avatar_clips.add(moment.avatar_video_clip_id)

    cue_count = max(1, len(decision.cue_points))
    dram_projectors = _pick_dramaturgy_projectors(moment, cue_count)

    if (
        decision.visual
        and decision.visual.clip_id
        and decision.visual.clip_id not in avatar_clips
        and decision.visual.video_type != "avatar"
    ):
        decision.visual = _assign_atmosphere_visual(decision.visual, dram_projectors[0])

    for index, point in enumerate(decision.cue_points):
        if not point.visual or not point.visual.clip_id:
            continue
        if point.visual.clip_id in avatar_clips or point.visual.video_type == "avatar":
            point.visual = None
            continue
        target = dram_projectors[index % len(dram_projectors)]
        point.visual = _assign_atmosphere_visual(point.visual, target)


def _ensure_cue_points(decision: DramaturgyDecision, moment: CompositionMoment) -> None:
    if decision.cue_points:
        if moment.anarchy_level > 0.65:
            for point in decision.cue_points:
                if point.function in ("verstärken", "überlagern"):
                    point.function = "überlagern"
                    point.intensity = max(point.intensity, moment.anarchy_level)
        return

    fn = "überlagern" if moment.anarchy_level > 0.6 else "verstärken"
    decision.cue_points = [
        CuePoint(
            trigger=CuePointTrigger.START,
            function=fn,
            intensity=moment.anarchy_level,
            visual=decision.visual,
            sound=decision.sound,
            light=decision.light,
        )
    ]
    if moment.anarchy_level >= 0.75:
        clip = _ATMOSPHERE_CLIPS[moment.order % len(_ATMOSPHERE_CLIPS)]
        reserved = _avatar_reserved_projectors(moment)
        targets = pick_atmosphere_projectors(1, reserved=reserved, seed=moment.order + 1)
        target = targets[0]
        decision.cue_points.append(
            CuePoint(
                trigger=CuePointTrigger.START,
                function="überlagern",
                intensity=min(1.0, moment.anarchy_level + 0.1),
                visual=_assign_atmosphere_visual(
                    VisualCue(clip_id=clip, blend_mode="layer"),
                    target,
                ),
                sound=decision.sound,
                light=decision.light,
            )
        )


def _apply_atmosphere_to_decision(decision: DramaturgyDecision, moment: CompositionMoment) -> None:
    atmosphere: list[VisualCue] = []
    avatar_clip = moment.avatar_video_clip_id

    if moment.anarchy_level >= 0.35 and decision.cue_points:
        reserved = _avatar_reserved_projectors(moment)
        atmosphere_projectors = [p for p in ("adam", "eva", "led", "rz21") if p not in reserved]
        if not atmosphere_projectors:
            atmosphere_projectors = ["rz21"]
        atmo_index = 0
        for point in decision.cue_points:
            if point.visual and point.visual.clip_id and point.visual.clip_id != avatar_clip:
                target = atmosphere_projectors[atmo_index % len(atmosphere_projectors)]
                atmo_index += 1
                atmo = _assign_atmosphere_visual(point.visual, target)
                atmosphere.append(atmo)
    moment.atmosphere_video_cues = atmosphere
