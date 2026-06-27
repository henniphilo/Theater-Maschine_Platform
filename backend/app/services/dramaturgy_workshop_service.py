from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import AsyncIterator, Literal

from app.core.config import settings
from app.director.cues.cue_points import min_cue_points_for_text
from app.director.dialogue.builder import build_dialogue_event
from app.director.dramaturgy.rules_text import dramaturgy_rules_excerpt
from app.director.dramaturgy.llm_director import LLMDirector
from app.director.outputs.osc_commands import build_osc_commands
from app.schemas.script import DiscussionTurn, ScriptBeat
from app.services.ai_service import AIService
from app.services.dramaturgy_text import clamp_statement
from app.services.script_splitter import beat_scene_label, dramaturgy_quote_excerpts


@lru_cache(maxsize=1)
def _dramaturgy_system_prompt() -> str:
    rules = dramaturgy_rules_excerpt(max_chars=settings.dramaturgy_rules_excerpt_chars)
    max_chars = settings.dramaturgy_statement_max_chars
    return f"""Ihr seid zwei KI-Dramaturgen (GPT und Claude) im Gespräch über die Bühne Unter Tieren.
Ihr ordnet den Textabschnitt inhaltlich ein und plant die Regie (Video, Sound, Licht).
Sprecht euch direkt an (Du-Form), nennt euch gegenseitig beim Namen (Dramaturg A / Dramaturg B).
Bezieht euch auf den Szentitel und den Text — mindestens ein kurzes wörtliches Zitat pro Beitrag (in «…»).
Der erste Beitrag zu einem Abschnitt nennt den Szentitel einmal beim Namen; danach reicht ein Bezug im Du-Gespräch.
Keine Illustration, keine Schauspielanweisungen, keine erfundenen Medien.
Jeder Beitrag: maximal {max_chars} Zeichen, 2–3 kurze Sätze — wie am Regietisch, nicht abstrakt.

=== DRAMATURGIE-REGELWERK (Auszug) ===
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
    discussion_turns: list[dict] | None = None
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
        scene_label = beat_scene_label(beat)
        quotes = dramaturgy_quote_excerpts(beat.text)
        quote_block = (
            "\n".join(f"- «{quote}»" for quote in quotes)
            if quotes
            else "- (kurze Formulierungen direkt aus dem Abschnitt wählen)"
        )
        if role == "openai":
            action = (
                "Du bist Dramaturg A (GPT). Nimm Bezug auf den Szentitel und zitiere mindestens "
                "eine Formulierung aus dem Text. Skizziere, wie Video, Sound und Licht darauf reagieren sollen."
            )
        else:
            action = (
                "Du bist Dramaturg B (Claude). Antworte direkt an Dramaturg A: ergänze, widersprich "
                "oder schärfe die Lesart — mit Bezug zum Szentitel und mindestens einem Textzitat."
            )
        return (
            f"Stück: {title}\n"
            f"Szentitel: {scene_label}\n"
            f"Textabschnitt ({len(beat.text)} Zeichen):\n{beat.text}\n\n"
            f"Formulierungen zum Zitieren:\n{quote_block}\n\n"
            f"Ziel für die spätere Regie: mindestens {min_cues} Cue-Punkte.\n"
            f"Medien-Katalog (Auszug):\n{catalog_hint}\n\n"
            f"Bisheriges Gespräch:\n{context}\n\n"
            f"{action}\n\nAntworte in maximal {settings.dramaturgy_statement_max_chars} Zeichen."
        )

    async def _generate_discussion_turn(
        self,
        *,
        beat: ScriptBeat,
        title: str,
        catalog_hint: str,
        discussion_lines: list[str],
        role: str,
        model: str,
    ) -> str:
        system = _dramaturgy_system_prompt()
        raw = await self.ai.generate(
            role,
            model,
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": self._discussion_user_prompt(
                        beat, title, catalog_hint, discussion_lines, role=role
                    ),
                },
            ],
            max_tokens=settings.dramaturgy_discussion_max_tokens,
        )
        return clamp_statement(raw)

    def _proposed_decision_for_turn(
        self,
        *,
        beat: ScriptBeat,
        turn_speaker: str,
        turn_content: str,
        title: str,
    ):
        try:
            event = build_dialogue_event(
                speaker=turn_speaker,
                text=turn_content,
                topic=f"{title}: {beat.text[:240]}",
                created_at=datetime.now(UTC),
            )
            return self.llm_director.rule_engine.decide(event)
        except Exception:
            return None

    async def run_stream(
        self,
        *,
        title: str,
        beats: list[ScriptBeat],
        openai_model: str,
        anthropic_model: str,
        discussion_rounds: int | None = None,
    ) -> AsyncIterator[WorkshopEvent]:
        del discussion_rounds  # fixed sequential flow; kept for API compatibility
        self._validate_providers()
        catalog_hint = str(self.llm_director.catalog_allowlist(compact=True))[:900]
        max_per_dramaturg = settings.dramaturgy_statements_per_dramaturg

        for beat in beats:
            discussion_lines: list[str] = []
            discussion_turns: list[DiscussionTurn] = []
            openai_count = 0
            anthropic_count = 0
            try:
                while openai_count < max_per_dramaturg or anthropic_count < max_per_dramaturg:
                    if openai_count < max_per_dramaturg:
                        yield WorkshopEvent(
                            type="thinking", beat_id=beat.id, beat_order=beat.order, speaker="openai"
                        )
                        gpt = await self._generate_discussion_turn(
                            beat=beat,
                            title=title,
                            catalog_hint=catalog_hint,
                            discussion_lines=discussion_lines,
                            role="openai",
                            model=openai_model,
                        )
                        discussion_lines.append(f"{OPENAI_DRAMATURGE}: {gpt}")
                        proposed = self._proposed_decision_for_turn(
                            beat=beat,
                            turn_speaker="openai",
                            turn_content=gpt,
                            title=title,
                        )
                        discussion_turns.append(
                            DiscussionTurn(speaker="openai", content=gpt, proposed_decision=proposed)
                        )
                        openai_count += 1
                        yield WorkshopEvent(
                            type="discussion_turn",
                            beat_id=beat.id,
                            beat_order=beat.order,
                            speaker="openai",
                            content=gpt,
                            discussion_turns=[t.model_dump(mode="json") for t in discussion_turns],
                        )

                    if anthropic_count >= max_per_dramaturg:
                        break

                    yield WorkshopEvent(
                        type="thinking", beat_id=beat.id, beat_order=beat.order, speaker="anthropic"
                    )
                    claude = await self._generate_discussion_turn(
                        beat=beat,
                        title=title,
                        catalog_hint=catalog_hint,
                        discussion_lines=discussion_lines,
                        role="anthropic",
                        model=anthropic_model,
                    )
                    discussion_lines.append(f"{ANTHROPIC_DRAMATURGE}: {claude}")
                    proposed = self._proposed_decision_for_turn(
                        beat=beat,
                        turn_speaker="anthropic",
                        turn_content=claude,
                        title=title,
                    )
                    discussion_turns.append(
                        DiscussionTurn(speaker="anthropic", content=claude, proposed_decision=proposed)
                    )
                    anthropic_count += 1
                    yield WorkshopEvent(
                        type="discussion_turn",
                        beat_id=beat.id,
                        beat_order=beat.order,
                        speaker="anthropic",
                        content=claude,
                        discussion_turns=[t.model_dump(mode="json") for t in discussion_turns],
                    )

                    if openai_count >= max_per_dramaturg and anthropic_count >= max_per_dramaturg:
                        break

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
                turns_payload = [t.model_dump(mode="json") for t in discussion_turns]

                yield WorkshopEvent(
                    type="dramaturgy_decision",
                    beat_id=beat.id,
                    beat_order=beat.order,
                    dramaturgy=decision.model_dump(mode="json"),
                    planned_commands=[c.model_dump(mode="json") for c in planned],
                    discussion_turns=turns_payload,
                    discussion_summary=discussion_summary,
                )
                yield WorkshopEvent(
                    type="beat_done",
                    beat_id=beat.id,
                    beat_order=beat.order,
                    discussion_turns=turns_payload,
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
