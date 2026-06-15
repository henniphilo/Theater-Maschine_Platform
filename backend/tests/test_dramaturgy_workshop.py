import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision, LightCue, SoundCue, VisualCue, VisualAction
from app.schemas.script import ScriptBeat
from app.services.dramaturgy_workshop_service import DramaturgyWorkshopService


def _beat(text: str = "Erinnerung ist eine Störung.") -> ScriptBeat:
    return ScriptBeat(id="beat-1", order=0, text=text, speaker="AI_A")


def _sample_decision() -> DramaturgyDecision:
    return DramaturgyDecision(
        visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde"),
        sound=SoundCue(cue_id="maschinen_grundader"),
        light=LightCue(scene_id="vorbuehnenzug"),
        reason="Testentscheidung",
        mood="melancholisch",
        intensity=0.5,
    )


@pytest.fixture
def workshop(monkeypatch: pytest.MonkeyPatch) -> DramaturgyWorkshopService:
    monkeypatch.setattr(settings, "dramaturgy_statements_per_dramaturg", 2)

    ai = MagicMock()
    ai.providers = {"openai": MagicMock(), "anthropic": MagicMock()}
    call_count = {"n": 0}

    async def fake_generate(provider: str, model: str, messages: list, max_tokens: int = 2048) -> str:
        call_count["n"] += 1
        return f"{provider} statement {call_count['n']}"

    ai.generate = AsyncMock(side_effect=fake_generate)

    llm = MagicMock()
    llm.catalog_allowlist.return_value = {"videos": [], "sounds": [], "lights": []}
    llm.decide = AsyncMock(return_value=_sample_decision())

    return DramaturgyWorkshopService(ai_service=ai, llm_director=llm)


async def _collect_events(service: DramaturgyWorkshopService) -> list:
    events = []
    async for event in service.run_stream(
        title="Teststück",
        beats=[_beat()],
        openai_model="gpt-4o",
        anthropic_model="claude-sonnet-4-6",
    ):
        events.append(event)
    return events


def test_workshop_sequential_turns_max_four(workshop: DramaturgyWorkshopService) -> None:
    events = asyncio.run(_collect_events(workshop))

    turn_events = [e for e in events if e.type == "discussion_turn"]
    assert len(turn_events) == 4
    assert [e.speaker for e in turn_events] == ["openai", "anthropic", "openai", "anthropic"]

    decision = next(e for e in events if e.type == "dramaturgy_decision")
    assert decision.discussion_turns is not None
    assert len(decision.discussion_turns) == 4
    assert decision.discussion_summary
    assert "Dramaturg A (GPT)" in decision.discussion_summary
    assert "Dramaturg B (Claude)" in decision.discussion_summary

    speakers = [t["speaker"] for t in decision.discussion_turns]
    assert speakers == ["openai", "anthropic", "openai", "anthropic"]


def test_workshop_respects_statements_per_dramaturg(
    workshop: DramaturgyWorkshopService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "dramaturgy_statements_per_dramaturg", 1)
    events = asyncio.run(_collect_events(workshop))
    turn_events = [e for e in events if e.type == "discussion_turn"]
    assert len(turn_events) == 2
    assert [e.speaker for e in turn_events] == ["openai", "anthropic"]


def test_workshop_clamps_long_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dramaturgy_statements_per_dramaturg", 1)
    monkeypatch.setattr(settings, "dramaturgy_statement_max_chars", 80)

    ai = MagicMock()
    ai.providers = {"openai": MagicMock(), "anthropic": MagicMock()}
    long_text = "Wort " * 50

    async def fake_generate(provider: str, model: str, messages: list, max_tokens: int = 2048) -> str:
        return long_text

    ai.generate = AsyncMock(side_effect=fake_generate)
    llm = MagicMock()
    llm.catalog_allowlist.return_value = {"videos": [], "sounds": [], "lights": []}
    llm.decide = AsyncMock(return_value=_sample_decision())
    service = DramaturgyWorkshopService(ai_service=ai, llm_director=llm)

    events = asyncio.run(_collect_events(service))
    turn = next(e for e in events if e.type == "discussion_turn")
    assert turn.content is not None
    assert len(turn.content) <= 80
