"""Teil-2 composition — deterministic script timeline from avatar CSV."""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Literal

from app.schemas.inszenierung import CompositionPlan, SceneCorpus
from app.services.inszenierung_validation import validate_composition
from app.services.teil2_compose_service import ComposeScriptEvent, compose_script_plan

EventType = Literal["thinking", "moment", "composition_plan", "error", "done"]


@dataclass
class KompositionEvent:
    type: EventType
    moment: dict | None = None
    moment_order: int | None = None
    composition: dict | None = None
    detail: str | None = None


class InszenierungKompositionService:
    async def run_stream(
        self,
        corpus: SceneCorpus,
        *,
        openai_model: str = "gpt-4o",
        moment_count: int = 12,
    ) -> AsyncIterator[KompositionEvent]:
        del openai_model, moment_count
        if not corpus.script_text and not corpus.scenes:
            yield KompositionEvent(type="error", detail="Kein Skripttext im Korpus")
            return

        try:
            yield KompositionEvent(type="thinking")
            plan = compose_script_plan(corpus)
            validate_composition(plan, corpus)
            for index, moment in enumerate(plan.moments):
                yield KompositionEvent(
                    type="moment",
                    moment_order=index,
                    moment=moment.model_dump(mode="json"),
                )
            yield KompositionEvent(
                type="composition_plan",
                composition=plan.model_dump(mode="json"),
            )
            yield KompositionEvent(type="done")
        except Exception as exc:
            yield KompositionEvent(type="error", detail=str(exc))

    def compose_plan(self, corpus: SceneCorpus) -> CompositionPlan:
        plan = compose_script_plan(corpus)
        validate_composition(plan, corpus)
        return plan
