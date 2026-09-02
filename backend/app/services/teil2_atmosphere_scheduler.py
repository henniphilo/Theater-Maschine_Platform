"""LLM-driven time-based atmosphere video scheduling for Teil 2."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.core.config import settings
from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    DramaturgyDecision,
    VisualCue,
    VisualOutputAssignment,
)
from app.director.dramaturgy.llm_director import LLMDirector
from app.schemas.inszenierung import AnarchyCurve, AvatarTextSegment, Gesamtkonzept
from app.services.ai_service import AIService
from app.services.atmosphere_required_clips import (
    REQUIRED_RECURRING_ATMOSPHERE_CLIPS,
    available_recurring_clips,
    ensure_recurring_atmosphere_clips,
    pick_recurring_or_pool_clip,
)
from app.services.avatar_duration import estimate_duration_ms
from app.services.part2_cue_density import atmosphere_intervals_for_anarchy
from app.services.teil2_projector_assignment import (
    ALL_PROJECTORS,
    STAGE_BEAMER_ORDER,
    STAGE_ALWAYS_ATMOSPHERE,
    atmosphere_targets_for_free,
    pick_atmosphere_projectors,
)
from app.services.video_scope import atmosphere_clip_ids


@dataclass(frozen=True)
class AvatarWindow:
    start_sec: float
    end_sec: float
    projectors: frozenset[str]


def estimate_script_duration_sec(script_text: str, segments: list[AvatarTextSegment]) -> float:
    words = max(1, len(script_text.split()))
    from_words = words * 0.4
    from_segments = 0.0
    script_len = max(1, len(script_text))
    for segment in segments:
        offset = segment.char_offset or 0
        duration_ms = _segment_duration_ms(segment)
        start = (offset / script_len) * from_words
        from_segments = max(from_segments, start + duration_ms / 1000.0)
    return max(60.0, from_words, from_segments) + 15.0


def _segment_duration_ms(segment: AvatarTextSegment) -> int:
    duration_ms = 0
    for layer in segment.avatar_layers:
        visual = layer.visual_cue
        if visual and visual.duration_ms:
            duration_ms = max(duration_ms, visual.duration_ms)
    if duration_ms > 0:
        return duration_ms
    return estimate_duration_ms(segment.text_excerpt)


def build_avatar_windows(
    script_text: str,
    segments: list[AvatarTextSegment],
    total_sec: float,
) -> list[AvatarWindow]:
    script_len = max(1, len(script_text))
    windows: list[AvatarWindow] = []
    for segment in segments:
        offset = segment.char_offset or 0
        start = (offset / script_len) * total_sec
        end = start + _segment_duration_ms(segment) / 1000.0
        projectors: set[str] = set()
        for layer in segment.avatar_layers:
            if layer.projector:
                projectors.add(layer.projector)
            for output in layer.outputs or []:
                projectors.add(output.output_id)
        if projectors:
            windows.append(
                AvatarWindow(
                    start_sec=start,
                    end_sec=end,
                    projectors=frozenset(projectors),
                )
            )
    return windows


def reserved_projectors_at(windows: list[AvatarWindow], time_sec: float) -> set[str]:
    reserved: set[str] = set()
    for window in windows:
        if window.start_sec <= time_sec < window.end_sec:
            reserved |= set(window.projectors)
    return reserved


def free_projectors_at(windows: list[AvatarWindow], time_sec: float) -> list[str]:
    reserved = reserved_projectors_at(windows, time_sec)
    return [p for p in ALL_PROJECTORS if p not in reserved]


def _atmosphere_clip_pool(*, avatar_clip_ids: set[str]) -> list[str]:
    """Clyde/Bonnie first, then remaining Ohne-Avatare clips alphabetically."""
    allowed = atmosphere_clip_ids(avatar_clip_ids=avatar_clip_ids)
    preferred = [clip_id for clip_id in REQUIRED_RECURRING_ATMOSPHERE_CLIPS if clip_id in allowed]
    rest = sorted(clip_id for clip_id in allowed if clip_id not in preferred)
    return preferred + rest


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


def _parse_llm_cue_points(raw: str) -> list[CuePoint]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    points_raw = data.get("cue_points", data if isinstance(data, list) else [])
    return [CuePoint.model_validate(item) for item in points_raw]


def _validate_atmosphere_points(
    points: list[CuePoint],
    *,
    allowed_clips: set[str],
    allowed_projectors: set[str],
    max_time_sec: float,
) -> list[CuePoint]:
    from app.director.cues.cue_models import VisualAction

    validated: list[CuePoint] = []
    for point in points:
        if point.trigger != CuePointTrigger.TIME and str(point.trigger) != "time":
            continue
        if point.time_offset_sec < 0 or point.time_offset_sec > max_time_sec + 5:
            continue
        visual = point.visual
        if visual is None:
            continue
        action = visual.action
        is_release = action in {VisualAction.FADE_TO_BLACK, VisualAction.STOP_CLIP, "fade_to_black", "stop_clip"}
        projector = visual.projector
        if not projector and visual.outputs:
            projector = visual.outputs[0].output_id  # type: ignore[assignment]
        if projector and projector not in allowed_projectors:
            continue
        if is_release:
            validated.append(
                CuePoint(
                    trigger=CuePointTrigger.TIME,
                    time_offset_sec=round(point.time_offset_sec, 2),
                    function=point.function or "release",
                    intensity=point.intensity,
                    visual=VisualCue(
                        action=VisualAction.FADE_TO_BLACK
                        if "fade" in str(getattr(action, "value", action))
                        else VisualAction.STOP_CLIP,
                        fade_time=visual.fade_time or 3.0,
                        projector=projector,
                    ),
                )
            )
            continue
        if not visual.clip_id:
            continue
        if visual.clip_id not in allowed_clips:
            continue
        if projector not in allowed_projectors:
            continue
        validated.append(
            CuePoint(
                trigger=CuePointTrigger.TIME,
                time_offset_sec=round(point.time_offset_sec, 2),
                function=point.function or "atmosphaere",
                intensity=point.intensity,
                visual=_assign_atmosphere_visual(visual.clip_id, projector),  # type: ignore[arg-type]
            )
        )
    validated.sort(key=lambda item: item.time_offset_sec)
    return validated


def _anarchy_at_time(time_sec: float, total_sec: float, curve: AnarchyCurve) -> float:
    if total_sec <= 0:
        return curve.end
    t = max(0.0, min(1.0, time_sec / total_sec))
    return curve.start + (curve.end - curve.start) * t


def atmosphere_fill_count(free_count: int, anarchy: float) -> int:
    """Legacy helper: how many free beamers get Begleitvideo (anarchy escalation).

    Prefer ``atmosphere_targets_for_free`` — Adam/Eva are always filled when free.
    """
    if free_count <= 0:
        return 0
    # Approximate: always prefer at least the two stage beamers when available.
    always = min(2, free_count)
    others = max(0, free_count - always)
    if anarchy < 0.35:
        return always + min(1, others)
    if anarchy < 0.55:
        return always + min(1, others)
    return free_count


def _ordered_free_projectors(free: list[str], *, seed: int) -> list[str]:
    """Rotate STAGE_BEAMER_ORDER so Adam/Eva stay preferred but don't stick."""
    ordered = [p for p in STAGE_BEAMER_ORDER if p in free]
    if not ordered:
        return list(free)
    start = seed % len(ordered)
    return ordered[start:] + ordered[:start]


