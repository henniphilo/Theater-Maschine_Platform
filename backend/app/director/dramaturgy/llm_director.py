"""Phase 5 stub: LLM-based dramaturgy director (not implemented yet)."""

from app.director.cues.cue_models import DramaturgyDecision
from app.director.dialogue.models import DialogueEvent


class LLMDirector:
    """Future: structured JSON dramaturgy via LLM with allowlisted actions only."""

    def decide(self, event: DialogueEvent, history: list[DialogueEvent]) -> DramaturgyDecision:
        raise NotImplementedError(
            "LLM dramaturgy is planned for Phase 5. Use DramaturgyEngine for rule-based mode."
        )
