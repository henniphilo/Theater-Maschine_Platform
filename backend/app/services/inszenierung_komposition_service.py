import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import AsyncIterator, Literal

from app.core.config import settings
from app.director.cues.cue_models import CuePoint, CuePointTrigger, DramaturgyDecision
from app.director.dialogue.builder import build_dialogue_event
from app.director.dramaturgy.llm_director import LLMDirector
from app.director.dramaturgy.rules_text import dramaturgy_rules_excerpt
from app.director.outputs.osc_commands import build_osc_commands
from app.schemas.inszenierung import (
    CompositionMoment,
    CompositionPlan,
    Gesamtkonzept,
    SceneCorpus,
)
from app.services.ai_service import AIService
from app.services.inszenierung_validation import (
    anarchy_level_for_index,
    apply_anarchy_curve,
    ensure_moment_ids,
    excerpt_in_scene,
    overlap_for_anarchy,
    validate_composition,
)
from app.services.script_splitter import split_sentences

EventType = Literal["thinking", "moment", "composition_plan", "error", "done"]


@dataclass
class KompositionEvent:
    type: EventType
    moment: dict | None = None
    moment_order: int | None = None
    composition: dict | None = None
    detail: str | None = None


class InszenierungKompositionService:
    def __init__(
        self,
        ai_service: AIService | None = None,
        llm_director: LLMDirector | None = None,
    ) -> None:
        self.ai = ai_service or AIService()
        self.llm = llm_director or LLMDirector(ai_service=self.ai)

    def _validate_providers(self) -> None:
        if "openai" not in self.ai.providers:
            raise ValueError("OpenAI is not configured (set OPENAI_API_KEY)")

    async def run_stream(
        self,
        corpus: SceneCorpus,
        *,
        openai_model: str,
        moment_count: int,
    ) -> AsyncIterator[KompositionEvent]:
        if not corpus.gesamtkonzept:
            yield KompositionEvent(type="error", detail="Zuerst Analyse-Workshop abschließen")
            return
        if not corpus.scenes:
            yield KompositionEvent(type="error", detail="Keine Szenen im Korpus")
            return
        self._validate_providers()

        yield KompositionEvent(type="thinking")
        moments = await self._generate_moments(corpus, openai_model, moment_count)
        curve = corpus.gesamtkonzept.anarchy_curve
        moments = apply_anarchy_curve(ensure_moment_ids(moments), curve)

        enriched: list[CompositionMoment] = []
        for index, moment in enumerate(moments):
            yield KompositionEvent(type="thinking")
            dramaturgy = await self._dramaturgy_for_moment(
                corpus,
                moment,
                openai_model,
            )
            moment.dramaturgy = dramaturgy
            enriched.append(moment)
            yield KompositionEvent(
                type="moment",
                moment_order=index,
                moment=moment.model_dump(mode="json"),
            )

        plan = CompositionPlan(
            moments=enriched,
            total_estimated_duration_sec=sum(
                (m.duration_hint_ms or 8000) / 1000 for m in enriched
            ),
            max_concurrent_voices=3,
            max_concurrent_videos=2,
        )
        validate_composition(plan, corpus)
        yield KompositionEvent(
            type="composition_plan",
            composition=plan.model_dump(mode="json"),
        )
        yield KompositionEvent(type="done")

    async def _generate_moments(
        self,
        corpus: SceneCorpus,
        model: str,
        moment_count: int,
    ) -> list[CompositionMoment]:
        scene_lines = []
        for scene in corpus.scenes:
            scene_lines.append(
                f"- id={scene.id} tier={scene.animal} titel={scene.title or '—'} "
                f"text_len={len(scene.source_text)}"
            )
        concept = corpus.gesamtkonzept
        assert concept is not None
        prompt = (
            f"Gesamtkonzept: {concept.thesis}\n"
            f"Geld-Themen: {', '.join(concept.money_themes)}\n\n"
            f"Szenen:\n" + "\n".join(scene_lines) + "\n\n"
            f"Wähle {moment_count} Textausschnitte (wörtlich aus den Szenen) für eine Aufführung, "
            f"die von klar zu anarchisch eskaliert. Frühe Momente kurz, späte dürfen überlappen.\n\n"
            "JSON:\n"
            '{"moments":[{"scene_id":"uuid","text_excerpt":"wörtlicher Ausschnitt",'
            '"speaker":"AI_A|AI_B|narrator","start_delay_ms":0,"duration_hint_ms":8000}]}\n'
            "Nur gültiges JSON."
        )
        raw = await self.ai.generate(
            "openai",
            model,
            [
                {"role": "system", "content": "Du bist Dramaturg für Teil 2. Nur JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=settings.dramaturgy_decision_max_tokens,
        )
        parsed = self._parse_moments_json(raw, corpus, moment_count, concept)
        return parsed

    def _parse_moments_json(
        self,
        raw: str,
        corpus: SceneCorpus,
        moment_count: int,
        concept: Gesamtkonzept,
    ) -> list[CompositionMoment]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
            items = data.get("moments", data if isinstance(data, list) else [])
            moments: list[CompositionMoment] = []
            for index, item in enumerate(items[:moment_count]):
                scene_id = item["scene_id"]
                excerpt = item["text_excerpt"].strip()
                scene = next((s for s in corpus.scenes if s.id == scene_id), None)
                if scene is None or not excerpt_in_scene(scene, excerpt):
                    continue
                moments.append(
                    CompositionMoment(
                        id=str(uuid.uuid4()),
                        order=index,
                        scene_id=scene_id,
                        text_excerpt=excerpt,
                        speaker=item.get("speaker", "AI_A"),
                        start_delay_ms=int(item.get("start_delay_ms", 0)),
                        duration_hint_ms=int(item.get("duration_hint_ms", 8000)),
                        anarchy_level=anarchy_level_for_index(
                            index, min(moment_count, len(items)), concept.anarchy_curve
                        ),
                    )
                )
            if moments:
                return moments
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass
        return self._fallback_moments(corpus, moment_count, concept)

    def _fallback_moments(
        self,
        corpus: SceneCorpus,
        moment_count: int,
        concept: Gesamtkonzept,
    ) -> list[CompositionMoment]:
        moments: list[CompositionMoment] = []
        scene_index = 0
        for index in range(moment_count):
            scene = corpus.scenes[scene_index % len(corpus.scenes)]
            sentences = split_sentences(scene.source_text)
            if not sentences:
                excerpt = scene.source_text[:200].strip()
            else:
                sent_idx = (index * 2) % len(sentences)
                excerpt = sentences[sent_idx]
                if sent_idx + 1 < len(sentences) and index > moment_count // 2:
                    excerpt = f"{sentences[sent_idx]} {sentences[sent_idx + 1]}"
            level = anarchy_level_for_index(index, moment_count, concept.anarchy_curve)
            moments.append(
                CompositionMoment(
                    id=str(uuid.uuid4()),
                    order=index,
                    scene_id=scene.id,
                    text_excerpt=excerpt,
                    speaker="AI_B" if index % 2 else "AI_A",
                    overlap_with_previous=overlap_for_anarchy(level) if index else 0.0,
                    anarchy_level=level,
                    start_delay_ms=max(0, 1200 - int(level * 800)),
                    duration_hint_ms=6000 + int(level * 4000),
                )
            )
            scene_index += 1
        return moments

    async def _dramaturgy_for_moment(
        self,
        corpus: SceneCorpus,
        moment: CompositionMoment,
        model: str,
    ) -> DramaturgyDecision:
        scene = next((s for s in corpus.scenes if s.id == moment.scene_id), None)
        topic = f"{corpus.title}: {scene.animal if scene else ''}"
        event = build_dialogue_event(
            speaker="openai",
            text=moment.text_excerpt,
            topic=topic,
            created_at=datetime.now(UTC),
        )
        try:
            decision = await self.llm.decide(
                event,
                model=model,
                discussion_context=corpus.gesamtkonzept.discussion_summary or "",
            )
        except Exception:
            decision = self.llm.rule_engine.decide(event)
        decision.intensity = max(decision.intensity, moment.anarchy_level * 0.9)
        if not decision.cue_points:
            decision.cue_points = [
                CuePoint(
                    trigger=CuePointTrigger.START,
                    function="überlagern" if moment.anarchy_level > 0.6 else "verstärken",
                    intensity=moment.anarchy_level,
                    visual=decision.visual,
                    sound=decision.sound,
                    light=decision.light,
                )
            ]
        build_osc_commands(decision, dry_run=True)
        return decision
