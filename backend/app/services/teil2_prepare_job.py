"""Background Teil-2 prepare jobs with corpus status updates."""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.director.cues.cue_models import PerformanceSpeaker
from app.services.inszenierung_store import get_inszenierung_store
from app.services.teil2_prepare_service import get_teil2_prepare_service

logger = logging.getLogger(__name__)

_active_tasks: dict[str, asyncio.Task[None]] = {}


class Teil2PrepareJobService:
    def __init__(self) -> None:
        self._store = get_inszenierung_store()
        self._prepare = get_teil2_prepare_service()

    def is_running(self, corpus_id: str) -> bool:
        """Only a live asyncio task counts — stale disk status must not block forever."""
        task = _active_tasks.get(corpus_id)
        return task is not None and not task.done()

    def start(
        self,
        corpus_id: str,
        *,
        openai_model: str = "gpt-4o-mini",
        performance_speaker: PerformanceSpeaker = "narrator",
    ) -> None:
        if self.is_running(corpus_id):
            raise ValueError("Vorbereiten läuft bereits")

        corpus = self._store.get(corpus_id)
        if not (corpus.script_text or "").strip():
            raise ValueError("Kein Aufführungstext — zuerst Text hochladen")

        # Clear zombie "preparing" left behind after reload / hung LLM calls.
        if corpus.status == "preparing":
            logger.warning(
                "Clearing stale prepare status for %s (phase=%s)",
                corpus_id,
                corpus.prepare_phase,
            )

        self._store.set_preparing(corpus_id, phase="analyse")
        task = asyncio.create_task(
            self._run(corpus_id, openai_model=openai_model, performance_speaker=performance_speaker)
        )
        _active_tasks[corpus_id] = task

        def _cleanup(done: asyncio.Task[None]) -> None:
            _active_tasks.pop(corpus_id, None)
            if done.cancelled():
                return
            exc = done.exception()
            if exc is not None:
                logger.exception("Teil-2 prepare failed for %s", corpus_id, exc_info=exc)

        task.add_done_callback(_cleanup)

    async def _run(
        self,
        corpus_id: str,
        *,
        openai_model: str,
        performance_speaker: PerformanceSpeaker,
    ) -> None:
        try:
            corpus = self._store.get(corpus_id)
            last_phase: str | None = None

            async def on_phase(phase: str) -> None:
                nonlocal last_phase
                if phase == last_phase:
                    return
                last_phase = phase
                self._store.set_prepare_phase(corpus_id, phase)

            model = openai_model or settings.teil2_prepare_model
            gesamtkonzept, plan = await self._prepare.prepare(
                corpus,
                openai_model=model,
                performance_speaker=performance_speaker,
                on_phase=on_phase,
            )
            self._store.set_teil2_plan(corpus_id, plan, gesamtkonzept=gesamtkonzept)
        except Exception as exc:
            self._store.set_prepare_error(corpus_id, str(exc))
            raise


_job_service: Teil2PrepareJobService | None = None


def get_teil2_prepare_job_service() -> Teil2PrepareJobService:
    global _job_service
    if _job_service is None:
        _job_service = Teil2PrepareJobService()
    return _job_service
