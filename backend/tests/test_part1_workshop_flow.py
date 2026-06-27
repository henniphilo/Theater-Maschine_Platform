import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.script import ScriptBeat
from app.services.part1_workshop_service import Part1WorkshopService


def _beat() -> ScriptBeat:
    return ScriptBeat(
        id="bk-1",
        order=0,
        text="Der Bärenklau wächst im Keller.",
        scene_title="Bärenklau",
        speaker="AI_A",
    )


def _theme_text() -> str:
    return "Das Thema ist Erinnerung als Störung — «vielleicht ist Erinnerung nur eine technische Störung»."


def _media_json() -> str:
    sounds = [f"s{i}" for i in range(6)]
    videos = [f"v{i}" for i in range(6)]
    lights = [f"l{i}" for i in range(6)]
    return (
        "Wir nehmen diese Variante.\n```json\n"
        + json.dumps({"sounds": sounds, "music": ["m1"], "videos": videos, "lights": lights})
        + "\n```"
    )


def _handoff_text() -> str:
    return _media_json() + " Dann wird der Text jetzt aufgeführt — Play wenn bereit."


@pytest.fixture
def workshop(monkeypatch: pytest.MonkeyPatch) -> Part1WorkshopService:
    ai = MagicMock()
    ai.providers = {"openai": MagicMock(), "anthropic": MagicMock()}
    responses = iter(
        [
            _theme_text(),
            _theme_text(),
            _media_json(),
            _media_json(),
            _handoff_text(),
        ]
    )

    async def fake_generate(provider: str, model: str, messages: list, max_tokens: int = 2048) -> str:
        return next(responses)

    ai.generate = AsyncMock(side_effect=fake_generate)
    llm = MagicMock()
    llm.catalog_allowlist.return_value = {"sounds": [], "videos": [], "lights": []}
    preview = MagicMock()
    preview.run_preview = AsyncMock(return_value=[])

    monkeypatch.setattr(
        "app.services.part1_workshop_service.validate_media_lists",
        lambda lists, **kwargs: lists,
    )
    monkeypatch.setattr(
        "app.services.part1_workshop_service.fallback_baerenklau_selection_from_catalog",
        lambda: ([f"s{i}" for i in range(6)], ["m1"], [f"v{i}" for i in range(6)], [f"l{i}" for i in range(6)]),
    )

    store = MagicMock()
    store.save = MagicMock(side_effect=lambda s: s)
    monkeypatch.setattr("app.services.part1_workshop_service.get_part1_selection_store", lambda: store)

    return Part1WorkshopService(ai_service=ai, llm_director=llm, preview=preview)


def test_part1_workshop_discussion_before_preview(workshop: Part1WorkshopService) -> None:
    async def run() -> list:
        events = []
        async for event in workshop.run_stream(
            script_id="s1",
            title="Test",
            beat=_beat(),
            openai_model="gpt-4o",
            anthropic_model="claude-sonnet-4-6",
        ):
            events.append(event)
        return events

    events = asyncio.run(run())
    turns = [e for e in events if e.type == "discussion_turn"]
    assert len(turns) == 5
    assert turns[0].speaker == "anthropic"
    assert turns[0].workshop_phase == "theme_discussion"
    assert turns[4].workshop_phase == "claude_handoff"

    first_preview_idx = next(i for i, e in enumerate(events) if e.type == "preview_start")
    last_turn_idx = max(i for i, e in enumerate(events) if e.type == "discussion_turn")
    assert first_preview_idx > last_turn_idx
    assert any(e.type == "agreement_saved" for e in events)

    assert "```json" not in turns[0].content
    assert turns[0].discussion_turns is not None
    assert "```json" not in turns[0].discussion_turns[0]["content"]


def _mood_proposal() -> str:
    return (
        "«Bärenklau» — maschinelles Summen, Grundader-Ton (Sound).\n"
        "«Keller» — kalte Bildschirmflächen (Video)."
    )


def test_part1_workshop_mood_turn_spoken_without_ids(workshop: Part1WorkshopService) -> None:
    workshop.llm.catalog_allowlist.return_value = {
        "sounds": [{"id": "maschinen_grundader", "tags": ["drone", "grundton"]}],
        "videos": [{"id": "macbook", "tags": []}],
        "lights": [],
    }
    ai = workshop.ai
    ai.generate = AsyncMock(
        side_effect=[
            _theme_text(),
            _theme_text(),
            _mood_proposal(),
            _mood_proposal(),
            _handoff_text(),
        ]
    )

    async def run() -> list:
        events = []
        async for event in workshop.run_stream(
            script_id="s1",
            title="Test",
            beat=_beat(),
            openai_model="gpt-4o",
            anthropic_model="claude-sonnet-4-6",
        ):
            events.append(event)
        return events

    events = asyncio.run(run())
    turns = [e for e in events if e.type == "discussion_turn"]
    stored = turns[2].discussion_turns[2]
    spoken = stored["content"]
    assert "maschinen_grundader" not in spoken
    assert "Beim Stichwort" in spoken
    mentions = stored["media_mentions"]
    assert len(mentions) >= 1
    assert all(m["char_offset"] < len(spoken) for m in mentions)


def test_part1_workshop_prompt_includes_full_text(workshop: Part1WorkshopService) -> None:
    long_text = "A" * 3500 + " Schluss."
    beat = ScriptBeat(id="bk-1", order=0, text=long_text, speaker="AI_A")

    async def run() -> None:
        async for event in workshop.run_stream(
            script_id="s1",
            title="Test",
            beat=beat,
            openai_model="gpt-4o",
            anthropic_model="claude-sonnet-4-6",
        ):
            if event.type == "discussion_turn":
                break

    asyncio.run(run())
    first_call = workshop.ai.generate.await_args_list[0]
    user_prompt = first_call.args[2][1]["content"]
    assert "Gesamttext" in user_prompt
    assert long_text[:3500] in user_prompt
    assert "Textauszug" not in user_prompt
