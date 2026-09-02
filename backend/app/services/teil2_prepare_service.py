"""One-step Teil-2 prepare: compact analyse, LLM/rule dramaturgy, CSV alignment."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable

from app.core.config import settings
from app.director.cues.cue_models import (
    CuePoint,
    DramaturgyDecision,
    PerformanceSpeaker,
)
from app.director.dramaturgy.llm_director import LLMDirector
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
from app.services.avatar_required_lights import apply_required_lights_to_plan
from app.services.avatar_speech_catalog import get_avatar_speech_catalog_service
from app.services.teil2_anarchy_cues import (
    apply_anarchy_to_keyword_cue_point,
    build_keyword_cue_point,
    densify_keyword_sound_cues,
    extract_text_fallback_keywords,
    find_sentence_index_for_keyword,
    keyword_in_script,
    max_keywords_per_chunk,
    min_keyword_cues_for_script,
    min_keywords_per_chunk,
    teil2_cue_allowlist,
)
from app.services.teil2_atmosphere_scheduler import get_teil2_atmosphere_scheduler
from app.services.teil2_cue_overview import build_cue_overview
from app.services.teil2_dramaturgy_routing import (
    reserved_projectors_from_segments,
    route_dramaturgy_away_from_projectors,
)
from app.services.teil2_script_service import animal_sections_from_script
from app.services.teil2_text_alignment import align_avatar_csv_to_script
from app.services.text_split import sentence_char_ranges, split_sentences


PreparePhaseCallback = Callable[[str], Awaitable[None] | None]


def _strip_avatar_visuals_from_dramaturgy(
    decision: DramaturgyDecision,
    avatar_clip_ids: set[str],
) -> DramaturgyDecision:
    if decision.visual and decision.visual.clip_id in avatar_clip_ids:
        decision.visual = None
    for point in decision.cue_points:
        if point.visual and (
            point.visual.clip_id in avatar_clip_ids
            or point.visual.video_type == "avatar"
        ):
            point.visual = None
    return decision


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
        on_phase: PreparePhaseCallback | None = None,
    ) -> tuple[Gesamtkonzept, Teil2PerformancePlan]:
        async def phase(name: str) -> None:
            if on_phase is not None:
                result = on_phase(name)
                if result is not None:
                    await result

        script_text = (corpus.script_text or "").strip()
        if not script_text:
            raise ValueError("Kein Aufführungstext — zuerst Text hochladen")

        await phase("analyse")
        sentences = split_sentences(script_text)
        sentence_char_starts = [start for start, _ in sentence_char_ranges(script_text)]
        gesamtkonzept, (segments, alignment_warnings) = await asyncio.gather(
            self._compact_analyse(corpus, openai_model=openai_model),
            asyncio.to_thread(self._align_avatars, script_text, sentences),
        )
        await phase("avatar_alignment")
        await phase("dramaturgy")
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
        dramaturgy = _strip_avatar_visuals_from_dramaturgy(dramaturgy, avatar_clip_ids)
        reserved = reserved_projectors_from_segments(segments)
        dramaturgy = route_dramaturgy_away_from_projectors(
            dramaturgy,
            reserved,
            avatar_clip_ids=avatar_clip_ids,
            seed=len(sentences),
        )
        dramaturgy = apply_required_lights_to_plan(dramaturgy, segments)
        await phase("atmosphere")
        atmosphere_cue_points = await get_teil2_atmosphere_scheduler().schedule(
            script_text=script_text,
            sentences=sentences,
            segments=segments,
            gesamtkonzept=gesamtkonzept,
            dramaturgy=dramaturgy,
            avatar_clip_ids=avatar_clip_ids,
            openai_model=openai_model,
        )
        build_osc_commands(dramaturgy, dry_run=True, video_scope="part2")
        await phase("overview")
        cue_overview = build_cue_overview(
            sentences,
            dramaturgy,
            segments,
            atmosphere_cue_points,
            dramaturgy_reason=dramaturgy.reason,
        )

        plan = Teil2PerformancePlan(
            performance_speaker=performance_speaker,
            sentences=sentences,
            sentence_char_starts=sentence_char_starts,
            avatar_segments=segments,
            dramaturgy=dramaturgy,
            atmosphere_cue_points=atmosphere_cue_points,
            cue_overview=cue_overview,
            anarchy_level_end=gesamtkonzept.anarchy_curve.end,
            alignment_warnings=alignment_warnings,
        )
        await phase("done")
        return gesamtkonzept, plan

    def _align_avatars(
        self,
        script_text: str,
        sentences: list[str],
    ) -> tuple[list[AvatarTextSegment], list[str]]:
        catalog = get_avatar_speech_catalog_service().load()
        return align_avatar_csv_to_script(
            script_text,
            catalog.cues,
            anarchy_level=0.35,
            anarchy_curve=(0.35, 1.0),
        )

    async def _compact_analyse(self, corpus: SceneCorpus, *, openai_model: str) -> Gesamtkonzept:
        script_text = corpus.script_text or ""
        if (
            settings.teil2_use_analyse_llm
            and "openai" in self.ai.providers
            and settings.director_dramaturgy_mode != "rules"
        ):
            digest = script_text[:6000] + ("…" if len(script_text) > 6000 else "")
            try:
                prompt = (
                    f"Skript: {corpus.title}\n\nText:\n{digest}\n\n"
                    "Kurz-Analyse als JSON (kein Dialog, keine Diskussion):\n"
                    '{"thesis":"...","money_themes":["..."],"animal_positions":[{"animal":"...","stance":"...","money_angle":"..."}],'
                    '"cross_scene_links":[{"label":"...","scene_ids":["avatar"],"note":"..."}],'
                    '"anarchy_curve":{"start":0.35,"end":1.0}}'
                )
                raw_json = await self.ai.generate(
                    "openai",
                    openai_model,
                    [
                        {
                            "role": "system",
                            "content": "Teil-2 Anarchie-Kurve. Nur JSON, kein Dialog.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=600,
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
                decision = await self._build_dramaturgy_chunked(
                    script_text,
                    sentences,
                    curve,
                    openai_model=openai_model,
                )
                decision = self._finalize_keyword_cues(
                    decision,
                    script_text,
                    sentences,
                    curve,
                )
                return decision
            except Exception:
                pass
        return self._rule_dramaturgy_for_script(
            script_text, sentences, gesamtkonzept
        )

    async def _build_dramaturgy_chunked(
        self,
        script_text: str,
        sentences: list[str],
        curve: AnarchyCurve,
        *,
        openai_model: str,
    ) -> DramaturgyDecision:
        chunk_size = max(6, settings.teil2_dramaturgy_chunk_size)
        total = len(sentences)
        allowlist = json.dumps(teil2_cue_allowlist(self.llm.media_db), ensure_ascii=False)

        async def one_chunk(start: int) -> list[CuePoint]:
            chunk = sentences[start : start + chunk_size]
            if not chunk:
                return []
            chunk_text = " ".join(chunk)
            min_k = min_keywords_per_chunk(chunk_text)
            max_k = max_keywords_per_chunk(chunk_text)
            prompt = (
                "Teil 2 — Stichwort-Cues für einen Textabschnitt.\n"
                "Avatar-Videos laufen separat. Plane NUR Licht + Sound.\n"
                "KEIN Dialog. Nicht satzweise.\n"
                "Lies den Abschnitt und finde SELBST dramaturgisch auffällige Stichworte "
                "oder kurze Phrasen (2–4 Wörter): Bild, Bruch, Kontrast, Benennung, "
                "Wiederholung, rhetorische Spitze — was im Text wirklich auffällt.\n"
                "Keine vorgegebene Themenliste, keine Schlagwort-Vorgabe von außen.\n"
                "Jedes keyword muss wörtlich im Textabschnitt vorkommen.\n"
                "Jeder cue_point MUSS einen sound.cue_id aus sounds[] haben (nur play, keine _out/cut).\n"
                "Sound oft und hörbar: lieber zu viele Sound-Cues als Lücken.\n"
                "Mehrere Cues pro Abschnitt; Anarchie steigt über den Verlauf (früh dezent, spät überlagert).\n\n"
                f"Textabschnitt:\n{chunk_text}\n\n"
                f"Medien-Allowlist:\n{allowlist}\n\n"
                f"Mindestens {min_k}, maximal {max_k} cue_points mit trigger keyword.\n"
                'JSON: {"cue_points":[{"trigger":"keyword","keyword":"STICHWORT_AUS_TEXT",'
                '"sound":{"action":"trigger_cue","cue_id":"..."},'
                '"light":{"action":"set_scene","scene_id":"..."}}]}'
            )
            raw = await self.ai.generate(
                "openai",
                openai_model,
                [
                    {
                        "role": "system",
                        "content": (
                            "Teil-2-Cue-Planner: Entdecke Stichworte im Textabschnitt "
                            "und weise Licht/Sound zu. Jeder Cue braucht einen play-Sound. "
                            "Keine _out/cut_all. Keine externe Wortliste. "
                            "keyword muss wörtlich im Text stehen. Kein Dialog. Nur JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=min(3500, 200 + max_k * 110),
            )
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            points = [CuePoint.model_validate(item) for item in data.get("cue_points", [])]
            validated: list[CuePoint] = []
            for point in points:
                keyword = (point.keyword or "").strip()
                if not keyword:
                    continue
                fixed = apply_anarchy_to_keyword_cue_point(
                    point,
                    keyword,
                    script_text,
                    sentences,
                    curve,
                    self.llm.media_db,
                )
                if fixed is not None:
                    validated.append(fixed)
            return validated

        starts = list(range(0, total, chunk_size))
        chunk_results = await asyncio.gather(
            *[one_chunk(start) for start in starts],
            return_exceptions=True,
        )
        merged_points: list[CuePoint] = []
        for result in chunk_results:
            if isinstance(result, Exception):
                continue
            merged_points.extend(result)
        if not merged_points:
            raise ValueError("Keine LLM-Stichwort-Cues aus Chunks")
        merged_points.sort(
            key=lambda point: (
                find_sentence_index_for_keyword(point.keyword or "", sentences) or 0,
                point.keyword or "",
            )
        )
        return DramaturgyDecision(
            reason="Teil-2 Stichwort-Cues (LLM, selbst gefunden)",
            tags=["teil2", "text_sync", "chunked_llm", "keyword", "anarchy"],
            mood="anarchy",
            intensity=curve.end,
            cue_points=merged_points,
        )

    def _rule_dramaturgy_for_script(
        self,
        script_text: str,
        sentences: list[str],
        gesamtkonzept: Gesamtkonzept,
    ) -> DramaturgyDecision:
        curve = gesamtkonzept.anarchy_curve
        keywords = extract_text_fallback_keywords(
            script_text,
            sentences,
            curve,
            min_keywords=min_keyword_cues_for_script(script_text),
        )
        recent_sounds: list[str] = []
        recent_lights: list[str] = []
        merged_points = [
            build_keyword_cue_point(
                keyword,
                sentence_index,
                anarchy,
                self.llm.media_db,
                slot=index,
                recent_sound_ids=recent_sounds,
                recent_light_ids=recent_lights,
            )
            for index, (keyword, sentence_index, anarchy) in enumerate(keywords)
        ]
        merged_points = densify_keyword_sound_cues(
            merged_points,
            script_text,
            sentences,
            curve,
            self.llm.media_db,
        )
        return DramaturgyDecision(
            reason="Teil-2 Stichwort-Cues (Regel-Fallback ohne LLM)",
            tags=["teil2", "text_sync", "keyword", "anarchy", "fallback"],
            mood="anarchy",
            intensity=curve.end,
            cue_points=merged_points,
        )

    def _finalize_keyword_cues(
        self,
        decision: DramaturgyDecision,
        script_text: str,
        sentences: list[str],
        curve: AnarchyCurve,
    ) -> DramaturgyDecision:
        validated: list[CuePoint] = []
        seen_keywords: set[str] = set()
        recent_sounds: list[str] = []
        for index, point in enumerate(decision.cue_points):
            keyword = (point.keyword or "").strip()
            if not keyword or not keyword_in_script(keyword, script_text):
                continue
            norm = keyword.lower()
            if norm in seen_keywords:
                continue
            fixed = apply_anarchy_to_keyword_cue_point(
                point,
                keyword,
                script_text,
                sentences,
                curve,
                self.llm.media_db,
                slot=index,
                recent_sound_ids=recent_sounds,
            )
            if fixed is None:
                continue
            seen_keywords.add(norm)
            validated.append(fixed)

        decision.cue_points = densify_keyword_sound_cues(
            validated,
            script_text,
            sentences,
            curve,
            self.llm.media_db,
        )
        return decision


_service: Teil2PrepareService | None = None


def get_teil2_prepare_service() -> Teil2PrepareService:
    global _service
    if _service is None:
        _service = Teil2PrepareService()
    return _service
