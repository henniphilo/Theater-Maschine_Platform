import json
from pathlib import Path

from app.core.config import settings
from app.director.media.database import SoundAsset
from app.director.media.sound_inventory import load_sound_cues_from_csv, resolve_sound_overview_path
from app.director.outputs.sound_midi import MidiCueMapping
from app.schemas.sound_cues import SoundCueCatalog


def _repo_roots() -> list[Path]:
    module_root = Path(__file__).resolve()
    data_dir = Path(settings.director_data_dir)
    if not data_dir.is_absolute():
        data_dir = module_root.parents[1] / data_dir
    return [data_dir.parent, data_dir, module_root.parents[2], module_root.parents[3], Path.cwd()]


def _data_dir() -> Path:
    configured = Path(settings.director_data_dir)
    if configured.is_absolute():
        return configured
    for root in _repo_roots():
        candidate = root / configured
        if candidate.is_dir():
            return candidate
    return Path.cwd() / configured


def catalog_json_path() -> Path:
    configured = Path(settings.sound_cues_path)
    if configured.is_file():
        return configured
    for root in _repo_roots():
        candidate = root / settings.sound_cues_path
        if candidate.is_file():
            return candidate
    return _data_dir() / "sound_cues.json"


class SoundCueCatalogService:
    def load_raw(self) -> SoundCueCatalog:
        """Catalog from CSV/JSON without operator overlays."""
        overview = resolve_sound_overview_path(_data_dir())
        if overview is not None:
            catalog = load_sound_cues_from_csv(overview)
            self._write_json_cache(catalog, source=str(overview))
            return catalog

        path = catalog_json_path()
        if path.is_file():
            return SoundCueCatalog.model_validate_json(path.read_text(encoding="utf-8"))
        return SoundCueCatalog()

    def load(self) -> SoundCueCatalog:
        from app.services.extra_media_overrides import merge_sound_catalog

        return merge_sound_catalog(self.load_raw())

    @staticmethod
    def _write_json_cache(catalog: SoundCueCatalog, *, source: str) -> None:
        path = catalog_json_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": catalog.version,
            "_source": source,
            "_note": "Abgeleitet aus Sound Übersicht.csv — bitte CSV bearbeiten, nicht diese Datei.",
            "defaults": catalog.defaults.model_dump(),
            "cues": [c.model_dump() for c in catalog.cues],
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def to_sound_assets(self, catalog: SoundCueCatalog | None = None) -> list[SoundAsset]:
        catalog = catalog or self.load()
        assets: list[SoundAsset] = []
        default_channel = catalog.defaults.channel
        for cue in catalog.cues:
            channel = cue.channel if cue.channel is not None else default_channel
            assets.append(
                SoundAsset(
                    id=cue.id,
                    type="midi_cue",
                    label=cue.soundname or cue.label or cue.id,
                    description=cue.description,
                    path="",
                    midi_note=cue.midi_note,
                    channel=channel,
                    ableton_hint=cue.ableton_hint,
                    tags=cue.tags or [cue.id],
                    moods=cue.moods or ["neutral"],
                    action=cue.action,
                    soundname=cue.soundname or cue.label,
                    dramaturgy_active=cue.dramaturgy_active,
                )
            )
        return assets

    def to_midi_map(self, catalog: SoundCueCatalog | None = None) -> dict[str, MidiCueMapping]:
        catalog = catalog or self.load()
        default_channel = catalog.defaults.channel
        default_velocity = catalog.defaults.velocity
        mapping: dict[str, MidiCueMapping] = {}
        for cue in catalog.cues:
            mapping[cue.id] = MidiCueMapping(
                note=cue.midi_note,
                channel=cue.channel if cue.channel is not None else default_channel,
                velocity=cue.velocity if cue.velocity is not None else default_velocity,
            )
        return mapping


_catalog: SoundCueCatalogService | None = None


def get_sound_cue_catalog_service() -> SoundCueCatalogService:
    global _catalog
    if _catalog is None:
        _catalog = SoundCueCatalogService()
    return _catalog
