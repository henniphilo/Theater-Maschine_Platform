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
# Begleitvideo: Pixera-Cues ohne volle Beamer-Anlage bzw. nicht spielbar.
_EXCLUDED_ATMOSPHERE_PIXERA = frozenset({"Random", "Avatar2"})
_EXCLUDED_ATMOSPHERE_CLIP_IDS = frozenset({"random", "avatar2"})


def _is_excluded_atmosphere(pixera_name: str | None = None, clip_id: str | None = None) -> bool:
    if pixera_name and pixera_name.strip() in _EXCLUDED_ATMOSPHERE_PIXERA:
        return True
    if clip_id and clip_id.strip().lower() in _EXCLUDED_ATMOSPHERE_CLIP_IDS:
        return True
    return False


def _required_projector_ids(catalog: VideoCueCatalog) -> set[str]:
    required = {projector.id for projector in catalog.projectors}
    return required or {"rz21", "adam", "eva", "led"}


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
    all_ids = {clip.id for clip in base.clips if not _is_excluded_atmosphere(clip_id=clip.id)}
    if not paths:
        if scope == "part1":
            avatar_ids = {clip.id for clip in base.clips if clip.pixera_name in _AVATAR_PIXERA_NAMES}
            return all_ids - avatar_ids
        return all_ids

    name_to_id = _name_to_id_map(base.clips)
    clip_ids: set[str] = set()
    for _prefix, pixera_name in _parse_osc_pairs(paths):
        if _is_excluded_atmosphere(pixera_name=pixera_name):
            continue
        clip_id = _clip_id_for_pixera_name(pixera_name, name_to_id)
        if clip_id and not _is_excluded_atmosphere(clip_id=clip_id):
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
    from app.services.extra_media_overrides import merge_video_catalog

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

    scoped = base.model_copy(update={"clips": clips})
    return merge_video_catalog(scoped)


def osc_availability_by_clip(scope: VideoScope = "part2") -> dict[str, set[str]]:
    """clip_id → output_ids with Pixera cues in scope."""
    from app.services.extra_media_overrides import merge_osc_availability

    catalog = _load_base_catalog()
    paths = _osc_paths_for_scope(scope)
    if not paths:
        availability = {clip.id: {p.id for p in catalog.projectors} for clip in catalog.clips}
    else:
        prefix_to_id = {p.pixera_prefix: p.id for p in catalog.projectors}
        prefix_to_id["KI_KI_RZ21"] = "rz21"
        name_to_id = _name_to_id_map(catalog.clips)

        availability = {}
        for prefix, pixera_name in _parse_osc_pairs(paths):
            if _is_excluded_atmosphere(pixera_name=pixera_name):
                continue
            output_id = prefix_to_id.get(prefix)
            clip_id = _clip_id_for_pixera_name(pixera_name, name_to_id)
            if not output_id or not clip_id or _is_excluded_atmosphere(clip_id=clip_id):
                continue
            availability.setdefault(clip_id, set()).add(output_id)
    merged = merge_osc_availability(availability, catalog)
    return {
        clip_id: outputs
        for clip_id, outputs in merged.items()
        if not _is_excluded_atmosphere(clip_id=clip_id)
    }


def clip_ids_on_all_projectors(scope: VideoScope = "part1") -> set[str]:
    """Clips that have Pixera cues on every configured beamer."""
    catalog = _load_base_catalog()
    required = _required_projector_ids(catalog)
    availability = osc_availability_by_clip(scope)
    return {
        clip_id
        for clip_id, outputs in availability.items()
        if required <= outputs and not _is_excluded_atmosphere(clip_id=clip_id)
    }


def atmosphere_clip_ids(*, avatar_clip_ids: set[str] | None = None) -> set[str]:
    """Begleitvideo pool: Ohne-Avatare OSC, only clips laid out on all beamers."""
    excluded = set(avatar_clip_ids or ()) | _EXCLUDED_ATMOSPHERE_CLIP_IDS
    return {clip_id for clip_id in clip_ids_on_all_projectors("part1") if clip_id not in excluded}


def usable_dramaturgy_video_ids(scope: VideoScope = "part2") -> set[str]:
    """LLM/rules may only pick avatars or atmosphere clips present on all beamers."""
    from app.services.extra_media_overrides import is_dramaturgy_active

    catalog = build_video_catalog(scope)
    atmosphere_ok = clip_ids_on_all_projectors("part1")
    avatar_ids = _avatar_clip_ids() if scope == "part2" else set()
    usable: set[str] = set()
    for clip in catalog.clips:
        if not is_dramaturgy_active("video", clip.id):
            continue
        if clip.id in avatar_ids or clip.id in atmosphere_ok:
            usable.add(clip.id)
    return usable
