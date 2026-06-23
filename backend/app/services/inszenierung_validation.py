"""Validate and normalize composition excerpts for Teil 2."""

from __future__ import annotations

import re
import uuid

from app.director.cues.cue_models import DramaturgyDecision
from app.schemas.inszenierung import (
    AnimalScene,
    AnarchyCurve,
    CompositionMoment,
    CompositionPlan,
    Gesamtkonzept,
    SceneCorpus,
)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def excerpt_in_scene(scene: AnimalScene, excerpt: str) -> bool:
    if not excerpt.strip():
        return False
    hay = normalize_whitespace(scene.source_text)
    needle = normalize_whitespace(excerpt)
    return needle in hay


def find_scene(corpus: SceneCorpus, scene_id: str) -> AnimalScene | None:
    return next((s for s in corpus.scenes if s.id == scene_id), None)


def anarchy_level_for_index(index: int, total: int, curve: AnarchyCurve) -> float:
    if total <= 1:
        return curve.end
    t = index / (total - 1)
    return round(curve.start + (curve.end - curve.start) * t, 3)


def overlap_for_anarchy(anarchy_level: float) -> float:
    if anarchy_level <= 0.35:
        return 0.0
    if anarchy_level <= 0.55:
        return 0.15
    if anarchy_level <= 0.75:
        return 0.35
    return min(0.85, 0.45 + (anarchy_level - 0.75) * 1.6)


def apply_anarchy_curve(moments: list[CompositionMoment], curve: AnarchyCurve) -> list[CompositionMoment]:
    total = len(moments)
    for index, moment in enumerate(moments):
        level = anarchy_level_for_index(index, total, curve)
        moment.anarchy_level = level
        moment.overlap_with_previous = overlap_for_anarchy(level) if index > 0 else 0.0
        moment.order = index
    return moments


def validate_moment(moment: CompositionMoment, corpus: SceneCorpus) -> None:
    scene = find_scene(corpus, moment.scene_id)
    if scene is None:
        raise ValueError(f"Unknown scene_id: {moment.scene_id}")
    if moment.speech_mode != "silent" and not excerpt_in_scene(scene, moment.text_excerpt):
        raise ValueError(f"Excerpt not found in scene {scene.animal}: {moment.text_excerpt[:80]}…")
    if moment.speech_mode == "avatar_video":
        if not moment.avatar_speech_id and not moment.avatar_video_clip_id:
            raise ValueError("avatar_video moment needs avatar_speech_id or avatar_video_clip_id")


def validate_composition(plan: CompositionPlan, corpus: SceneCorpus) -> CompositionPlan:
    if not plan.moments:
        raise ValueError("Composition needs at least one moment")
    levels = [m.anarchy_level for m in plan.moments]
    for index in range(1, len(levels)):
        if levels[index] + 0.05 < levels[index - 1]:
            raise ValueError("anarchy_level must be non-decreasing")
    for moment in plan.moments:
        validate_moment(moment, corpus)
    return plan


def ensure_moment_ids(moments: list[CompositionMoment]) -> list[CompositionMoment]:
    for moment in moments:
        if not moment.id:
            moment.id = str(uuid.uuid4())
    return moments


def dramaturgy_with_anarchy(decision: DramaturgyDecision, anarchy_level: float) -> DramaturgyDecision:
    decision = decision.model_copy(deep=True)
    decision.intensity = max(decision.intensity, anarchy_level * 0.85)
    if decision.light and decision.light.intensity is None:
        decision.light.intensity = round(0.25 + anarchy_level * 0.75, 2)
    if decision.visual:
        decision.visual.opacity = min(1.0, round(0.55 + anarchy_level * 0.45, 2))
    if decision.sound:
        decision.sound.volume = min(1.0, round(0.35 + anarchy_level * 0.55, 2))
    return decision