def _fill_free_projectors_at(
    *,
    time_sec: float,
    free: list[str],
    anarchy: float,
    pool: list[str],
    clip_index: int,
) -> tuple[list[CuePoint], int]:
    """Place distinct Begleitclips on free beamers for one time tick.

    Adam/Eva always get atmosphere when free; other free beamers escalate with anarchy.
    """
    if not free or not pool:
        return [], clip_index

    tick_seed = int(time_sec * 10) + clip_index
    targets = atmosphere_targets_for_free(free, anarchy=anarchy, seed=tick_seed)
    if not targets:
        return [], clip_index

    # At high anarchy we previously filled *all* additional free beamers in the same tick.
    # To make durations feel less "synchronized", keep Adam/Eva always and only rotate *one*
    # of the other free surfaces when chaos gets high.
    #
    # This creates parallel "longer" vs "shorter" atmosphere clips across rz21 vs led
    # (or whatever other free surfaces are available).
    if anarchy >= 0.8:
        always = set(STAGE_ALWAYS_ATMOSPHERE)
        other_targets = [p for p in targets if p not in always]
        if len(other_targets) > 1:
            ordered_others = [p for p in STAGE_BEAMER_ORDER if p in other_targets]
            keep_other = ordered_others[tick_seed % len(ordered_others)]
            targets = [p for p in targets if p in always or p == keep_other]

    points: list[CuePoint] = []
    next_index = clip_index
    for projector in targets:
        clip_id = pick_recurring_or_pool_clip(pool, next_index)
        next_index += 1
        points.append(
            CuePoint(
                trigger=CuePointTrigger.TIME,
                time_offset_sec=round(time_sec, 2),
                function="atmosphaere",
                intensity=round(max(0.35, min(1.0, anarchy)), 2),
                visual=_assign_atmosphere_visual(clip_id, projector),
            )
        )
    return points, next_index


