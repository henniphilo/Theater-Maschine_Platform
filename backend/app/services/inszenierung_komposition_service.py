import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import AsyncIterator, Literal

from app.core.config import settings
from app.director.cues.cue_models import CuePoint, CuePointTrigger, DramaturgyDecision, VisualCue
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
from app.services.avatar_speech_catalog import get_avatar_speech_catalog_service, match_avatar_cues
from app.services.inszenierung_validation import (
    anarchy_level_for_index,
    apply_anarchy_curve,
    ensure_moment_ids,
    excerpt_in_scene,
    overlap_for_anarchy,
    validate_composition,
)
from app.services.teil2_scene_filter import filter_teil2_scenes, teil2_corpus_view
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
        teil2_scenes = filter_teil2_scenes(corpus)
        if not teil2_scenes:
            yield KompositionEvent(type="error", detail="Keine Teil-2-Szenen (ohne Bärenklau) im Korpus")
            return
        corpus = teil2_corpus_view(corpus)
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
        avatar_lines = self._avatar_catalog_excerpt()
        prompt = (
            f"Gesamtkonzept: {concept.thesis}\n"
            f"Geld-Themen: {', '.join(concept.money_themes)}\n\n"
            f"Szenen:\n" + "\n".join(scene_lines) + "\n\n"
            f"Avatar-Video-Texte (gesprochen im Clip, kein TTS):\n{avatar_lines}\n\n"
            f"Wähle {moment_count} Textausschnitte (wörtlich aus den Szenen) für eine Aufführung, "
            f"die von klar zu anarchisch eskaliert. Frühe Momente kurz, bevorzugt avatar_video "
            f"wenn der Ausschnitt zu einem Avatar-Snippet passt. Späte Momente: Wechsel avatar_video/tts, "
            f"starke Überlappung.\n\n"
            "JSON:\n"
            '{"moments":[{"scene_id":"uuid","text_excerpt":"wörtlicher Ausschnitt",'
            '"speaker":"AI_A|AI_B|narrator",'
            '"speech_mode":"tts|avatar_video|silent",'
            '"avatar_speech_id":"BK3 oder null",'
            '"start_delay_ms":0,"duration_hint_ms":8000}]}\n'
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
                level = anarchy_level_for_index(
                    index, min(moment_count, len(items)), concept.anarchy_curve
                )
                moment = CompositionMoment(
                    id=str(uuid.uuid4()),
                    order=index,
                    scene_id=scene_id,
                    text_excerpt=excerpt,
                    speaker=item.get("speaker", "AI_A"),
                    start_delay_ms=int(item.get("start_delay_ms", 0)),
                    duration_hint_ms=int(item.get("duration_hint_ms", 8000)),
                    anarchy_level=level,
                )
                self._apply_speech_fields(moment, item, index)
                moments.append(moment)
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
            moment = CompositionMoment(
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
            self._apply_speech_fields(moment, None, index)
            moments.append(moment)
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
        self._apply_avatar_visual(decision, moment)
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

    def _avatar_catalog_excerpt(self, *, max_chars: int = 120) -> str:
        catalog = get_avatar_speech_catalog_service().load()
        lines: list[str] = []
        for cue in catalog.cues:
            if cue.id.upper().startswith("BK"):
                continue
            snippet = cue.text[:max_chars].replace("\n", " ")
            lines.append(f"- {cue.id} ({cue.avatar}): {snippet}")
        return "\n".join(lines) if lines else "(kein Katalog)"

    def _set_avatar_video(self, moment: CompositionMoment, cue_id: str, clip_id: str) -> None:
        moment.speech_mode = "avatar_video"
        moment.avatar_speech_id = cue_id
        moment.avatar_video_clip_id = clip_id

    def _apply_speech_fields(
        self,
        moment: CompositionMoment,
        item: dict | None,
        index: int,
    ) -> None:
        service = get_avatar_speech_catalog_service()
        if item:
            raw_mode = item.get("speech_mode")
            if raw_mode in ("tts", "avatar_video", "silent"):
                moment.speech_mode = raw_mode  # type: ignore[assignment]
            avatar_id = item.get("avatar_speech_id")
            if avatar_id:
                cue = service.cue_by_id(str(avatar_id))
                if cue:
                    self._set_avatar_video(moment, cue.id, cue.video_clip_id)
                    return
        if moment.speech_mode == "silent":
            return
        matches = match_avatar_cues(moment.text_excerpt, limit=3, exclude_baerenklau=True)
        level = moment.anarchy_level
        use_avatar = False
        if matches and level < 0.4:
            use_avatar = True
        elif matches and level < 0.7 and index % 2 == 0:
            use_avatar = True
        elif matches and level >= 0.7 and index % 3 != 1:
            use_avatar = True
        if use_avatar and matches:
            cue = matches[0]
            self._set_avatar_video(moment, cue.id, cue.video_clip_id)
        else:
            moment.speech_mode = "tts"

    def _apply_avatar_visual(self, decision: DramaturgyDecision, moment: CompositionMoment) -> None:
        if moment.speech_mode != "avatar_video":
            return
        clip_id = moment.avatar_video_clip_id
        if not clip_id:
            return
        projector = "adam" if moment.order % 2 == 0 else "eva"
        layer = moment.anarchy_level > 0.55
        avatar_cue = VisualCue(
            clip_id=clip_id,
            blend_mode="layer" if layer else "replace",
            video_type="avatar",
            projector=projector,  # type: ignore[arg-type]
            lock_until_finished=True,
            can_be_interrupted=False,
            duration_ms=moment.duration_hint_ms,
            outputs=[{"output_id": projector, "clip_id": clip_id}],  # type: ignore[list-item]
        )
        moment.avatar_video_cue = avatar_cue
        if decision.visual is None:
            decision.visual = avatar_cue
        else:
            decision.visual = avatar_cue
        atmosphere: list[VisualCue] = []
        if moment.anarchy_level >= 0.35 and decision.cue_points:
            for point in decision.cue_points:
                if point.visual and point.visual.clip_id and point.visual.clip_id != clip_id:
                    atmo = point.visual.model_copy(
                        update={
                            "video_type": "atmosphere",
                            "projector": "rz21",
                            "lock_until_finished": False,
                            "outputs": [{"output_id": "rz21", "clip_id": point.visual.clip_id}],
                        }
                    )
                    atmosphere.append(atmo)
        moment.atmosphere_video_cues = atmosphere
        if moment.anarchy_level > 0.65 and decision.cue_points:
            for point in decision.cue_points:
                if point.visual is None:
                    point.visual = avatar_cue.model_copy(update={"blend_mode": "layer"})
                elif point.visual.clip_id is None:
                    point.visual.clip_id = clip_id
                    point.visual.blend_mode = "layer"
