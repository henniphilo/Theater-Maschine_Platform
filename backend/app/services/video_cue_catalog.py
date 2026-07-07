import json
from pathlib import Path

from app.core.config import settings
from app.director.media.database import VideoAsset
from app.director.media.video_inventory import load_video_cues_from_csv, resolve_video_overview_paths
from app.schemas.video_cues import VideoCueCatalog
from app.services.video_pixera_aliases import catalog_pixera_to_osc_name
from app.services.video_scope import VideoScope, build_video_catalog, osc_availability_by_clip


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
    configured = Path(settings.video_cues_path)
    if configured.is_file():
        return configured
    for root in _repo_roots():
        candidate = root / settings.video_cues_path
        if candidate.is_file():
            return candidate
    return _data_dir() / "video_cues.json"


class VideoCueCatalogService:
    def __init__(self) -> None:
        self._cache: dict[VideoScope, VideoCueCatalog] = {}

    def load(self, scope: VideoScope = "part2") -> VideoCueCatalog:
        if scope in self._cache:
            return self._cache[scope]

        clips_path, projectors_path = resolve_video_overview_paths(_data_dir())
        if clips_path is not None:
            base = load_video_cues_from_csv(clips_path, projectors_path)
            self._write_json_cache(base, source=str(clips_path))

        catalog = build_video_catalog(scope)
        self._cache[scope] = catalog
        return catalog

    def clear_cache(self) -> None:
        self._cache.clear()

    @staticmethod
    def _write_json_cache(catalog: VideoCueCatalog, *, source: str) -> None:
        path = catalog_json_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": catalog.version,
            "osc_address": catalog.osc_address,
            "_source": source,
            "_note": "Abgeleitet aus Video Übersicht.csv — bitte CSV bearbeiten, nicht diese Datei.",
            "projectors": [p.model_dump() for p in catalog.projectors],
            "clips": [c.model_dump() for c in catalog.clips],
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def projector_by_id(
        self,
        output_id: str,
        catalog: VideoCueCatalog | None = None,
        *,
        scope: VideoScope = "part2",
    ) -> str | None:
        catalog = catalog or self.load(scope)
        normalized = output_id.strip().lower()
        for projector in catalog.projectors:
            if projector.id == normalized:
                return projector.pixera_prefix
        return None

    def clip_by_id(self, clip_id: str, catalog: VideoCueCatalog | None = None, *, scope: VideoScope = "part2"):
        catalog = catalog or self.load(scope)
        normalized = clip_id.strip().lower()
        return next((clip for clip in catalog.clips if clip.id == normalized), None)

    def projectors_for_clip(
        self,
        clip_id: str,
        catalog: VideoCueCatalog | None = None,
        *,
        scope: VideoScope = "part2",
    ) -> list[str]:
        catalog = catalog or self.load(scope)
        normalized = clip_id.strip().lower()
        available = osc_availability_by_clip(scope).get(normalized)
        if available:
            order = [p.id for p in catalog.projectors]
            return [output_id for output_id in order if output_id in available]
        return [p.id for p in catalog.projectors]

    def pixera_cue_name(
        self,
        output_id: str,
        clip_id: str,
        catalog: VideoCueCatalog | None = None,
        *,
        scope: VideoScope = "part2",
    ) -> str:
        catalog = catalog or self.load(scope)
        prefix = self.projector_by_id(output_id, catalog, scope=scope)
        clip = self.clip_by_id(clip_id, catalog, scope=scope)
        if not prefix or not clip:
            raise KeyError(f"Unknown projector {output_id!r} or clip {clip_id!r}")
        return f"{prefix}.{catalog_pixera_to_osc_name(clip.pixera_name)}"

    def to_video_assets(self, catalog: VideoCueCatalog | None = None, *, scope: VideoScope = "part2") -> list[VideoAsset]:
        catalog = catalog or self.load(scope)
        assets: list[VideoAsset] = []
        for clip in catalog.clips:
            assets.append(
                VideoAsset(
                    id=clip.id,
                    type="video",
                    path=f"pixera:{clip.pixera_name}",
                    tags=clip.tags,
                    moods=clip.moods,
                    intensity_min=clip.intensity_min,
                    intensity_max=clip.intensity_max,
                    loopable=True,
                    preferred_blend="slow_fade",
                )
            )
        return assets


_catalog: VideoCueCatalogService | None = None


def get_video_cue_catalog_service() -> VideoCueCatalogService:
    global _catalog
    if _catalog is None:
        _catalog = VideoCueCatalogService()
    return _catalog