def _rule_based_atmosphere_points(
    *,
    script_text: str,
    sentences: list[str],
    segments: list[AvatarTextSegment],
    curve: AnarchyCurve,
    avatar_clip_ids: set[str],
    dramaturgy: DramaturgyDecision,
) -> list[CuePoint]:
    """Walk the show timeline and fill free (non-avatar) beamers with B-roll.

    Density and how many free surfaces get a clip both escalate with the anarchy curve.
    ``sentences`` / ``dramaturgy`` are unused but kept for call-site compatibility.
    """
    _ = (sentences, dramaturgy)
    pool = _atmosphere_clip_pool(avatar_clip_ids=avatar_clip_ids)
    if not pool:
        return []

    total_sec = estimate_script_duration_sec(script_text, segments)
    windows = build_avatar_windows(script_text, segments, total_sec)
    points: list[CuePoint] = []
    clip_index = 0
    time_sec = 0.0

    while time_sec < total_sec:
        anarchy = _anarchy_at_time(time_sec, total_sec, curve)
        video_min, video_max = atmosphere_intervals_for_anarchy(anarchy)

        base_step = max(2.5, (video_min + video_max) / 2.0)
        # Give the beginning a slightly more "breathing" duration, so the first atmosphere
        # clips stand a bit longer before the first overwrite tick.
        early_phase_end = min(25.0, total_sec * 0.25)
        early_multiplier = 1.35 if time_sec < early_phase_end else 1.0
        step = base_step * early_multiplier

        free = free_projectors_at(windows, time_sec)
        batch, clip_index = _fill_free_projectors_at(
            time_sec=time_sec,
            free=free,
            anarchy=anarchy,
            pool=pool,
            clip_index=clip_index,
        )
        points.extend(batch)
        time_sec += step

    points.sort(key=lambda item: item.time_offset_sec)
    return points


def _expand_points_onto_free_projectors(
    points: list[CuePoint],
    *,
    windows: list[AvatarWindow],
    curve: AnarchyCurve,
    total_sec: float,
    allowed_clips: set[str],
) -> list[CuePoint]:
    """Ensure each atmosphere tick also covers other free beamers (LLM densify)."""
    preferred = [clip_id for clip_id in REQUIRED_RECURRING_ATMOSPHERE_CLIPS if clip_id in allowed_clips]
    pool = preferred + sorted(clip_id for clip_id in allowed_clips if clip_id not in preferred)
    if not pool:
        return points

    by_time: dict[float, list[CuePoint]] = {}
    for point in points:
        by_time.setdefault(point.time_offset_sec, []).append(point)

    expanded: list[CuePoint] = []
    clip_index = 0
    for time_sec in sorted(by_time):
        group = by_time[time_sec]
        used = set()
        for point in group:
            visual = point.visual
            if visual is None:
                continue
            projector = visual.projector
            if not projector and visual.outputs:
                projector = visual.outputs[0].output_id  # type: ignore[assignment]
            if projector:
                used.add(projector)
            if visual.clip_id:
                expanded.append(point)

        free = [p for p in free_projectors_at(windows, time_sec) if p not in used]
        anarchy = _anarchy_at_time(time_sec, total_sec, curve)
        # Fill remaining free beamers up to the Adam/Eva + anarchy target set.
        target_set = set(
            atmosphere_targets_for_free(
                list(used) + free,
                anarchy=max(anarchy, 0.55),
                seed=int(time_sec * 10),
            )
        )
        need_projectors = [p for p in target_set if p not in used and p in free]
        if not need_projectors:
            continue
        batch, clip_index = _fill_free_projectors_at(
            time_sec=time_sec,
            free=need_projectors,
            anarchy=max(anarchy, 0.55),
            pool=pool,
            clip_index=clip_index,
        )
        expanded.extend(batch)

    expanded.sort(key=lambda item: item.time_offset_sec)
    return expanded


