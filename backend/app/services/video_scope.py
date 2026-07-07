"""Video OSC scope: Teil 1 (ohne Erzähler-Avatare) vs Teil 2 (Vereinigung)."""

from __future__ import annotations

from typing import Literal

from app.schemas.video_cues import VideoClipEntry, VideoCueCatalog
from app.services.video_pixera_aliases import catalog_pixera_to_osc_name, osc_pixera_to_catalog_name

VideoScope = Literal["part1", "part2"]

_AVATAR_PIXERA_NAMES = frozenset(
    {
        "Inge",
        "Sebastian",
        "Thomas",
        "Nicolas",
        "Branko",
        "Thiemo",
        "Musiker",
    }
)


def _data_dir():
    from app.services.video_cue_catalog import _data_dir as catalog_data_dir

    return catalog_data_dir()


def _load_base_catalog() -> VideoCueCatalog:
    from app.director.media.video_inventory import load_video_cues_from_csv, resolve_video_overview_paths

    clips_path, projectors_path = resolve_video_overview_paths(_data_dir())
    if clips_path is not None:
        return load_video_cues_from_csv(clips_path, projectors_path)
    from app.services.video_cue_catalog import catalog_json_path

    path = catalog_json_path()
    if path.is_file():
        return VideoCueCatalog.model_validate_json(path.read_text(encoding="utf-8"))
    return VideoCueCatalog()


def _osc_paths_for_scope(scope: VideoScope) -> list:
    from app.director.media.video_inventory import resolve_osc_befehlliste_paths_for_scope

    return resolve_osc_befehlliste_paths_for_scope(_data_dir(), scope)


def _parse_osc_pairs(paths: list) -> list[tuple[str, str]]:
    from app.director.media.video_inventory import parse_osc_befehlliste_files

    return parse_osc_befehlliste_files(paths)


def _name_to_id_map(clips: list[VideoClipEntry]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for clip in clips:
        mapping[clip.pixera_name] = clip.id
        osc_name = catalog_pixera_to_osc_name(clip.pixera_name)
        if osc_name != clip.pixera_name:
            mapping[osc_name] = clip.id
    return mapping


def _clip_id_for_pixera_name(pixera_name: str, name_to_id: dict[str, str]) -> str | None:
    clip_id = name_to_id.get(pixera_name)
    if clip_id:
        return clip_id
    catalog_name = osc_pixera_to_catalog_name(pixera_name)
    if catalog_name != pixera_name:
        return name_to_id.get(catalog_name)
    return None


def _clip_ids_for_scope(scope: VideoScope) -> set[str]:
    paths = _osc_paths_for_scope(scope)
    base = _load_base_catalog()
    all_ids = {clip.id for clip in base.clips}
    if not paths:
        if scope == "part1":
            avatar_ids = {clip.id for clip in base.clips if clip.pixera_name in _AVATAR_PIXERA_NAMES}
            return all_ids - avatar_ids
        return all_ids

    name_to_id = _name_to_id_map(base.clips)
    clip_ids: set[str] = set()
    for _prefix, pixera_name in _parse_osc_pairs(paths):
        clip_id = _clip_id_for_pixera_name(pixera_name, name_to_id)
        if clip_id:
            clip_ids.add(clip_id)
    return clip_ids


def _avatar_clip_ids() -> set[str]:
    from app.director.media.video_inventory import OSC_PART2_AVATAR_FILENAME

    paths = _osc_paths_for_scope("part2")
    avatar_path = next((p for p in paths if p.name == OSC_PART2_AVATAR_FILENAME), None)
    if avatar_path is None:
        return {clip.id for clip in _load_base_catalog().clips if clip.pixera_name in _AVATAR_PIXERA_NAMES}

    base = _load_base_catalog()
    name_to_id = _name_to_id_map(base.clips)
    ids: set[str] = set()
    for _prefix, pixera_name in _parse_osc_pairs([avatar_path]):
        clip_id = _clip_id_for_pixera_name(pixera_name, name_to_id)
        if clip_id:
            ids.add(clip_id)
    return ids


def build_video_catalog(scope: VideoScope = "part2") -> VideoCueCatalog:
    base = _load_base_catalog()
    allowed = _clip_ids_for_scope(scope)
    avatar_ids = _avatar_clip_ids() if scope == "part2" else set()

    clips: list[VideoClipEntry] = []
    for clip in base.clips:
        if clip.id not in allowed:
            continue
        updated = clip
        if clip.id in avatar_ids:
            updated = clip.model_copy(update={"video_type": "avatar"})
        clips.append(updated)

    return base.model_copy(update={"clips": clips})


def osc_availability_by_clip(scope: VideoScope = "part2") -> dict[str, set[str]]:
    """clip_id → output_ids with Pixera cues in scope."""
    catalog = _load_base_catalog()
    paths = _osc_paths_for_scope(scope)
    if not paths:
        return {clip.id: {p.id for p in catalog.projectors} for clip in catalog.clips}

    prefix_to_id = {p.pixera_prefix: p.id for p in catalog.projectors}
    prefix_to_id["KI_KI_RZ21"] = "rz21"
    name_to_id = _name_to_id_map(catalog.clips)

    availability: dict[str, set[str]] = {}
    for prefix, pixera_name in _parse_osc_pairs(paths):
        output_id = prefix_to_id.get(prefix)
        clip_id = _clip_id_for_pixera_name(pixera_name, name_to_id)
        if not output_id or not clip_id:
            continue
        availability.setdefault(clip_id, set()).add(output_id)
    return availability
