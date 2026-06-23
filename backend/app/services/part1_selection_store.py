import json
from pathlib import Path


from app.schemas.part1_selection import Part1BaerenklauSelection
from app.schemas.script import ProductionScript
from app.services.script_store import ScriptStore, get_script_store


class Part1SelectionStore:
    def __init__(self, script_store: ScriptStore | None = None) -> None:
        self.script_store = script_store or get_script_store()

    def _selection_path(self, script_id: str) -> Path:
        safe = script_id.replace("/", "").replace("..", "")
        folder = self.script_store.base_dir / safe
        folder.mkdir(parents=True, exist_ok=True)
        return folder / "baerenklau_selection.json"

    def save(self, selection: Part1BaerenklauSelection) -> Part1BaerenklauSelection:
        path = self._selection_path(selection.script_id)
        path.write_text(
            json.dumps(selection.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        script = self.script_store.get(selection.script_id)
        script.part1_selection = selection
        self.script_store.save(script)
        return selection

    def load(self, script_id: str) -> Part1BaerenklauSelection | None:
        script = self.script_store.get(script_id)
        if script.part1_selection is not None:
            return script.part1_selection
        path = self._selection_path(script_id)
        if not path.is_file():
            return None
        return Part1BaerenklauSelection.model_validate_json(path.read_text(encoding="utf-8"))

    def attach_to_script(self, script: ProductionScript) -> ProductionScript:
        selection = self.load(script.id)
        if selection is not None:
            script.part1_selection = selection
        return script


_store: Part1SelectionStore | None = None


def get_part1_selection_store() -> Part1SelectionStore:
    global _store
    if _store is None:
        _store = Part1SelectionStore()
    return _store
