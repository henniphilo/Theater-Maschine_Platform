"""Roundtrip tests for Teil-2 .tmteil2.zip export/import."""

import json
import zipfile
from io import BytesIO

import pytest
from fastapi import HTTPException

from app.schemas.inszenierung import AnarchyCurve, CompositionMoment, CompositionPlan, Gesamtkonzept, SceneCorpus
from app.services.inszenierung_bundle_service import InszenierungBundleService
from app.services.teil2_script_service import SCRIPT_SOURCE, load_canonical_script_text


class _MemoryStore:
    def __init__(self) -> None:
        self._items: dict[str, SceneCorpus] = {}

    def get(self, corpus_id: str) -> SceneCorpus:
        if corpus_id not in self._items:
            raise HTTPException(status_code=404, detail="not found")
        return self._items[corpus_id]

    def save(self, corpus: SceneCorpus) -> SceneCorpus:
        self._items[corpus.id] = corpus
        return corpus


def _sample_corpus() -> SceneCorpus:
    return SceneCorpus(
        id="export-me",
        title="Teil 2 Test",
        script_source=SCRIPT_SOURCE,
        script_text=load_canonical_script_text()[:500],
        gesamtkonzept=Gesamtkonzept(
            thesis="Test",
            anarchy_curve=AnarchyCurve(start=0.2, end=0.9),
        ),
        composition=CompositionPlan(
            moments=[
                CompositionMoment(
                    id="m1",
                    order=0,
                    scene_id="s1",
                    text_excerpt="Hallo",
                    speech_mode="avatar_video",
                    anarchy_level=0.3,
                )
            ]
        ),
    )


class _FakeUpload:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self) -> bytes:
        return self._data


@pytest.mark.anyio
async def test_export_import_roundtrip() -> None:
    store = _MemoryStore()
    corpus = _sample_corpus()
    store.save(corpus)
    service = InszenierungBundleService(store=store)  # type: ignore[arg-type]

    payload, filename = service.export_zip(corpus.id)
    assert filename.endswith(".tmteil2.zip")

    with zipfile.ZipFile(BytesIO(payload)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        exported = json.loads(archive.read("corpus.json"))
    assert manifest["format"] == "theatermaschine.teil2"
    assert exported["id"] == corpus.id
    assert len(exported["composition"]["moments"]) == 1

    imported = await service.import_zip(_FakeUpload(payload))
    assert imported.id != corpus.id
    assert imported.title == corpus.title
    assert len(imported.composition.moments) == 1
    saved = store.get(imported.id)
    assert saved.composition.moments[0].text_excerpt == "Hallo"


def test_export_requires_timeline() -> None:
    store = _MemoryStore()
    corpus = SceneCorpus(id="empty", title="Ohne Plan")
    store.save(corpus)
    service = InszenierungBundleService(store=store)  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as exc:
        service.export_zip(corpus.id)
    assert exc.value.status_code == 400
