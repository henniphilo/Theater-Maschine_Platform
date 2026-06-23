from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

from app.director.media.database import MediaDatabase
from app.director.outputs.osc_commands import build_osc_commands
from app.schemas.script import PatchScriptBeatRequest, PatchScriptRequest, ProductionScript, ScriptBeat
from app.services.baerenklau_beat import find_baerenklau_beats, resolve_part1_beats


class ScriptStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.media_db = MediaDatabase(data_dir)
        base = self.media_db.data_dir / "productions"
        base.mkdir(parents=True, exist_ok=True)
        self.base_dir = base

    def _path(self, script_id: str) -> Path:
        safe = script_id.replace("/", "").replace("..", "")
        return self.base_dir / f"{safe}.json"

    def save(self, script: ProductionScript) -> ProductionScript:
        script = self._recompute_status(script)
        self._path(script.id).write_text(
            script.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return script

    def get(self, script_id: str) -> ProductionScript:
        path = self._path(script_id)
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
        return ProductionScript.model_validate_json(path.read_text(encoding="utf-8"))

    def create(self, title: str, source_text: str, beats: list[ScriptBeat]) -> ProductionScript:
        script = ProductionScript(
            id=str(uuid4()),
            title=title.strip() or "Stück",
            source_text=source_text.strip(),
            beats=beats,
            status="draft",
        )
        return self.save(script)

    def patch_script(self, script_id: str, payload: PatchScriptRequest) -> ProductionScript:
        script = self.get(script_id)
        if payload.performance_part is not None:
            script.performance_part = payload.performance_part
        if payload.teil2_corpus_id is not None:
            script.teil2_corpus_id = payload.teil2_corpus_id or None
        return self.save(script)

    def patch_beat(
        self,
        script_id: str,
        beat_id: str,
        payload: PatchScriptBeatRequest,
    ) -> ProductionScript:
        script = self.get(script_id)
        beat = next((b for b in script.beats if b.id == beat_id), None)
        if beat is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beat not found")

        if payload.speaker is not None:
            beat.speaker = payload.speaker
        if payload.dramaturgy is not None:
            beat.dramaturgy = payload.dramaturgy
            beat.planned_commands = build_osc_commands(payload.dramaturgy, dry_run=True)

        return self.save(script)

    def update_beat(self, script_id: str, beat: ScriptBeat) -> ProductionScript:
        script = self.get(script_id)
        for index, existing in enumerate(script.beats):
            if existing.id == beat.id:
                script.beats[index] = beat
                break
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beat not found")
        return self.save(script)

    @staticmethod
    def _recompute_status(script: ProductionScript) -> ProductionScript:
        if not script.beats:
            script.status = "draft"
            return script
        baerenklau = find_baerenklau_beats(script.beats)
        required = resolve_part1_beats(script.beats)
        all_have_dramaturgy = all(b.dramaturgy is not None for b in required)
        any_have_dramaturgy = any(b.dramaturgy is not None for b in required)
        if all_have_dramaturgy and (script.part1_selection is not None or not baerenklau):
            script.status = "ready"
        elif any_have_dramaturgy:
            script.status = "review"
        else:
            script.status = "draft"
        return script


_store: ScriptStore | None = None


def get_script_store() -> ScriptStore:
    global _store
    if _store is None:
        _store = ScriptStore()
    return _store
