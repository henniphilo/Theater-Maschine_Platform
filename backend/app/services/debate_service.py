from dataclasses import dataclass
from datetime import UTC, datetime
from typing import AsyncIterator, Literal

from app.services.ai_service import AIService

DEBATE_MAX_TOKENS = 220

OPENAI_DEBATE_SYSTEM = """You are in a casual face-to-face chat with another person about a topic.
Speak like real people: short, simple sentences. React naturally ("Ja, aber...", "Stimmt, allerdings...").
Max 3–5 sentences, ~60–80 words. No lists, no essay tone, no lecturing.
Use everyday language. Match the topic language. Never say you are an AI or a model."""

ANTHROPIC_DEBATE_SYSTEM = """You are in a casual face-to-face chat with another person about a topic.
Speak like real people: short, simple sentences. React naturally ("Ja, aber...", "Stimmt, allerdings...").
Max 3–5 sentences, ~60–80 words. No lists, no essay tone, no lecturing.
Use everyday language. Match the topic language. Never say you are an AI or a model."""

EventType = Literal["thinking", "turn", "done", "error"]


@dataclass
class TurnResult:
    speaker: str
    content: str
    model: str
    created_at: datetime


@dataclass
class DebateEvent:
    type: EventType
    speaker: str | None = None
    content: str | None = None
    model: str | None = None
    created_at: datetime | None = None
    conversation_id: str | None = None
    topic: str | None = None
    detail: str | None = None


def _format_transcript(turns: list[TurnResult]) -> str:
    lines: list[str] = []
    for t in turns:
        label = "Partner" if t.speaker == "openai" else "Gegenüber"
        lines.append(f"{label}:\n{t.content}")
    return "\n\n".join(lines)


class DebateService:
    def __init__(self, ai_service: AIService | None = None) -> None:
        self.ai = ai_service or AIService()

    def _validate_providers(self) -> None:
        if "openai" not in self.ai.providers:
            raise ValueError("OpenAI is not configured (set OPENAI_API_KEY)")
        if "anthropic" not in self.ai.providers:
            raise ValueError("Anthropic is not configured (set ANTHROPIC_API_KEY)")

    async def _openai_turn(
        self, topic: str, turns: list[TurnResult], openai_model: str, *, opening: bool
    ) -> str:
        if opening and not turns:
            user = f"Thema: {topic}\n\nDu fängst an. Sag kurz und locker, was du denkst."
        elif turns and turns[-1].speaker == "anthropic":
            user = (
                f"Thema: {topic}\n\nDein Gegenüber hat gerade gesagt:\n\"{turns[-1].content}\"\n\n"
                "Antworte natürlich, als würdet ihr euch unterhalten."
            )
        else:
            user = (
                f"Thema: {topic}\n\nBisher:\n{_format_transcript(turns)}\n\n"
                "Antworte natürlich auf den letzten Punkt."
            )
        return await self.ai.generate(
            "openai",
            openai_model,
            [
                {"role": "system", "content": f"{OPENAI_DEBATE_SYSTEM}\n\nTopic: {topic}"},
                {"role": "user", "content": user},
            ],
            max_tokens=DEBATE_MAX_TOKENS,
        )

    async def _anthropic_turn(
        self, topic: str, turns: list[TurnResult], anthropic_model: str
    ) -> str:
        last_gpt = next((t for t in reversed(turns) if t.speaker == "openai"), None)
        if last_gpt:
            user = (
                f"Thema: {topic}\n\nDein Gegenüber hat gerade gesagt:\n\"{last_gpt.content}\"\n\n"
                "Antworte natürlich, als würdet ihr euch unterhalten."
            )
        else:
            user = f"Thema: {topic}\n\nAntworte locker auf den anderen."
        return await self.ai.generate(
            "anthropic",
            anthropic_model,
            [
                {"role": "system", "content": f"{ANTHROPIC_DEBATE_SYSTEM}\n\nTopic: {topic}"},
                {"role": "user", "content": user},
            ],
            max_tokens=DEBATE_MAX_TOKENS,
        )

    async def run_stream(
        self,
        topic: str,
        rounds: int,
        openai_model: str,
        anthropic_model: str,
        prior_turns: list[TurnResult] | None = None,
    ) -> AsyncIterator[DebateEvent]:
        self._validate_providers()
        turns: list[TurnResult] = list(prior_turns or [])
        opening = not turns

        try:
            for _ in range(rounds):
                yield DebateEvent(type="thinking", speaker="openai")
                openai_reply = await self._openai_turn(
                    topic, turns, openai_model, opening=opening
                )
                opening = False
                openai_turn = TurnResult(
                    speaker="openai",
                    content=openai_reply,
                    model=openai_model,
                    created_at=datetime.now(UTC),
                )
                turns.append(openai_turn)
                yield DebateEvent(
                    type="turn",
                    speaker=openai_turn.speaker,
                    content=openai_turn.content,
                    model=openai_turn.model,
                    created_at=openai_turn.created_at,
                )

                yield DebateEvent(type="thinking", speaker="anthropic")
                anthropic_reply = await self._anthropic_turn(topic, turns, anthropic_model)
                anthropic_turn = TurnResult(
                    speaker="anthropic",
                    content=anthropic_reply,
                    model=anthropic_model,
                    created_at=datetime.now(UTC),
                )
                turns.append(anthropic_turn)
                yield DebateEvent(
                    type="turn",
                    speaker=anthropic_turn.speaker,
                    content=anthropic_turn.content,
                    model=anthropic_turn.model,
                    created_at=anthropic_turn.created_at,
                )
        except Exception as exc:
            yield DebateEvent(type="error", detail=str(exc))
            return

    async def run(
        self,
        topic: str,
        rounds: int,
        openai_model: str,
        anthropic_model: str,
        prior_turns: list[TurnResult] | None = None,
    ) -> list[TurnResult]:
        results: list[TurnResult] = []
        async for event in self.run_stream(topic, rounds, openai_model, anthropic_model, prior_turns):
            if event.type == "turn" and event.speaker and event.content and event.model and event.created_at:
                results.append(
                    TurnResult(
                        speaker=event.speaker,
                        content=event.content,
                        model=event.model,
                        created_at=event.created_at,
                    )
                )
            if event.type == "error":
                raise RuntimeError(event.detail or "Debate failed")
        return results