def _timeline_summary(windows: list[AvatarWindow], total_sec: float) -> str:
    lines = [f"Gesamtdauer geschätzt: {total_sec:.0f}s"]
    for window in windows[:40]:
        proj = ", ".join(sorted(window.projectors))
        lines.append(f"  {window.start_sec:.1f}s–{window.end_sec:.1f}s: Avatar auf {proj}")
    if len(windows) > 40:
        lines.append(f"  … +{len(windows) - 40} weitere Avatar-Fenster")
    return "\n".join(lines)


class Teil2AtmosphereScheduler:
    def __init__(
        self,
        ai_service: AIService | None = None,
        llm_director: LLMDirector | None = None,
    ) -> None:
        self.ai = ai_service or AIService()
        self.llm = llm_director or LLMDirector(ai_service=self.ai)

    async def schedule(
        self,
        *,
        script_text: str,
        sentences: list[str],
        segments: list[AvatarTextSegment],
        gesamtkonzept: Gesamtkonzept,
        dramaturgy: DramaturgyDecision,
        avatar_clip_ids: set[str],
        openai_model: str = "gpt-4o",
    ) -> list[CuePoint]:
        total_sec = estimate_script_duration_sec(script_text, segments)
        windows = build_avatar_windows(script_text, segments, total_sec)
        allowed_clips = set(_atmosphere_clip_pool(avatar_clip_ids=avatar_clip_ids))
        if not allowed_clips:
            return []

        mid_anarchy = (gesamtkonzept.anarchy_curve.start + gesamtkonzept.anarchy_curve.end) / 2
        video_min, video_max = atmosphere_intervals_for_anarchy(mid_anarchy)

        points: list[CuePoint] = []
        if settings.teil2_atmosphere_use_llm and settings.director_dramaturgy_mode != "rules" and "openai" in self.ai.providers:
            try:
                llm_points = await self._schedule_llm(
                    script_text=script_text,
                    gesamtkonzept=gesamtkonzept,
                    windows=windows,
                    total_sec=total_sec,
                    allowed_clips=allowed_clips,
                    video_interval=(video_min, video_max),
                    openai_model=openai_model,
                )
                if llm_points:
                    points = llm_points
            except Exception:
                pass

        if not points:
            points = _rule_based_atmosphere_points(
                script_text=script_text,
                sentences=sentences,
                segments=segments,
                curve=gesamtkonzept.anarchy_curve,
                avatar_clip_ids=avatar_clip_ids,
                dramaturgy=dramaturgy,
            )
        return ensure_recurring_atmosphere_clips(
            points,
            windows=windows,
            total_sec=total_sec,
            allowed_clips=allowed_clips,
        )

    async def _schedule_llm(
        self,
        *,
        script_text: str,
        gesamtkonzept: Gesamtkonzept,
        windows: list[AvatarWindow],
        total_sec: float,
        allowed_clips: set[str],
        video_interval: tuple[float, float],
        openai_model: str,
    ) -> list[CuePoint]:
        digest = script_text[:8000] + ("…" if len(script_text) > 8000 else "")
        timeline = _timeline_summary(windows, total_sec)
        clip_sample = available_recurring_clips(allowed_clips)
        clip_sample.extend(
            clip_id for clip_id in sorted(allowed_clips) if clip_id not in clip_sample
        )
        clip_sample = clip_sample[:40]
        prompt = (
            f"Anarchie-Kurve: {gesamtkonzept.anarchy_curve.start} → {gesamtkonzept.anarchy_curve.end}\n"
            f"Geschätzte Dauer: {total_sec:.0f}s\n\n"
            f"Skript-Auszug:\n{digest}\n\n"
            f"Avatar-Belegung (reservierte Beamers):\n{timeline}\n\n"
            "Plane Atmosphären-/Begleit-Videos (OhneAvatare) auf FREIEN Beamern.\n"
            "KEIN Dialog. Stimmungsunabhängig — variiere Clips nach Zeit/Anarchie, nicht nach Text.\n"
            f"Rhythmus: erste Clips bei 0s, dann alle {video_interval[0]:.0f}–{video_interval[1]:.0f}s — "
            "früh schon dicht, nicht erst spät in der Aufführung.\n"
            "Pflicht: Adam und Eva müssen immer etwas zeigen, sobald kein Avatar dort läuft "
            "(Atmosphäre auf jedem freien Adam/Eva).\n"
            "Früh zusätzlich einen weiteren freien Beamer (rz21 oder led) belegen.\n"
            "Pflicht: clip_id bonnie und clyde mehrmals über die Aufführung als Begleitvideo "
            "(OSC ohne Avatare) verteilen — nicht nur einmal, nicht dauernd.\n"
            "Pro Zeitstempel: mehrere cue_points mit gleichem time_offset_sec, "
            "je ein anderer freier Projektor (Begleitung parallel zu Avataren).\n"
            "Je höher die Anarchie, desto mehr zusätzliche freie Flächen (rz21, led).\n"
            f"Nur clip_id aus: {clip_sample}\n"
            f"Projektoren: rz21, adam, eva, led — nur freie zum jeweiligen time_offset_sec.\n"
            f"Gesamtdauer: {total_sec:.0f}s\n\n"
            'Antworte nur mit JSON: {"cue_points":[{"trigger":"time","time_offset_sec":12.0,'
            '"function":"atmosphaere","intensity":0.5,'
            '"visual":{"clip_id":"clyde","projector":"adam","video_type":"atmosphere"}},'
            '{"trigger":"time","time_offset_sec":12.0,"function":"atmosphaere","intensity":0.5,'
            '"visual":{"clip_id":"strand","projector":"eva","video_type":"atmosphere"}},'
            '{"trigger":"time","time_offset_sec":40.0,"function":"release","intensity":0.3,'
            '"visual":{"action":"fade_to_black","fade_time":4,"projector":"adam"}}]}'
        )
        raw = await self.ai.generate(
            "openai",
            openai_model,
            [
                {
                    "role": "system",
                    "content": (
                        "Du planst B-Roll/Begleitvideo auf freien Projektoren. Kein Dialog. "
                        "Stimmungsunabhängig — Rhythmus und Anarchie, nicht Textinhalt. "
                        "Avatar-Beamers nie belegen. Freie Flächen parallel mit verschiedenen Clips füllen. "
                        "Plane auch bewusst Leerstellen: fade_to_black oder stop_clip, "
                        "damit die Atmosphäre atmet und nicht nur startet. "
                        "Pflichtclips bonnie und clyde mehrmals als Begleitvideo einplanen. "
                        "Keine Avatar-Clips. Nur gültiges JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=settings.dramaturgy_decision_max_tokens,
        )
        parsed = _parse_llm_cue_points(raw)
        allowed_projectors = set(ALL_PROJECTORS)
        validated = _validate_atmosphere_points(
            parsed,
            allowed_clips=allowed_clips,
            allowed_projectors=allowed_projectors,
            max_time_sec=total_sec,
        )
        if len(validated) < 3:
            return []
        rerouted: list[CuePoint] = []
        for point in validated:
            free = free_projectors_at(windows, point.time_offset_sec)
            visual = point.visual
            if visual is None or not visual.clip_id:
                continue
            projector = visual.projector
            if projector not in free:
                if not free:
                    continue
                projector = pick_atmosphere_projectors(
                    1,
                    reserved=set(ALL_PROJECTORS) - set(free),
                    seed=int(point.time_offset_sec),
                )[0]
            rerouted.append(
                CuePoint(
                    trigger=CuePointTrigger.TIME,
                    time_offset_sec=point.time_offset_sec,
                    function=point.function,
                    intensity=point.intensity,
                    visual=_assign_atmosphere_visual(visual.clip_id, projector),  # type: ignore[arg-type]
                )
            )
        return _expand_points_onto_free_projectors(
            rerouted,
            windows=windows,
            curve=gesamtkonzept.anarchy_curve,
            total_sec=total_sec,
            allowed_clips=allowed_clips,
        )


_scheduler: Teil2AtmosphereScheduler | None = None


def get_teil2_atmosphere_scheduler() -> Teil2AtmosphereScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Teil2AtmosphereScheduler()
    return _scheduler
