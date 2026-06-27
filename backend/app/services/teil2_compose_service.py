"""Orchestrate deterministic Teil-2 composition from avatar CSV script."""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Literal

from app.schemas.inszenierung import AnarchyCurve, CompositionPlan, Gesamtkonzept, SceneCorpus
from app.services.inszenierung_store import get_inszenierung_store
from app.services.teil2_beat_dramaturgy import build_dramaturgy_for_beat
from app.services.teil2_script_service import (
    SCRIPT_SCENE_ID,
    build_timeline_from_csv,
    load_canonical_script_text,
)

EventType = Literal["thinking", "moment", "composition_plan", "error", "done"]


@dataclass
class ComposeScriptEvent:
    type: EventType
    moment: dict | None = None
    moment_order: int | None = None
    composition: dict | None = None
    detail: str | None = None


def enrich_plan_with_dramaturgy(
    plan: CompositionPlan,
    *,
    corpus: SceneCorpus,
) -> CompositionPlan:
    concept = corpus.gesamtkonzept
    for moment in plan.moments:
        moment.dramaturgy = build_dramaturgy_for_beat(
            moment,
            title=corpus.title,
            gesamtkonzept=concept,
        )
    return plan


def compose_script_plan(corpus: SceneCorpus) -> CompositionPlan:
    curve = (
        corpus.gesamtkonzept.anarchy_curve
        if corpus.gesamtkonzept
        else AnarchyCurve()
    )
    script_text = corpus.script_text or load_canonical_script_text()
    plan = build_timeline_from_csv(anarchy_curve=curve, script_text=script_text)
    return enrich_plan_with_dramaturgy(plan, corpus=corpus)


async def compose_script_stream(corpus: SceneCorpus) -> AsyncIterator[ComposeScriptEvent]:
    try:
        yield ComposeScriptEvent(type="thinking")
        plan = compose_script_plan(corpus)
        for index, moment in enumerate(plan.moments):
            yield ComposeScriptEvent(
                type="moment",
                moment_order=index,
                moment=moment.model_dump(mode="json"),
            )
        yield ComposeScriptEvent(
            type="composition_plan",
            composition=plan.model_dump(mode="json"),
        )
        yield ComposeScriptEvent(type="done")
    except Exception as exc:
        yield ComposeScriptEvent(type="error", detail=str(exc))


def save_composed_plan(corpus_id: str, plan: CompositionPlan) -> SceneCorpus:
    store = get_inszenierung_store()
    return store.set_composition(corpus_id, plan)
