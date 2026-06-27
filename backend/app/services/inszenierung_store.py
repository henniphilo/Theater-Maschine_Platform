from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

from app.director.media.database import MediaDatabase
from app.schemas.inszenierung import (
    AnimalScene,
    CompositionPlan,
    CreateAnimalSceneRequest,
    Gesamtkonzept,
    PatchCorpusRequest,
    SceneCorpus,
)
from app.services.teil2_script_service import (
    SCRIPT_SOURCE,
    load_canonical_script_text,
)


class InszenierungStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.media_db = MediaDatabase(data_dir)
        base = self.media_db.data_dir / "inszenierungen"
        base.mkdir(parents=True, exist_ok=True)
        self.base_dir = base

    def _path(self, corpus_id: str) -> Path:
        safe = corpus_id.replace("/", "").replace("..", "")
        return self.base_dir / f"{safe}.json"

    def save(self, corpus: SceneCorpus) -> SceneCorpus:
        corpus = self._recompute_status(corpus)
        self._path(corpus.id).write_text(
            corpus.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return corpus

    def get(self, corpus_id: str) -> SceneCorpus:
        path = self._path(corpus_id)
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inszenierung not found")
        return SceneCorpus.model_validate_json(path.read_text(encoding="utf-8"))

    def create(self, title: str) -> SceneCorpus:
        try:
            script_text = load_canonical_script_text()
        except FileNotFoundError:
            script_text = None
        corpus = SceneCorpus(
            id=str(uuid4()),
            title=title.strip() or "Unter Tieren — Geld",
            status="draft",
            script_source=SCRIPT_SOURCE if script_text else None,
            script_text=script_text,
        )
        return self.save(corpus)

    def patch(self, corpus_id: str, payload: PatchCorpusRequest) -> SceneCorpus:
        corpus = self.get(corpus_id)
        if payload.title is not None:
            corpus.title = payload.title.strip() or corpus.title
        return self.save(corpus)

    def add_scene(self, corpus_id: str, payload: CreateAnimalSceneRequest) -> SceneCorpus:
        corpus = self.get(corpus_id)
        corpus.scenes.append(
            AnimalScene(
                id=str(uuid4()),
                animal=payload.animal.strip(),
                title=payload.title.strip(),
                source_text=payload.source_text.strip(),
                play_reference=payload.play_reference,
            )
        )
        return self.save(corpus)

    def add_scenes_batch(
        self,
        corpus_id: str,
        scenes: list[CreateAnimalSceneRequest],
    ) -> SceneCorpus:
        corpus = self.get(corpus_id)
        for item in scenes:
            corpus.scenes.append(
                AnimalScene(
                    id=str(uuid4()),
                    animal=item.animal.strip(),
                    title=item.title.strip(),
                    source_text=item.source_text.strip(),
                    play_reference=item.play_reference,
                )
            )
        return self.save(corpus)

    def delete_scene(self, corpus_id: str, scene_id: str) -> SceneCorpus:
        corpus = self.get(corpus_id)
        before = len(corpus.scenes)
        corpus.scenes = [s for s in corpus.scenes if s.id != scene_id]
        if len(corpus.scenes) == before:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")
        return self.save(corpus)

    def set_gesamtkonzept(self, corpus_id: str, concept: Gesamtkonzept) -> SceneCorpus:
        corpus = self.get(corpus_id)
        corpus.gesamtkonzept = concept
        return self.save(corpus)

    def set_composition(self, corpus_id: str, plan: CompositionPlan) -> SceneCorpus:
        corpus = self.get(corpus_id)
        corpus.composition = plan
        return self.save(corpus)

    @staticmethod
    def _recompute_status(corpus: SceneCorpus) -> SceneCorpus:
        has_script = bool(corpus.script_source and corpus.script_text)
        has_scenes = bool(corpus.scenes)
        if not has_script and not has_scenes:
            corpus.status = "draft"
        elif corpus.composition and corpus.composition.moments and corpus.gesamtkonzept:
            corpus.status = "ready"
        elif corpus.composition and corpus.composition.moments:
            corpus.status = "composed"
        elif corpus.gesamtkonzept and corpus.gesamtkonzept.thesis:
            corpus.status = "analyzed"
        elif has_script:
            corpus.status = "draft"
        else:
            corpus.status = "draft"
        return corpus


_store: InszenierungStore | None = None


def get_inszenierung_store() -> InszenierungStore:
    global _store
    if _store is None:
        _store = InszenierungStore()
    return _store
