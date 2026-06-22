import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.schemas.inszenierung import (
    AnalyseStreamRequest,
    BatchAnimalScenesRequest,
    CompositionPlan,
    CreateAnimalSceneRequest,
    CreateCorpusRequest,
    Gesamtkonzept,
    KompositionStreamRequest,
    PatchCorpusRequest,
    SceneCorpus,
)
from app.services.inszenierung_analyse_service import InszenierungAnalyseService
from app.services.inszenierung_komposition_service import InszenierungKompositionService
from app.services.inszenierung_store import get_inszenierung_store

router = APIRouter(prefix="/inszenierung", tags=["inszenierung"])
_store = get_inszenierung_store()
_analyse = InszenierungAnalyseService()
_komposition = InszenierungKompositionService()


@router.post("", response_model=SceneCorpus, status_code=status.HTTP_201_CREATED)
def create_corpus(payload: CreateCorpusRequest) -> SceneCorpus:
    return _store.create(payload.title)


@router.get("/{corpus_id}", response_model=SceneCorpus)
def get_corpus(corpus_id: str) -> SceneCorpus:
    return _store.get(corpus_id)


@router.patch("/{corpus_id}", response_model=SceneCorpus)
def patch_corpus(corpus_id: str, payload: PatchCorpusRequest) -> SceneCorpus:
    return _store.patch(corpus_id, payload)


@router.post("/{corpus_id}/scenes", response_model=SceneCorpus)
def add_scene(corpus_id: str, payload: CreateAnimalSceneRequest) -> SceneCorpus:
    return _store.add_scene(corpus_id, payload)


@router.post("/{corpus_id}/scenes/batch", response_model=SceneCorpus)
def add_scenes_batch(corpus_id: str, payload: BatchAnimalScenesRequest) -> SceneCorpus:
    return _store.add_scenes_batch(corpus_id, payload.scenes)


@router.delete("/{corpus_id}/scenes/{scene_id}", response_model=SceneCorpus)
def delete_scene(corpus_id: str, scene_id: str) -> SceneCorpus:
    return _store.delete_scene(corpus_id, scene_id)


def _analyse_payload(event) -> dict:
    data: dict = {"type": event.type}
    if event.speaker is not None:
        data["speaker"] = event.speaker
    if event.content is not None:
        data["content"] = event.content
    if event.gesamtkonzept is not None:
        data["gesamtkonzept"] = event.gesamtkonzept
    if event.detail is not None:
        data["detail"] = event.detail
    return data


async def _analyse_stream(corpus_id: str, payload: AnalyseStreamRequest) -> AsyncIterator[str]:
    corpus = _store.get(corpus_id)
    try:
        async for event in _analyse.run_stream(
            corpus,
            openai_model=payload.openai_model,
            anthropic_model=payload.anthropic_model,
        ):
            if event.type == "gesamtkonzept" and event.gesamtkonzept:
                concept = Gesamtkonzept.model_validate(event.gesamtkonzept)
                corpus = _store.set_gesamtkonzept(corpus_id, concept)
                yield f"data: {json.dumps({'type': 'corpus_updated', 'corpus': corpus.model_dump(mode='json')})}\n\n"
            yield f"data: {json.dumps(_analyse_payload(event))}\n\n"
        corpus = _store.get(corpus_id)
        yield f"data: {json.dumps({'type': 'corpus_updated', 'corpus': corpus.model_dump(mode='json')})}\n\n"
    except ValidationError as exc:
        yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"


@router.post("/{corpus_id}/analyse/stream")
async def stream_analyse(corpus_id: str, payload: AnalyseStreamRequest) -> StreamingResponse:
    return StreamingResponse(_analyse_stream(corpus_id, payload), media_type="text/event-stream")


def _komposition_payload(event) -> dict:
    data: dict = {"type": event.type}
    if event.moment is not None:
        data["moment"] = event.moment
    if event.moment_order is not None:
        data["moment_order"] = event.moment_order
    if event.composition is not None:
        data["composition"] = event.composition
    if event.detail is not None:
        data["detail"] = event.detail
    return data


async def _komposition_stream(corpus_id: str, payload: KompositionStreamRequest) -> AsyncIterator[str]:
    corpus = _store.get(corpus_id)
    try:
        async for event in _komposition.run_stream(
            corpus,
            openai_model=payload.openai_model,
            moment_count=payload.moment_count,
        ):
            if event.type == "composition_plan" and event.composition:
                plan = CompositionPlan.model_validate(event.composition)
                corpus = _store.set_composition(corpus_id, plan)
                yield f"data: {json.dumps({'type': 'corpus_updated', 'corpus': corpus.model_dump(mode='json')})}\n\n"
            yield f"data: {json.dumps(_komposition_payload(event))}\n\n"
        corpus = _store.get(corpus_id)
        yield f"data: {json.dumps({'type': 'corpus_updated', 'corpus': corpus.model_dump(mode='json')})}\n\n"
    except ValidationError as exc:
        yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"


@router.post("/{corpus_id}/komposition/stream")
async def stream_komposition(corpus_id: str, payload: KompositionStreamRequest) -> StreamingResponse:
    return StreamingResponse(_komposition_stream(corpus_id, payload), media_type="text/event-stream")
