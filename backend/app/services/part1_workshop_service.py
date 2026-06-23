import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import AsyncIterator, Literal

from app.core.config import settings
from app.director.cues.cue_models import CuePoint, CuePointTrigger, DramaturgyDecision, LightCue, SoundCue, VisualCue
from app.director.cues.cue_points import min_cue_points_for_text
from app.director.dramaturgy.llm_director import LLMDirector
from app.director.dramaturgy.rules_text import dramaturgy_rules_excerpt
from app.director.outputs.osc_commands import build_osc_commands
from app.schemas.part1_selection import MediaSelectionLists, Part1BaerenklauSelection, PreviewCue
from app.schemas.script import DiscussionTurn, ScriptBeat
from app.services.ai_service import AIService
from app.services.dramaturg_labels import CHATGPT_LABEL, CLAUDE_LABEL
from app.services.part1_selection_store import get_part1_selection_store
from app.services.part1_selection_validation import Part1SelectionValidationError, validate_media_lists
from app.services.preview_executor import PreviewExecutor, build_preview_cue, fallback_baerenklau_selection_from_catalog
from app.services.script_splitter import dramaturgy_quote_excerpts, part1_scene_label
from app.services.spoken_text import spoken_discussion_text

_logger = logging.getLogger("theatermaschine.part1.workshop")

EventType = Literal[
    "thinking",
    "discussion_turn",
    "preview_start",
    "preview_end",
    "media_selection",
    "agreement_saved",
    "dramaturgy_decision",
    "beat_done",
    "error",
    "done",
]

WorkshopPhase = Literal[
    "theme_discussion",
    "chatgpt_theme",
    "claude_proposal",
    "chatgpt_delta",
    "claude_handoff",
    "preview",
    "final",
]


@dataclass
class Part1WorkshopEvent:
    type: EventType
    beat_id: str | None = None
    beat_order: int | None = None
    speaker: str | None = None
    content: str | None = None
    dramaturgy: dict | None = None
    planned_commands: list[dict] | None = None
    discussion_turns: list[dict] | None = None
    discussion_summary: str | None = None
    preview: dict | None = None
    media_selection: dict | None = None
    part1_selection: dict | None = None
    workshop_phase: str | None = None
    detail: str | None = None


def _system_prompt() -> str:
    rules = dramaturgy_rules_excerpt(max_chars=settings.dramaturgy_rules_excerpt_chars)
    return f"""Ihr seid Claude und ChatGPT — zwei KI-Dramaturgen für Teil 1 einer Theateraufführung.
Analysiert den **gesamten** Stücktext als Ganzes (nicht in Abschnitte zerlegen).
Führt ein lebendiges Gespräch auf Deutsch: Thema, Stimmung, mindestens 2 Zitate aus verschiedenen Stellen.
Begründet **jede einzelne** Medienwahl dramaturgisch mit «Zitat aus dem Text» oder Thema: … (z. B. Kälte, Verwaltung, Ökonomie).
Format pro Medium: - sound_id — «Zitat» / Thema: …
Kein JSON in den ersten beiden Beiträgen. Ab dem Medienpaket-Vorschlag am Ende optional ein JSON-Block:
```json
{{"sounds":["id",...],"music":["id"],"videos":["id",...],"lights":["id",...]}}
```
Nur IDs aus dem Katalog. Mindestens 6 Sounds, 1 Musik, 6 Videos, 6 Lichtstimmungen im finalen Paket.
Schließt mit einem klaren Übergang: der Stücktext wird gleich aufgeführt — die Regie drückt Play wenn sie bereit ist.

=== REGELWERK ===
{rules}"""


