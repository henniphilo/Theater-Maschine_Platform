from datetime import UTC, datetime

from app.director.dialogue.models import DialogueEvent, DialogueSpeaker
from app.director.dramaturgy.rules import analyze_text


def map_debate_speaker(speaker: str) -> DialogueSpeaker:
    if speaker == "anthropic":
        return DialogueSpeaker.AI_B
    return DialogueSpeaker.AI_A


def build_dialogue_event(
    *,
    speaker: str,
    text: str,
    topic: str,
    created_at: datetime | None = None,
    show_elapsed: float | None = None,
) -> DialogueEvent:
    analysis = analyze_text(text, topic)
    ts = show_elapsed
    if ts is None and created_at is not None:
        ts = created_at.timestamp()
    elif ts is None:
        ts = datetime.now(UTC).timestamp()

    return DialogueEvent(
        speaker=map_debate_speaker(speaker),
        text=text.strip(),
        topic=topic.strip(),
        mood=analysis.mood,
        intensity=analysis.intensity,
        tags=analysis.tags,
        timestamp=ts,
        created_at=created_at or datetime.now(UTC),
    )
