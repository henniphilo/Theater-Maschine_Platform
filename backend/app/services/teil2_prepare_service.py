"""One-step Teil-2 prepare: compact analyse, LLM/rule dramaturgy, CSV alignment."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from app.core.config import settings
from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    DramaturgyDecision,
    LightCue,
    PerformanceSpeaker,
)
from app.director.dialogue.builder import build_dialogue_event
from app.director.dramaturgy.llm_director import LLMDirector
from app.director.dramaturgy.rules_text import dramaturgy_rules_excerpt
from app.director.outputs.osc_commands import build_osc_commands
from app.schemas.inszenierung import (
    AnimalPosition,
    AnarchyCurve,
    AvatarTextSegment,
    CrossSceneLink,
    Gesamtkonzept,
    SceneCorpus,
    Teil2PerformancePlan,
)
from app.services.ai_service import AIService
from app.services.avatar_speech_catalog import get_avatar_speech_catalog_service
from app.services.inszenierung_validation import dramaturgy_with_anarchy
from app.services.teil2_atmosphere_cues import inject_atmosphere_visuals
from app.services.teil2_dramaturgy_routing import (
    reserved_projectors_from_segments,
    route_dramaturgy_away_from_projectors,
)
from app.services.teil2_script_service import animal_sections_from_script
from app.services.teil2_text_alignment import align_avatar_csv_to_script
from app.services.text_split import sentence_char_ranges, split_sentences


def _anarchy_at(sentence_index: int, total: int, curve: AnarchyCurve) -> float:
    if total <= 1:
        return curve.end
    t = sentence_index / (total - 1)
    return curve.start + (curve.end - curve.start) * t


class Teil2PrepareService:
    def __init__(
        self,
        ai_service: AIService | None = None,
        llm_director: LLMDirector | None = None,
    ) -> None:
        self.ai = ai_service or AIService()
        self.llm = llm_director or LLMDirector(ai_service=self.ai)

    async def prepare(
        self,
        corpus: SceneCorpus,
        *,
        openai_model: str = "gpt-4o",
        performance_speaker: PerformanceSpeaker = "narrator",
    ) -> tuple[Gesamtkonzept, Teil2PerformancePlan]:
        script_text = (corpus.script_text or "").strip()
        if not script_text:
            raise ValueError("Kein Aufführungstext — zuerst Text hochladen")

        gesamtkonzept = await self._compact_analyse(corpus, openai_model=openai_model)
        sentences = split_sentences(script_text)
        sentence_char_starts = [start for start, _ in sentence_char_ranges(script_text)]
        catalog = get_avatar_speech_catalog_service().load()
        segments, alignment_warnings = align_avatar_csv_to_script(
            script_text,
            catalog.cues,
            anarchy_level=gesamtkonzept.anarchy_curve.start,
        )
        dramaturgy = await self._build_dramaturgy(
            script_text,
            sentences,
            segments,
            gesamtkonzept,
            title=corpus.title,
            openai_model=openai_model,
        )
        avatar_clip_ids = {
            layer.video_clip_id for segment in segments for layer in segment.avatar_layers
        }
        dramaturgy = inject_atmosphere_visuals(
            dramaturgy,
            sentences=sentences,
            segments=segments,
            curve=gesamtkonzept.anarchy_curve,
            avatar_clip_ids=avatar_clip_ids,
        )
        reserved = reserved_projectors_from_segments(segments)
        dramaturgy = route_dramaturgy_away_from_projectors(
            dramaturgy,
            reserved,
            avatar_clip_ids=avatar_clip_ids,
            seed=len(sentences),
        )
        build_osc_commands(dramaturgy, dry_run=True, video_scope="part2")

        plan = Teil2PerformancePlan(
            performance_speaker=performance_speaker,
            sentences=sentences,
            sentence_char_starts=sentence_char_starts,
            avatar_segments=segments,
            dramaturgy=dramaturgy,
            anarchy_level_end=gesamtkonzept.anarchy_curve.end,
            alignment_warnings=alignment_warnings,
        )
        return gesamtkonzept, plan

    async def _compact_analyse(self, corpus: SceneCorpus, *, openai_model: str) -> Gesamtkonzept:
        script_text = corpus.script_text or ""
        digest = script_text[:12000] + ("…" if len(script_text) > 12000 else "")
        if "openai" in self.ai.providers and settings.director_dramaturgy_mode != "rules":
            try:
                rules = dramaturgy_rules_excerpt(max_chars=settings.dramaturgy_rules_excerpt_chars)
                prompt = (
                    f"Skript: {corpus.title}\n\nAufführungstext:\n{digest}\n\n"
                    "Erstelle das Gesamtkonzept als JSON:\n"
                    '{"thesis":"...","money_themes":["..."],"animal_positions":[{"animal":"...","stance":"...","money_angle":"..."}],'
                    '"cross_scene_links":[{"label":"...","scene_ids":["avatar"],"note":"..."}],'
                    '"anarchy_curve":{"start":0.35,"end":1.0},"discussion_summary":"..."}'
                )
                raw_json = await self.ai.generate(
                    "openai",
                    openai_model,
                    [
                        {
                            "role": "system",
                            "content": (
                                "Du bist Dramaturg für Teil 2 (Avatar-Skript). "
                                f"=== REGELWERK ===\n{rules}\nAntworte nur mit gültigem JSON."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=settings.dramaturgy_decision_max_tokens,
                )
                return self._parse_gesamtkonzept(raw_json, script_text)
            except Exception:
                pass
        return self._fallback_gesamtkonzept(script_text)

    def _parse_gesamtkonzept(self, raw: str, script_text: str) -> Gesamtkonzept:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
            return Gesamtkonzept.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            return self._fallback_gesamtkonzept(script_text)

    def _fallback_gesamtkonzept(self, script_text: str) -> Gesamtkonzept:
        sections = animal_sections_from_script(script_text)
        animals = [
            AnimalPosition(animal=name, stance="im Aufführungstext", money_angle="Geld / Ökonomie")
            for name, _ in sections
        ]
        if not animals:
            animals = [
                AnimalPosition(
                    animal="Avatar-Figuren",
                    stance="im Skript",
                    money_angle="Geld / Ökonomie",
                )
            ]
        return Gesamtkonzept(
            thesis="Geld erscheint bei den Tieren als Austauschlogik, Schuldzuweisung und Sprachmaske.",
            money_themes=["Austausch", "Schuld", "Wert", "Rendite"],
            animal_positions=animals,
            cross_scene_links=[
                CrossSceneLink(
                    label="Geld-Klammer",
                    scene_ids=["avatar"],
                    note="Querverweis über den Aufführungstext",
                )
            ],
            anarchy_curve=AnarchyCurve(start=0.35, end=1.0),
            discussion_summary="Kompakt-Analyse (Regel-Fallback)",
        )

    async def _build_dramaturgy(
        self,
        script_text: str,
        sentences: list[str],
        segments: list[AvatarTextSegment],
        gesamtkonzept: Gesamtkonzept,
        *,
        title: str,
        openai_model: str,
    ) -> DramaturgyDecision:
        curve = gesamtkonzept.anarchy_curve
        if settings.director_dramaturgy_mode != "rules" and "openai" in self.ai.providers:
            try:
                event = build_dialogue_event(
                    speaker="openai",
                    text=script_text[:12000],
                    topic=title,
                    created_at=datetime.now(UTC),
                )
                decision = await self.llm.decide(
                    event,
                    model=openai_model,
                    discussion_context=gesamtkonzept.thesis,
                )
                decision = self._ensure_sentence_cue_points(
                    decision, sentences, segments, curve
                )
                return dramaturgy_with_anarchy(decision, curve.end)
            except Exception:
                pass
        return self._rule_dramaturgy_for_script(sentences, segments, gesamtkonzept, title)

    def _cue_point_for_chunk(
        self,
        chunk: str,
        sentence_index: int,
        total_sentences: int,
        curve: AnarchyCurve,
        title: str,
    ) -> CuePoint:
        anarchy = _anarchy_at(sentence_index, total_sentences, curve)
        event = build_dialogue_event(
            speaker="openai",
            text=chunk,
            topic=title,
            created_at=datetime.now(UTC),
        )
        try:
            section = self.llm.rule_engine.decide(event)
        except Exception:
            section = DramaturgyDecision(
                reason="Teil-2 Text-Sync",
                tags=["teil2", "text_sync"],
                mood="tension",
                intensity=anarchy,
            )
        section = dramaturgy_with_anarchy(section, anarchy)
        fn = "überlagern" if anarchy > 0.6 else "verstärken"
        if section.cue_points:
            point = section.cue_points[0].model_copy(deep=True)
            point.trigger = CuePointTrigger.SENTENCE_END
            point.sentence_index = sentence_index
            point.function = point.function or fn
            point.intensity = max(point.intensity, anarchy)
            if not point.sound and section.sound:
                point.sound = section.sound
            if not point.light and section.light:
                point.light = section.light
            if not point.visual and section.visual:
                point.visual = section.visual
            return point
        return CuePoint(
            trigger=CuePointTrigger.SENTENCE_END,
            sentence_index=sentence_index,
            function=fn,
            intensity=anarchy,
            visual=section.visual,
            sound=section.sound,
            light=section.light,
        )

    def _rule_dramaturgy_for_script(
        self,
        sentences: list[str],
        segments: list[AvatarTextSegment],
        gesamtkonzept: Gesamtkonzept,
        title: str,
    ) -> DramaturgyDecision:
        curve = gesamtkonzept.anarchy_curve
        total = len(sentences)
        merged_points: list[CuePoint] = []
        covered: set[int] = set()

        for segment in segments:
            index = segment.start_sentence_index
            if index in covered or index >= total:
                continue
            chunk = segment.text_excerpt.strip() or sentences[index]
            merged_points.append(
                self._cue_point_for_chunk(chunk, index, total, curve, title)
            )
            covered.add(index)

        for index in range(0, max(1, total)):
            if index in covered:
                continue
            chunk = sentences[index]
            if not chunk.strip():
                continue
            merged_points.append(
                self._cue_point_for_chunk(chunk, index, total, curve, title)
            )
            covered.add(index)

        merged_points.sort(key=lambda point: point.sentence_index or 0)
        merged_points = self._boost_light_cue_density(merged_points, sentences, curve)

        return DramaturgyDecision(
            reason=f"Teil-2 OSC-Regie — {gesamtkonzept.thesis[:120]}",
            tags=["teil2", "text_sync"],
            mood="tension",
            intensity=curve.end,
            cue_points=merged_points,
        )

    def _light_mood_for_sentence(self, sentence: str, index: int) -> str:
        """Rotate moods so light selection is not stuck on one scene."""
        text = sentence.lower()
        mood_keywords = (
            ("warm", ("warm", "herz", "nähe", "mensch")),
            ("unheimlich", ("fremd", "dunkel", "schatten", "kalt")),
            ("melancholisch", ("verloren", "traurig", "leer", "stille")),
            ("spannung", ("plötzlich", "alarm", "!", "gefahr")),
            ("gegenlicht", ("licht", "schein", "bühne")),
            ("blendung", ("blend", "zuschauer", "saal")),
            ("musik", ("musik", "klavier", "chor", "ton")),
        )
        for mood, keywords in mood_keywords:
            if any(kw in text for kw in keywords):
                return mood
        fallback_moods = (
            "spannung",
            "warm",
            "gegenlicht",
            "blendung",
            "unheimlich",
            "melancholisch",
            "musik",
        )
        return fallback_moods[index % len(fallback_moods)]

    def _light_scene_for_sentence(
        self,
        sentence: str,
        index: int,
        total: int,
        anarchy: float,
        recent_scene_ids: list[str],
    ):
        mood = self._light_mood_for_sentence(sentence, index)
        selector = self.llm.rule_engine.selector
        scene = selector.select_light(mood, anarchy)
        if scene and scene.id not in recent_scene_ids[-2:]:
            recent_scene_ids.append(scene.id)
            return scene

        db = self.llm.rule_engine.media_db
        pool = [
            s
            for s in db.light_scenes
            if s.id != "blackout" and s.intensity_min <= anarchy <= s.intensity_max
        ]
        if not pool:
            pool = [s for s in db.light_scenes if s.id != "blackout"]
        if not pool:
            return scene

        recent = set(recent_scene_ids[-3:])
        for offset in range(len(pool)):
            candidate = pool[(index + offset) % len(pool)]
            if candidate.id not in recent:
                recent_scene_ids.append(candidate.id)
                selector._recent_light_ids.append(candidate.id)
                return candidate
        if scene:
            return scene
        chosen = pool[index % len(pool)]
        recent_scene_ids.append(chosen.id)
        return chosen

    def _boost_light_cue_density(
        self,
        points: list[CuePoint],
        sentences: list[str],
        curve: AnarchyCurve,
    ) -> list[CuePoint]:
        """Ensure a dedicated light shift on (almost) every sentence for Teil 2."""
        total = len(sentences)
        if total == 0:
            return points
        by_index = {p.sentence_index: p for p in points if p.sentence_index is not None}
        boosted: list[CuePoint] = []
        recent_scene_ids: list[str] = []
        for index in range(total):
            anarchy = _anarchy_at(index, total, curve)
            sentence = sentences[index]
            existing = by_index.get(index)
            if existing is not None:
                if existing.light is None:
                    light_scene = self._light_scene_for_sentence(
                        sentence, index, total, anarchy, recent_scene_ids
                    )
                    if light_scene:
                        existing.light = LightCue(
                            scene_id=light_scene.id,
                            fade_time=light_scene.fade_time,
                            intensity=round(0.3 + anarchy * 0.7, 2),
                        )
                        recent_scene_ids.append(light_scene.id)
                elif existing.light.scene_id:
                    if existing.light.intensity is not None and existing.light.intensity <= 0:
                        recent_scene_ids = [
                            sid for sid in recent_scene_ids if sid != existing.light.scene_id
                        ]
                    else:
                        recent_scene_ids.append(existing.light.scene_id)
                boosted.append(existing)
                if index % 5 == 4 and recent_scene_ids:
                    off_scene = recent_scene_ids[-1]
                    boosted.append(
                        CuePoint(
                            trigger=CuePointTrigger.SENTENCE_END,
                            sentence_index=index,
                            function="licht_aus",
                            intensity=0.0,
                            light=LightCue(
                                scene_id=off_scene,
                                fade_time=2.0,
                                intensity=0.0,
                                replace_previous=False,
                            ),
                        )
                    )
                continue
            light_scene = self._light_scene_for_sentence(
                sentence, index, total, anarchy, recent_scene_ids
            )
            if not light_scene:
                continue
            boosted.append(
                CuePoint(
                    trigger=CuePointTrigger.SENTENCE_END,
                    sentence_index=index,
                    function="licht_wechsel",
                    intensity=anarchy,
                    light=LightCue(
                        scene_id=light_scene.id,
                        fade_time=max(1.5, light_scene.fade_time * 0.75),
                        intensity=round(0.35 + anarchy * 0.65, 2),
                    ),
                )
            )
        return boosted or points

    def _ensure_sentence_cue_points(
        self,
        decision: DramaturgyDecision,
        sentences: list[str],
        segments: list[AvatarTextSegment],
        curve: AnarchyCurve,
    ) -> DramaturgyDecision:
        min_cues = max(len(segments), len(sentences), 12)
        if not decision.cue_points or len(decision.cue_points) < min_cues:
            rule_based = self._rule_dramaturgy_for_script(
                sentences,
                segments,
                Gesamtkonzept(anarchy_curve=curve, thesis=decision.reason),
                title="Teil 2",
            )
            if not decision.cue_points:
                return rule_based
            existing = {p.sentence_index for p in decision.cue_points if p.sentence_index is not None}
            for point in rule_based.cue_points:
                if point.sentence_index not in existing:
                    decision.cue_points.append(point)
            decision.cue_points.sort(key=lambda point: point.sentence_index or 0)
        decision.cue_points = self._boost_light_cue_density(
            decision.cue_points, sentences, curve
        )
        for index, point in enumerate(decision.cue_points):
            if point.sentence_index is None:
                point.sentence_index = min(
                    len(sentences) - 1,
                    int(index / max(1, len(decision.cue_points) - 1) * max(0, len(sentences) - 1)),
                )
            if point.trigger not in (CuePointTrigger.SENTENCE_END, CuePointTrigger.KEYWORD, CuePointTrigger.TIME):
                point.trigger = CuePointTrigger.SENTENCE_END
        return decision


_service: Teil2PrepareService | None = None


def get_teil2_prepare_service() -> Teil2PrepareService:
    global _service
    if _service is None:
        _service = Teil2PrepareService()
    return _service
