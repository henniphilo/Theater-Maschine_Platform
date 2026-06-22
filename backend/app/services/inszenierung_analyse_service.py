import json
import re
from dataclasses import dataclass
from typing import AsyncIterator, Literal

from app.core.config import settings
from app.director.dramaturgy.llm_director import LLMDirector
from app.director.dramaturgy.rules_text import dramaturgy_rules_excerpt
from app.schemas.inszenierung import (
    AnimalPosition,
    AnarchyCurve,
    CrossSceneLink,
    Gesamtkonzept,
    SceneCorpus,
)
from app.services.ai_service import AIService

EventType = Literal["thinking", "discussion_turn", "gesamtkonzept", "error", "done"]


@dataclass
class AnalyseEvent:
    type: EventType
    speaker: str | None = None
    content: str | None = None
    gesamtkonzept: dict | None = None
    detail: str | None = None


def _scene_digest(corpus: SceneCorpus, max_chars: int = 12000) -> str:
    parts: list[str] = []
    for scene in corpus.scenes:
        text = scene.source_text.strip()
        if len(text) > 900:
            text = text[:900] + "…"
        parts.append(
            f"[{scene.id}] Tier: {scene.animal} | Titel: {scene.title or '—'}\n{text}"
        )
    joined = "\n\n---\n\n".join(parts)
    return joined[:max_chars]


class InszenierungAnalyseService:
    def __init__(
        self,
        ai_service: AIService | None = None,
        llm_director: LLMDirector | None = None,
    ) -> None:
        self.ai = ai_service or AIService()
        self.llm = llm_director or LLMDirector(ai_service=self.ai)

    def _validate_providers(self) -> None:
        if "openai" not in self.ai.providers:
            raise ValueError("OpenAI is not configured (set OPENAI_API_KEY)")
        if "anthropic" not in self.ai.providers:
            raise ValueError("Anthropic is not configured (set ANTHROPIC_API_KEY)")

    async def run_stream(
        self,
        corpus: SceneCorpus,
        *,
        openai_model: str,
        anthropic_model: str,
    ) -> AsyncIterator[AnalyseEvent]:
        if not corpus.scenes:
            yield AnalyseEvent(type="error", detail="Keine Szenen im Korpus")
            return
        self._validate_providers()

        rules = dramaturgy_rules_excerpt(max_chars=settings.dramaturgy_rules_excerpt_chars)
        digest = _scene_digest(corpus)
        discussion: list[str] = []

        for role, model, label in (
            ("openai", openai_model, "Dramaturg A (GPT)"),
            ("anthropic", anthropic_model, "Dramaturg B (Claude)"),
        ):
            yield AnalyseEvent(type="thinking", speaker=role)
            prompt = (
                f"Korpus: {corpus.title}\n"
                f"Szenen aus Elfriede Jelinek «Unter Tieren» — Tiere sprechen über Geld.\n\n"
                f"{digest}\n\n"
                f"Bisherige Diskussion:\n{chr(10).join(discussion) or '(keine)'}\n\n"
                f"Du bist {label}. Beziehe dich auf konkrete Textstellen und Tiere. "
                f"Keine Illustration — Entlarven, Überlagern, Widersprechen. "
                f"Maximal {settings.dramaturgy_statement_max_chars} Zeichen."
            )
            system = (
                "Ihr seid zwei Dramaturgen für eine KI-Inszenierung (Teil 2). "
                "Ziel: ein Gesamtkonzept über alle Szenen — Geld als Thema, Tier-Positionen, Querverbindungen.\n\n"
                f"=== REGELWERK ===\n{rules}"
            )
            raw = await self.ai.generate(
                role,
                model,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.dramaturgy_discussion_max_tokens,
            )
            content = raw.strip()[: settings.dramaturgy_statement_max_chars]
            discussion.append(f"{label}: {content}")
            yield AnalyseEvent(type="discussion_turn", speaker=role, content=content)

        yield AnalyseEvent(type="thinking", speaker="openai")
        concept_prompt = (
            f"Korpus: {corpus.title}\n\nSzenen:\n{digest}\n\n"
            f"Dramaturgie-Diskussion:\n{chr(10).join(discussion)}\n\n"
            "Erstelle das Gesamtkonzept als JSON:\n"
            '{"thesis":"...","money_themes":["..."],"animal_positions":[{"animal":"...","stance":"...","money_angle":"..."}],'
            '"cross_scene_links":[{"label":"...","scene_ids":["uuid"],"note":"..."}],'
            '"anarchy_curve":{"start":0.2,"end":0.95},"discussion_summary":"..."}'
        )
        raw_json = await self.ai.generate(
            "openai",
            openai_model,
            [
                {
                    "role": "system",
                    "content": "Antworte nur mit gültigem JSON für das Gesamtkonzept.",
                },
                {"role": "user", "content": concept_prompt},
            ],
            max_tokens=settings.dramaturgy_decision_max_tokens,
        )
        concept = self._parse_gesamtkonzept(raw_json, corpus, discussion)
        yield AnalyseEvent(
            type="gesamtkonzept",
            gesamtkonzept=concept.model_dump(mode="json"),
        )
        yield AnalyseEvent(type="done")

    def _parse_gesamtkonzept(
        self,
        raw: str,
        corpus: SceneCorpus,
        discussion: list[str],
    ) -> Gesamtkonzept:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
            return Gesamtkonzept.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            animals = [
                AnimalPosition(
                    animal=s.animal,
                    stance="im Korpus",
                    money_angle="Geld / Ökonomie",
                )
                for s in corpus.scenes
            ]
            return Gesamtkonzept(
                thesis="Geld erscheint bei den Tieren als Austauschlogik, Schuldzuweisung und Sprachmaske.",
                money_themes=["Austausch", "Schuld", "Wert", "Klassenkampf"],
                animal_positions=animals,
                cross_scene_links=[
                    CrossSceneLink(
                        label="Geld-Klammer",
                        scene_ids=[s.id for s in corpus.scenes[:3]],
                        note="Querverweis über alle Tier-Szenen",
                    )
                ],
                anarchy_curve=AnarchyCurve(start=0.2, end=0.95),
                discussion_summary="\n".join(discussion),
            )
