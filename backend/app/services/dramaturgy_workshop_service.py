from dataclasses import dataclass
from datetime import UTC, datetime
from typing import AsyncIterator, Literal

from app.director.cues.cue_points import min_cue_points_for_text
from app.director.dialogue.builder import build_dialogue_event
from app.director.dramaturgy.rules_text import dramaturgy_rules_excerpt
from app.director.dramaturgy.llm_director import LLMDirector
from app.director.outputs.osc_commands import build_osc_commands
from app.schemas.script import ScriptBeat
from app.services.ai_service import AIService

def _dramaturgy_system_prompt() -> str:
    rules = dramaturgy_rules_excerpt(max_chars=6000)
    return f"""Ihr seid zwei Theater-Dramaturgen in einem Workshop (Bühne Unter Tieren).
Diskutiert ausschließlich die Regie für den gegebenen Textabschnitt: Video, Sound, Licht.
Alle Empfehlungen müssen dem Dramaturgie-Regelwerk folgen und als OSC-Cues umsetzbar sein.
Nur existierende clip_id aus media/video, recording_id aus media/recordings, Sound nur dummy_* Cues.
Licht nur scene_id aus der Kanal-Übersicht (Kanal Übersicht.xlsx).
Keine Illustration, keine Schauspiel- oder Bühnenanweisungen, keine erfundenen Medien.
Nennt dramaturgische Funktion (verstärken, widersprechen, entlarven, überlagern, reduzieren …).
Geht den Textabschnitt Satz für Satz durch — nennt Schlüsselwörter, Stimmungswechsel und mehrere Cue-Punkte.
Jeder Beitrag: 5–8 Sätze, konkret zu Video-, Sound- und Licht-Cues. Kein allgemeines Pro/Contra.

=== DRAMATURGIE-REGELWERK ===
{rules}"""

OPENAI_DRAMATURGE = "Dramaturg A (GPT)"
ANTHROPIC_DRAMATURGE = "Dramaturg B (Claude)"

EventType = Literal["thinking", "discussion_turn", "dramaturgy_decision", "beat_done", "error", "done"]


@dataclass
class WorkshopEvent:
    type: EventType
    beat_id: str | None = None
    beat_order: int | None = None
    speaker: str | None = None
    content: str | None = None
    dramaturgy: dict | None = None
    planned_commands: list[dict] | None = None
    discussion_summary: str | None = None
    detail: str | None = None


class DramaturgyWorkshopService:
    def __init__(
        self,
        ai_service: AIService | None = None,
        llm_director: LLMDirector | None = None,
    ) -> None:
        self.ai = ai_service or AIService()
        self.llm_director = llm_director or LLMDirector(ai_service=self.ai)

    def _validate_providers(self) -> None:
        if "openai" not in self.ai.providers:
            raise ValueError("OpenAI is not configured (set OPENAI_API_KEY)")
        if "anthropic" not in self.ai.providers:
            raise ValueError("Anthropic is not configured (set ANTHROPIC_API_KEY)")

    def _discussion_rounds_for_beat(self, beat: ScriptBeat, requested: int) -> int:
        extra = len(beat.text) // 400
        return min(6, max(requested, 2 + extra))

    def _discussion_user_prompt(
        self,
        beat: ScriptBeat,
        title: str,
        catalog_hint: str,
        prior: list[str],
        *,
        role: str,
    ) -> str:
        context = "\n\n".join(prior) if prior else "(noch keine Diskussion)"
        min_cues = min_cue_points_for_text(beat.text)
        action = (
            "Ergänze oder widersprich mit einer ausführlichen Regie-Empfehlung."
            if role == "openai"
            else "Antworte auf die letzte Empfehlung — vertiefe oder widersprich mit konkreten Cues."
        )
        return (
            f"Stück: {title}\n"
            f"Textabschnitt ({len(beat.text)} Zeichen):\n{beat.text}\n\n"
            f"Ziel: mindestens {min_cues} Cue-Punkte (start, keyword, sentence_end) für diesen Abschnitt.\n"
            f"Medien-Katalog (Auszug):\n{catalog_hint}\n\n"
            f"Bisherige Dramaturgie-Diskussion:\n{context}\n\n"
            f"{action} Beziehe dich auf konkrete Textstellen."
        )

    async def run_stream(
        self,
        *,
        title: str,
        beats: list[ScriptBeat],
        openai_model: str,
        anthropic_model: str,
        discussion_rounds: int = 1,
    ) -> AsyncIterator[WorkshopEvent]:
        self._validate_providers()
        catalog_hint = str(self.llm_director.catalog_allowlist())[:1200]

        for beat in beats:
            discussion_lines: list[str] = []
            beat_rounds = self._discussion_rounds_for_beat(beat, discussion_rounds)
            try:
                for _round in range(beat_rounds):
                    yield WorkshopEvent(type="thinking", beat_id=beat.id, beat_order=beat.order, speaker="openai")
                    gpt = await self.ai.generate(
                        "openai",
                        openai_model,
                        [
                            {"role": "system", "content": _dramaturgy_system_prompt()},
                            {
                                "role": "user",
                                "content": self._discussion_user_prompt(
                                    beat, title, catalog_hint, discussion_lines, role="openai"
                                ),
                            },
                        ],
                        max_tokens=650,
                    )
                    discussion_lines.append(f"{OPENAI_DRAMATURGE}: {gpt}")
                    yield WorkshopEvent(
                        type="discussion_turn",
                        beat_id=beat.id,
                        beat_order=beat.order,
                        speaker="openai",
                        content=gpt,
                    )

                    yield WorkshopEvent(type="thinking", beat_id=beat.id, beat_order=beat.order, speaker="anthropic")
                    claude = await self.ai.generate(
                        "anthropic",
                        anthropic_model,
                        [
                            {"role": "system", "content": _dramaturgy_system_prompt()},
                            {
                                "role": "user",
                                "content": self._discussion_user_prompt(
                                    beat, title, catalog_hint, discussion_lines, role="anthropic"
                                ),
                            },
                        ],
                        max_tokens=650,
                    )
                    discussion_lines.append(f"{ANTHROPIC_DRAMATURGE}: {claude}")
                    yield WorkshopEvent(
                        type="discussion_turn",
                        beat_id=beat.id,
                        beat_order=beat.order,
                        speaker="anthropic",
                        content=claude,
                    )

                discussion_summary = "\n".join(discussion_lines)
                event = build_dialogue_event(
                    speaker="openai" if beat.speaker == "AI_A" else "anthropic",
                    text=beat.text,
                    topic=title,
                    created_at=datetime.now(UTC),
                )
                decision = await self.llm_director.decide(
                    event,
                    model=openai_model,
                    discussion_context=discussion_summary,
                )
                planned = build_osc_commands(decision, dry_run=True)

                yield WorkshopEvent(
                    type="dramaturgy_decision",
                    beat_id=beat.id,
                    beat_order=beat.order,
                    dramaturgy=decision.model_dump(mode="json"),
                    planned_commands=[c.model_dump(mode="json") for c in planned],
                    discussion_summary=discussion_summary,
                )
                yield WorkshopEvent(
                    type="beat_done",
                    beat_id=beat.id,
                    beat_order=beat.order,
                    discussion_summary=discussion_summary,
                )
            except Exception as exc:
                yield WorkshopEvent(
                    type="error",
                    beat_id=beat.id,
                    beat_order=beat.order,
                    detail=str(exc),
                )
                return

        yield WorkshopEvent(type="done")