def _parse_media_json(raw: str) -> MediaSelectionLists | None:
    cleaned = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        match = re.search(r"\{[^{}]*\"sounds\"[^{}]*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
    try:
        data = json.loads(cleaned)
        return MediaSelectionLists(
            sounds=list(data.get("sounds", [])),
            music=list(data.get("music", [])),
            videos=list(data.get("videos", [])),
            lights=list(data.get("lights", [])),
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _preview_items(lists: MediaSelectionLists) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for sound_id in lists.sounds:
        items.append(("sound", sound_id))
    for music_id in lists.music:
        items.append(("music", music_id))
    for video_id in lists.videos:
        items.append(("video", video_id))
    for light_id in lists.lights:
        items.append(("light", light_id))
    return items


def _validate_or_fallback(lists: MediaSelectionLists | None) -> MediaSelectionLists:
    if lists is None:
        sounds, music, videos, lights = fallback_baerenklau_selection_from_catalog()
        return MediaSelectionLists(sounds=sounds, music=music, videos=videos, lights=lights)
    try:
        return validate_media_lists(lists)
    except Part1SelectionValidationError:
        sounds, music, videos, lights = fallback_baerenklau_selection_from_catalog()
        return MediaSelectionLists(sounds=sounds, music=music, videos=videos, lights=lights)


def dramaturgy_from_part1_selection(
    selection: Part1BaerenklauSelection,
    beat: ScriptBeat,
) -> DramaturgyDecision:
    points: list[CuePoint] = []
    sentences = max(1, min_cue_points_for_text(beat.text))
    for index in range(sentences):
        sound_id = selection.final_sounds[index % len(selection.final_sounds)]
        video_id = selection.final_videos[index % len(selection.final_videos)]
        light_id = selection.final_lights[index % len(selection.final_lights)]
        music_id = selection.final_music[index % len(selection.final_music)] if selection.final_music else None
        trigger = CuePointTrigger.START if index == 0 else CuePointTrigger.SENTENCE_END
        point = CuePoint(
            trigger=trigger,
            sentence_index=index if index else None,
            function="verstärken",
            intensity=0.2 + (index / sentences) * 0.15,
            visual=VisualCue(clip_id=video_id, blend_mode="replace"),
            sound=SoundCue(cue_id=sound_id, volume=0.55),
            light=LightCue(scene_id=light_id, intensity=0.45),
        )
        if music_id and index == 0:
            point.sound = SoundCue(cue_id=music_id, volume=0.5)
        points.append(point)
    return DramaturgyDecision(
        reason=selection.dramaturgical_reading or selection.cue_strategy,
        dramaturgical_reading=selection.dramaturgical_reading,
        cue_points=points,
        intensity=0.25,
        mood="kontrolliert",
    )


class Part1WorkshopService:
    def __init__(
        self,
        ai_service: AIService | None = None,
        llm_director: LLMDirector | None = None,
        preview: PreviewExecutor | None = None,
    ) -> None:
        self.ai = ai_service or AIService()
        self.llm = llm_director or LLMDirector(ai_service=self.ai)
        self.preview = preview or PreviewExecutor()
        self.selection_store = get_part1_selection_store()

    def _validate_providers(self) -> None:
        if "openai" not in self.ai.providers:
            raise ValueError("OpenAI is not configured")
        if "anthropic" not in self.ai.providers:
            raise ValueError("Anthropic is not configured")

    async def _generate_turn(
        self,
        *,
        role: str,
        model: str,
        beat: ScriptBeat,
        title: str,
        catalog_hint: str,
        discussion_lines: list[str],
        instruction: str,
        include_json_hint: bool = False,
    ) -> str:
        scene_label = part1_scene_label(beat)
        quotes = dramaturgy_quote_excerpts(beat.text)
        quote_block = "\n".join(f"- «{q}»" for q in quotes) if quotes else "(keine extrahiert)"
        context = "\n\n".join(discussion_lines) if discussion_lines else "(noch keine Diskussion)"
        text_excerpt = beat.text[: settings.dramaturgy_whole_text_max_chars]
        json_note = (
            " Am Ende ein JSON-Block mit sounds/music/videos/lights."
            if include_json_hint
            else " Kein JSON in dieser Antwort — nur Gespräch."
        )
        prompt = (
            f"Stück: {title}\n{scene_label}:\n{text_excerpt}\n\n"
            f"Zitate/Stichworte aus dem Gesamttext:\n{quote_block}\n\n"
            f"Medien-Katalog (Auszug):\n{catalog_hint}\n\n"
            f"Bisheriges Gespräch:\n{context}\n\n{instruction}{json_note}\n\n"
            f"Maximal {settings.dramaturgy_statement_max_chars} Zeichen."
        )
        raw = await self.ai.generate(
            role,
            model,
            [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": prompt},
            ],
            max_tokens=settings.dramaturgy_discussion_max_tokens,
        )
        return raw.strip()

    def _record_turn(
        self,
        discussion_lines: list[str],
        discussion_turns: list[DiscussionTurn],
        *,
        speaker: Literal["openai", "anthropic"],
        raw: str,
    ) -> None:
        label = CLAUDE_LABEL if speaker == "anthropic" else CHATGPT_LABEL
        discussion_lines.append(f"{label}: {raw}")
        discussion_turns.append(
            DiscussionTurn(speaker=speaker, content=spoken_discussion_text(raw))
        )

    async def _preview_lists(
        self,
        lists: MediaSelectionLists,
        *,
        beat: ScriptBeat,
    ) -> AsyncIterator[Part1WorkshopEvent]:
        for medium, medium_id in _preview_items(lists):
            preview = build_preview_cue(medium, medium_id)  # type: ignore[arg-type]
            yield Part1WorkshopEvent(
                type="preview_start",
                beat_id=beat.id,
                beat_order=beat.order,
                preview=preview.model_dump(mode="json"),
                workshop_phase="preview",
            )
            await self.preview.run_preview(preview)
            yield Part1WorkshopEvent(
                type="preview_end",
                beat_id=beat.id,
                beat_order=beat.order,
                preview=preview.model_dump(mode="json"),
                workshop_phase="preview",
            )

    async def _discussion_event(
        self,
        *,
        beat: ScriptBeat,
        speaker: Literal["openai", "anthropic"],
        raw: str,
        discussion_turns: list[DiscussionTurn],
        workshop_phase: WorkshopPhase,
        media_selection: MediaSelectionLists | None = None,
    ) -> Part1WorkshopEvent:
        payload: dict = {
            "type": "discussion_turn",
            "beat_id": beat.id,
            "beat_order": beat.order,
            "speaker": speaker,
            "content": raw,
            "discussion_turns": [t.model_dump(mode="json") for t in discussion_turns],
            "workshop_phase": workshop_phase,
        }
        if media_selection is not None:
            payload["media_selection"] = media_selection.model_dump()
        return Part1WorkshopEvent(**payload)

    async def run_stream(
        self,
        *,
        script_id: str,
        title: str,
        beat: ScriptBeat,
        openai_model: str,
        anthropic_model: str,
    ) -> AsyncIterator[Part1WorkshopEvent]:
        self._validate_providers()
        catalog_hint = str(self.llm.catalog_allowlist(compact=True))[:1200]
        discussion_lines: list[str] = []
        discussion_turns: list[DiscussionTurn] = []

        try:
            # 1 — Claude: Thema, Zitate, Stichworte (kein Preview, kein JSON)
            yield Part1WorkshopEvent(
                type="thinking",
                beat_id=beat.id,
                beat_order=beat.order,
                speaker="anthropic",
                workshop_phase="theme_discussion",
            )
            claude_theme = await self._generate_turn(
                role="anthropic",
                model=anthropic_model,
                beat=beat,
                title=title,
                catalog_hint=catalog_hint,
                discussion_lines=discussion_lines,
                instruction=(
                    f"Du bist {CLAUDE_LABEL} und eröffnest das Gespräch über den **gesamten** Text. "
                    "Nenne das übergreifende Thema in 2–3 Sätzen, zitiere mindestens 2 kurze Stellen aus verschiedenen Passagen. "
                    "Skizziere die Grundstimmung — noch keine konkrete Medienliste."
                ),
            )
            self._record_turn(discussion_lines, discussion_turns, speaker="anthropic", raw=claude_theme)
            yield await self._discussion_event(
                beat=beat,
                speaker="anthropic",
                raw=claude_theme,
                discussion_turns=discussion_turns,
                workshop_phase="theme_discussion",
            )

            # 2 — ChatGPT: Reaktion auf Thema
            yield Part1WorkshopEvent(
                type="thinking",
                beat_id=beat.id,
                beat_order=beat.order,
                speaker="openai",
                workshop_phase="chatgpt_theme",
            )
            gpt_theme = await self._generate_turn(
                role="openai",
                model=openai_model,
                beat=beat,
                title=title,
                catalog_hint=catalog_hint,
                discussion_lines=discussion_lines,
                instruction=(
                    f"Du bist {CHATGPT_LABEL}. Greife {CLAUDE_LABEL}s Gesamtlektüre auf, ergänze ein weiteres Zitat oder Thema, "
                    "und formuliere 1–2 dramaturgische Impulse für Sound/Video/Licht — noch ohne feste IDs."
                ),
            )
            self._record_turn(discussion_lines, discussion_turns, speaker="openai", raw=gpt_theme)
            yield await self._discussion_event(
                beat=beat,
                speaker="openai",
                raw=gpt_theme,
                discussion_turns=discussion_turns,
                workshop_phase="chatgpt_theme",
            )

            # 3 — Claude: Medienpaket mit Begründungen (kein Preview)
            yield Part1WorkshopEvent(
                type="thinking",
                beat_id=beat.id,
                beat_order=beat.order,
                speaker="anthropic",
                workshop_phase="claude_proposal",
            )
            claude_raw = await self._generate_turn(
                role="anthropic",
                model=anthropic_model,
                beat=beat,
                title=title,
                catalog_hint=catalog_hint,
                discussion_lines=discussion_lines,
                instruction=(
                    f"Du bist {CLAUDE_LABEL}. Schlage ein konkretes Medienpaket für den **gesamten** Text vor: "
                    "6 Sounds, 1 Musik, 6 Videos, 6 Lichtstimmungen. "
                    "Begründe **jede einzelne** Wahl mit «Zitat» oder Thema: … im Format `- sound_id — «…» / Thema: …`. "
                    "Reihenfolge: Sounds/Musik, Videos, Licht."
                ),
                include_json_hint=True,
            )
            claude_lists = _validate_or_fallback(_parse_media_json(claude_raw))
            self._record_turn(discussion_lines, discussion_turns, speaker="anthropic", raw=claude_raw)
            yield await self._discussion_event(
                beat=beat,
                speaker="anthropic",
                raw=claude_raw,
                discussion_turns=discussion_turns,
                workshop_phase="claude_proposal",
                media_selection=claude_lists,
            )

            # 4 — ChatGPT: Gegenvorschlag / Feintuning (kein Preview)
            yield Part1WorkshopEvent(
                type="thinking",
                beat_id=beat.id,
                beat_order=beat.order,
                speaker="openai",
                workshop_phase="chatgpt_delta",
            )
            gpt_raw = await self._generate_turn(
                role="openai",
                model=openai_model,
                beat=beat,
                title=title,
                catalog_hint=catalog_hint,
                discussion_lines=discussion_lines,
                instruction=(
                    f"Du bist {CHATGPT_LABEL}. Reagiere auf {CLAUDE_LABEL}s Paket: "
                    "was passt, was würdest du tauschen und warum (jeweils mit «Zitat» oder Thema). "
                    "Liefere das verhandelte Gesamtpaket im JSON."
                ),
                include_json_hint=True,
            )
            gpt_lists = _parse_media_json(gpt_raw)
            merged = _validate_or_fallback(
                MediaSelectionLists(
                    sounds=(gpt_lists.sounds if gpt_lists else []) or claude_lists.sounds,
                    music=(gpt_lists.music if gpt_lists else []) or claude_lists.music,
                    videos=(gpt_lists.videos if gpt_lists else []) or claude_lists.videos,
                    lights=(gpt_lists.lights if gpt_lists else []) or claude_lists.lights,
                )
            )
            self._record_turn(discussion_lines, discussion_turns, speaker="openai", raw=gpt_raw)
            yield await self._discussion_event(
                beat=beat,
                speaker="openai",
                raw=gpt_raw,
                discussion_turns=discussion_turns,
                workshop_phase="chatgpt_delta",
                media_selection=merged,
            )

            # 5 — Claude: Einigung + Übergang zur Aufführung (kein Preview)
            yield Part1WorkshopEvent(
                type="thinking",
                beat_id=beat.id,
                beat_order=beat.order,
                speaker="anthropic",
                workshop_phase="claude_handoff",
            )
            final_raw = await self._generate_turn(
                role="anthropic",
                model=anthropic_model,
                beat=beat,
                title=title,
                catalog_hint=catalog_hint,
                discussion_lines=discussion_lines,
                instruction=(
                    f"Du bist {CLAUDE_LABEL}. Fasst die finale Einigung für den **gesamten** Text zusammen (sinngemäß: "
                    "«Dann einigen wir uns auf folgende Variante …»). "
                    "Jede Medien-ID nochmals mit «Zitat» oder Thema begründen. "
                    "Erkläre kurz, dass der Stücktext jetzt aufgeführt wird — die Regie startet mit Play, "
                    "wenn sie bereit ist. Teil 2 (Anarchie) startet separat später. "
                    "JSON mit den finalen Medien-IDs."
                ),
                include_json_hint=True,
            )
            final_lists = _validate_or_fallback(_parse_media_json(final_raw) or merged)
            self._record_turn(discussion_lines, discussion_turns, speaker="anthropic", raw=final_raw)
            yield await self._discussion_event(
                beat=beat,
                speaker="anthropic",
                raw=final_raw,
                discussion_turns=discussion_turns,
                workshop_phase="claude_handoff",
                media_selection=final_lists,
            )

            # 6 — Previews erst nach abgeschlossenem Gespräch
            async for event in self._preview_lists(final_lists, beat=beat):
                yield event

            selection = Part1BaerenklauSelection(
                script_id=script_id,
                beat_id=beat.id,
                final_sounds=final_lists.sounds,
                final_music=final_lists.music,
                final_videos=final_lists.videos,
                final_lights=final_lists.lights,
                dramaturgical_reading=spoken_discussion_text(final_raw)[:500],
                cue_strategy="Teil 1 — Gesamttext, finale KI-Einigung nach Dramaturgen-Gespräch",
                discussion_turns=discussion_turns,
                created_at=datetime.now(UTC),
            )
            self.selection_store.save(selection)
            decision = dramaturgy_from_part1_selection(selection, beat)
            planned = build_osc_commands(decision, dry_run=True)

            yield Part1WorkshopEvent(
                type="agreement_saved",
                beat_id=beat.id,
                beat_order=beat.order,
                part1_selection=selection.model_dump(mode="json"),
                workshop_phase="final",
            )
            yield Part1WorkshopEvent(
                type="dramaturgy_decision",
                beat_id=beat.id,
                beat_order=beat.order,
                dramaturgy=decision.model_dump(mode="json"),
                planned_commands=[c.model_dump(mode="json") for c in planned],
                discussion_turns=[t.model_dump(mode="json") for t in discussion_turns],
                discussion_summary="\n".join(discussion_lines),
            )
            yield Part1WorkshopEvent(
                type="beat_done",
                beat_id=beat.id,
                beat_order=beat.order,
                discussion_turns=[t.model_dump(mode="json") for t in discussion_turns],
                discussion_summary="\n".join(discussion_lines),
                part1_selection=selection.model_dump(mode="json"),
            )
        except Exception as exc:
            _logger.exception("part1 workshop failed")
            yield Part1WorkshopEvent(
                type="error",
                beat_id=beat.id,
                beat_order=beat.order,
                detail=str(exc),
            )
            return

        yield Part1WorkshopEvent(type="done")
