from app.director.dialogue.models import DialogueEvent, DialogueSpeaker
from app.director.dramaturgy.engine import DramaturgyEngine
from app.director.dramaturgy.rules import analyze_text
from app.director.media.database import MediaDatabase


def test_analyze_text_detects_memory_and_mood() -> None:
    analysis = analyze_text(
        "Vielleicht ist Erinnerung nur eine technische Störung.",
        topic="Erinnerung",
    )
    assert "memory" in analysis.tags
    assert analysis.mood in ("melancholisch", "unheimlich", "neutral")
    assert 0.0 <= analysis.intensity <= 1.0


def test_dramaturgy_engine_selects_matching_assets() -> None:
    engine = DramaturgyEngine(MediaDatabase())
    event = DialogueEvent(
        speaker=DialogueSpeaker.AI_A,
        text="Erinnerung und Vergessen sind wie ein Archiv.",
        topic="Erinnerung",
        mood="melancholisch",
        intensity=0.6,
        tags=["memory", "erinnerung"],
        timestamp=1.0,
    )
    decision = engine.decide(event)
    assert decision.visual is not None
    assert decision.visual.clip_id == "memory_noise_03"
    assert decision.sound is not None
    assert decision.light is not None
    assert decision.reason
