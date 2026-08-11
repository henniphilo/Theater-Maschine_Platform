"""Persist and apply operator media cue overlays under data/extra_media_overrides.json."""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.schemas.extra_media import (
    CueAdminLightRow,
    CueAdminPatchRequest,
    CueAdminResponse,
    CueAdminSoundRow,
    CueAdminVideoRow,
    CueKind,
    CueOverrideFlags,
    ExtraLightCreateRequest,
    ExtraLightCue,
    ExtraMediaOverrides,
    ExtraSoundCreateRequest,
    ExtraSoundCue,
    ExtraVideoCreateRequest,
    ExtraVideoCue,
)
from app.schemas.sound_cues import SoundCueCatalog, SoundCueEntry
from app.schemas.video_cues import VideoClipEntry, VideoCueCatalog

logger = logging.getLogger(__name__)

_FILENAME = "extra_media_overrides.json"
_lock = threading.Lock()
_cache: ExtraMediaOverrides | None = None
_persist_path_override: Path | None = None


def _slug_id(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    slug = normalized.strip("_")
    if not slug:
        raise ValueError("id darf nicht leer sein")
    if not re.match(r"^[a-z][a-z0-9_]*$", slug):
        slug = f"c_{slug}" if slug[0].isdigit() else slug
    if not re.match(r"^[a-z][a-z0-9_]*$", slug):
        raise ValueError(f"Ungültige id: {value!r}")
    return slug


def _data_dir() -> Path:
    configured = Path(settings.director_data_dir)
    if configured.is_absolute():
        return configured
    module_root = Path(__file__).resolve()
    for root in (module_root.parents[2], module_root.parents[1], Path.cwd()):
        candidate = root / configured
        if candidate.is_dir():
            return candidate
    return Path.cwd() / configured


def persist_path() -> Path:
    if _persist_path_override is not None:
        return _persist_path_override
    return _data_dir() / _FILENAME


def reset_extra_media_for_tests(persist_path: Path | None = None) -> None:
    """Clear in-memory cache; optionally redirect persistence (tests)."""
    global _cache, _persist_path_override
    with _lock:
        _cache = None
        _persist_path_override = persist_path


def load_overrides(*, force: bool = False) -> ExtraMediaOverrides:
    global _cache
    with _lock:
        if _cache is not None and not force:
            return _cache
        path = persist_path()
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                _cache = ExtraMediaOverrides.model_validate(payload)
            except Exception as exc:
                logger.warning("extra_media_overrides unreadable (%s): %s", path, exc)
                _cache = ExtraMediaOverrides()
        else:
            _cache = ExtraMediaOverrides()
        return _cache


def save_overrides(data: ExtraMediaOverrides) -> ExtraMediaOverrides:
    global _cache
    path = persist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.model_dump(mode="json")
    with _lock:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _cache = data
    invalidate_media_caches()
    return data


def invalidate_media_caches() -> None:
    from app.services.video_cue_catalog import get_video_cue_catalog_service

    get_video_cue_catalog_service().clear_cache()


def _kind_overlay(data: ExtraMediaOverrides, kind: CueKind):
    if kind == "video":
        return data.videos
    if kind == "sound":
        return data.sounds
    return data.lights


def effective_flags(
    kind: CueKind,
    cue_id: str,
    *,
    default_active: bool = True,
    data: ExtraMediaOverrides | None = None,
) -> tuple[bool, bool]:
    """Return (dramaturgy_active, removed) for a cue id."""
    data = data or load_overrides()
    overlay = _kind_overlay(data, kind)
    cue_id = cue_id.strip().lower()
    for extra in overlay.extra:
        if extra.id == cue_id:
            flags = overlay.overrides.get(cue_id)
            active = extra.dramaturgy_active if flags is None or flags.dramaturgy_active is None else flags.dramaturgy_active
            removed = bool(flags.removed) if flags and flags.removed is not None else False
            return active, removed
    flags = overlay.overrides.get(cue_id)
    if flags is None:
        # Venue-specific default safety overrides.
        # Hallein: deaktiviert "blendung_magenta" (Ch. 1701) standardmäßig.
        # Operator Overrides (via extra_admin patch) must still win, therefore
        # this only applies when there is no override entry for this cue id.
        if kind == "light" and cue_id == "blendung_magenta":
            try:
                from app.services.venue_profiles import get_active_profile

                if get_active_profile().id == "hallein":
                    return False, False
            except Exception:
                # Fail open: if venue state cannot be read, use defaults.
                pass
        return default_active, False
    active = default_active if flags.dramaturgy_active is None else flags.dramaturgy_active
    removed = bool(flags.removed) if flags.removed is not None else False
    return active, removed


def is_removed(kind: CueKind, cue_id: str, *, data: ExtraMediaOverrides | None = None) -> bool:
    return effective_flags(kind, cue_id, data=data)[1]


def is_dramaturgy_active(
    kind: CueKind,
    cue_id: str,
    *,
    default_active: bool = True,
    data: ExtraMediaOverrides | None = None,
) -> bool:
    active, removed = effective_flags(kind, cue_id, default_active=default_active, data=data)
    return active and not removed


def extra_video_clips(data: ExtraMediaOverrides | None = None) -> list[VideoClipEntry]:
    data = data or load_overrides()
    clips: list[VideoClipEntry] = []
    for extra in data.videos.extra:
        _, removed = effective_flags("video", extra.id, default_active=extra.dramaturgy_active, data=data)
        if removed:
            continue
        clips.append(
            VideoClipEntry(
                id=extra.id,
                pixera_name=extra.pixera_name,
                label=extra.label or extra.pixera_name,
                description=extra.description,
                tags=extra.tags or [extra.id],
                moods=extra.moods or ["neutral"],
                video_type="atmosphere",
            )
        )
    return clips


def merge_video_catalog(catalog: VideoCueCatalog, *, data: ExtraMediaOverrides | None = None) -> VideoCueCatalog:
    data = data or load_overrides()
    existing_ids = {clip.id for clip in catalog.clips}
    merged: list[VideoClipEntry] = []
    for clip in catalog.clips:
        _, removed = effective_flags("video", clip.id, data=data)
        if removed:
            continue
        merged.append(clip)
    for clip in extra_video_clips(data):
        if clip.id in existing_ids:
            continue
        merged.append(clip)
        existing_ids.add(clip.id)
    return catalog.model_copy(update={"clips": merged})


def merge_osc_availability(
    availability: dict[str, set[str]],
    catalog: VideoCueCatalog,
    *,
    data: ExtraMediaOverrides | None = None,
) -> dict[str, set[str]]:
    data = data or load_overrides()
    all_projector_ids = {p.id for p in catalog.projectors}
    result: dict[str, set[str]] = {}
    for clip_id, outputs in availability.items():
        _, removed = effective_flags("video", clip_id, data=data)
        if removed:
            continue
        result[clip_id] = set(outputs)

    for extra in data.videos.extra:
        active, removed = effective_flags("video", extra.id, default_active=extra.dramaturgy_active, data=data)
        del active  # availability is independent of LLM lock
        if removed:
            continue
        if not extra.projectors or extra.projectors == ["*"]:
            result[extra.id] = set(all_projector_ids)
        else:
            result[extra.id] = {pid for pid in extra.projectors if pid in all_projector_ids} or set(all_projector_ids)
    return result


def merge_sound_catalog(catalog: SoundCueCatalog, *, data: ExtraMediaOverrides | None = None) -> SoundCueCatalog:
    data = data or load_overrides()
    existing = {cue.id for cue in catalog.cues}
    merged: list[SoundCueEntry] = []
    for cue in catalog.cues:
        active, removed = effective_flags("sound", cue.id, default_active=cue.dramaturgy_active, data=data)
        if removed:
            continue
        if active != cue.dramaturgy_active:
            merged.append(cue.model_copy(update={"dramaturgy_active": active}))
        else:
            merged.append(cue)
    for extra in data.sounds.extra:
        if extra.id in existing:
            continue
        active, removed = effective_flags("sound", extra.id, default_active=extra.dramaturgy_active, data=data)
        if removed:
            continue
        hint = f"{extra.soundname or extra.label or extra.id} — {extra.action} (Note {extra.midi_note})"
        merged.append(
            SoundCueEntry(
                id=extra.id,
                label=extra.label or extra.soundname or extra.id,
                soundname=extra.soundname or extra.label or extra.id,
                action=extra.action,
                description=extra.description,
                ableton_hint=hint,
                midi_note=extra.midi_note,
                channel=extra.channel,
                velocity=extra.velocity,
                tags=extra.tags or [extra.id],
                moods=extra.moods or ["neutral"],
                dramaturgy_active=active,
            )
        )
        existing.add(extra.id)
    return catalog.model_copy(update={"cues": merged})


def merge_light_scenes(scenes: list[Any], *, data: ExtraMediaOverrides | None = None) -> list[Any]:
    """Merge LightScene-compatible dicts/models; filter removed; append extras."""
    from app.director.media.database import LightScene

    data = data or load_overrides()
    existing = {getattr(s, "id", None) or s.get("id") for s in scenes}  # type: ignore[union-attr]
    merged: list[LightScene] = []
    for scene in scenes:
        model = scene if isinstance(scene, LightScene) else LightScene.model_validate(scene)
        _, removed = effective_flags("light", model.id, data=data)
        if removed:
            continue
        merged.append(model)
    for extra in data.lights.extra:
        if extra.id in existing:
            continue
        _, removed = effective_flags("light", extra.id, default_active=extra.dramaturgy_active, data=data)
        if removed:
            continue
        merged.append(
            LightScene(
                id=extra.id,
                description=extra.description or extra.id,
                location=extra.location,
                channels=extra.channels,
                groups=extra.groups,
                fixtures=extra.fixtures,
                moods=extra.moods or ["neutral"],
                intensity_min=extra.intensity_min,
                intensity_max=extra.intensity_max,
                fade_time=extra.fade_time,
            )
        )
        existing.add(extra.id)
    return merged


def build_cue_admin_response() -> CueAdminResponse:
    from app.services.sound_cue_catalog import get_sound_cue_catalog_service
    from app.director.media.database import MediaDatabase
    from app.services.video_scope import _avatar_clip_ids, _load_base_catalog, osc_availability_by_clip

    data = load_overrides()
    base_video = _load_base_catalog()
    avatar_ids = _avatar_clip_ids()
    availability = osc_availability_by_clip("part2")

    videos: list[CueAdminVideoRow] = []
    seen_video: set[str] = set()
    for clip in base_video.clips:
        if clip.id in avatar_ids or clip.video_type == "avatar":
            continue
        active, removed = effective_flags("video", clip.id, data=data)
        projectors = sorted(availability.get(clip.id, set()))
        videos.append(
            CueAdminVideoRow(
                id=clip.id,
                pixera_name=clip.pixera_name,
                label=clip.label or clip.pixera_name,
                source="catalog",
                dramaturgy_active=active,
                removed=removed,
                projectors=projectors,
                video_type=clip.video_type,
            )
        )
        seen_video.add(clip.id)

    for extra in data.videos.extra:
        if extra.id in seen_video:
            continue
        active, removed = effective_flags("video", extra.id, default_active=extra.dramaturgy_active, data=data)
        if not extra.projectors or extra.projectors == ["*"]:
            projectors = [p.id for p in base_video.projectors]
        else:
            projectors = list(extra.projectors)
        videos.append(
            CueAdminVideoRow(
                id=extra.id,
                pixera_name=extra.pixera_name,
                label=extra.label or extra.pixera_name,
                source="extra",
                dramaturgy_active=active,
                removed=removed,
                projectors=projectors,
                video_type="atmosphere",
            )
        )

    raw_sounds = get_sound_cue_catalog_service().load_raw()
    sounds: list[CueAdminSoundRow] = []
    seen_sound: set[str] = set()
    for cue in raw_sounds.cues:
        active, removed = effective_flags("sound", cue.id, default_active=cue.dramaturgy_active, data=data)
        sounds.append(
            CueAdminSoundRow(
                id=cue.id,
                label=cue.label,
                soundname=cue.soundname,
                action=cue.action,
                midi_note=cue.midi_note,
                ableton_hint=cue.ableton_hint,
                source="catalog",
                dramaturgy_active=active,
                removed=removed,
            )
        )
        seen_sound.add(cue.id)
    for extra in data.sounds.extra:
        if extra.id in seen_sound:
            continue
        active, removed = effective_flags("sound", extra.id, default_active=extra.dramaturgy_active, data=data)
        hint = f"{extra.soundname or extra.label or extra.id} — {extra.action} (Note {extra.midi_note})"
        sounds.append(
            CueAdminSoundRow(
                id=extra.id,
                label=extra.label or extra.soundname,
                soundname=extra.soundname,
                action=extra.action,
                midi_note=extra.midi_note,
                ableton_hint=hint,
                source="extra",
                dramaturgy_active=active,
                removed=removed,
            )
        )

    db = MediaDatabase()
    light_path = db.data_dir / "light_scenes.json"
    light_data = json.loads(light_path.read_text(encoding="utf-8")) if light_path.is_file() else {"scenes": []}
    lights: list[CueAdminLightRow] = []
    seen_light: set[str] = set()
    for scene in light_data.get("scenes", []):
        scene_id = scene["id"]
        active, removed = effective_flags("light", scene_id, data=data)
        lights.append(
            CueAdminLightRow(
                id=scene_id,
                description=scene.get("description", ""),
                channels=list(scene.get("channels") or []),
                groups=list(scene.get("groups") or []),
                source="catalog",
                dramaturgy_active=active,
                removed=removed,
            )
        )
        seen_light.add(scene_id)
    for extra in data.lights.extra:
        if extra.id in seen_light:
            continue
        active, removed = effective_flags("light", extra.id, default_active=extra.dramaturgy_active, data=data)
        lights.append(
            CueAdminLightRow(
                id=extra.id,
                description=extra.description,
                channels=list(extra.channels),
                groups=list(extra.groups),
                source="extra",
                dramaturgy_active=active,
                removed=removed,
            )
        )

    return CueAdminResponse(
        videos=videos,
        sounds=sounds,
        lights=lights,
        projectors=[p.model_dump() for p in base_video.projectors],
    )


def add_extra_video(body: ExtraVideoCreateRequest) -> ExtraVideoCue:
    data = load_overrides(force=True)
    pixera_name = body.pixera_name.strip()
    cue_id = _slug_id(body.id or pixera_name)
    if any(e.id == cue_id for e in data.videos.extra):
        raise ValueError(f"Video-Extra {cue_id!r} existiert bereits")
    # Also conflict with catalog id
    from app.services.video_scope import _load_base_catalog

    if any(c.id == cue_id for c in _load_base_catalog().clips):
        raise ValueError(f"Video-id {cue_id!r} ist bereits im Katalog")
    projectors = body.projectors
    cleaned = [p.strip().lower() for p in projectors if p.strip()]
    if cleaned and cleaned != ["*"] and not any(p in {"*", "all", "alle"} for p in cleaned):
        # keep selected; ExtraVideoCue normalizes
        pass
    elif not cleaned:
        cleaned = ["*"]
    entry = ExtraVideoCue(
        id=cue_id,
        pixera_name=pixera_name,
        label=body.label or pixera_name,
        description=body.description,
        projectors=cleaned,
        dramaturgy_active=body.dramaturgy_active,
    )
    data.videos.extra.append(entry)
    save_overrides(data)
    return entry


def add_extra_sound(body: ExtraSoundCreateRequest) -> ExtraSoundCue:
    data = load_overrides(force=True)
    soundname = body.soundname.strip()
    cue_id = _slug_id(body.id or soundname)
    if any(e.id == cue_id for e in data.sounds.extra):
        raise ValueError(f"Sound-Extra {cue_id!r} existiert bereits")
    from app.services.sound_cue_catalog import get_sound_cue_catalog_service

    raw = get_sound_cue_catalog_service().load_raw()
    if any(c.id == cue_id for c in raw.cues):
        raise ValueError(f"Sound-id {cue_id!r} ist bereits im Katalog")
    entry = ExtraSoundCue(
        id=cue_id,
        label=body.label or soundname,
        soundname=soundname,
        action=body.action,
        description=body.description,
        midi_note=body.midi_note,
        channel=body.channel,
        dramaturgy_active=body.dramaturgy_active,
    )
    data.sounds.extra.append(entry)
    save_overrides(data)
    return entry


def add_extra_light(body: ExtraLightCreateRequest) -> ExtraLightCue:
    data = load_overrides(force=True)
    if not body.channels and not body.groups:
        raise ValueError("Licht braucht mindestens channels oder groups")
    desc = (body.description or "").strip()
    cue_id = _slug_id(body.id or desc or "light_scene")
    if any(e.id == cue_id for e in data.lights.extra):
        raise ValueError(f"Licht-Extra {cue_id!r} existiert bereits")
    from app.director.media.database import MediaDatabase

    db = MediaDatabase()
    if any(s.id == cue_id for s in db.light_scenes):
        # May already include extras — check raw file
        pass
    light_path = db.data_dir / "light_scenes.json"
    if light_path.is_file():
        scenes = json.loads(light_path.read_text(encoding="utf-8")).get("scenes", [])
        if any(s.get("id") == cue_id for s in scenes):
            raise ValueError(f"Licht-id {cue_id!r} ist bereits im Katalog")
    entry = ExtraLightCue(
        id=cue_id,
        description=desc or cue_id,
        location=body.location,
        channels=body.channels,
        groups=body.groups,
        dramaturgy_active=body.dramaturgy_active,
    )
    data.lights.extra.append(entry)
    save_overrides(data)
    return entry


def patch_cue(kind: CueKind, cue_id: str, body: CueAdminPatchRequest) -> CueOverrideFlags:
    if body.dramaturgy_active is None and body.removed is None:
        raise ValueError("Keine Änderungen")
    data = load_overrides(force=True)
    cue_id = cue_id.strip().lower()
    overlay = _kind_overlay(data, kind)
    existing = overlay.overrides.get(cue_id) or CueOverrideFlags()
    updated = CueOverrideFlags(
        dramaturgy_active=(
            body.dramaturgy_active if body.dramaturgy_active is not None else existing.dramaturgy_active
        ),
        removed=body.removed if body.removed is not None else existing.removed,
    )
    # For extras, also mirror dramaturgy_active onto the extra entry when set
    if body.dramaturgy_active is not None:
        for extra in overlay.extra:
            if extra.id == cue_id:
                extra.dramaturgy_active = body.dramaturgy_active
                break
    overlay.overrides[cue_id] = updated
    save_overrides(data)
    return updated


def delete_extra(kind: CueKind, cue_id: str) -> None:
    data = load_overrides(force=True)
    cue_id = cue_id.strip().lower()
    overlay = _kind_overlay(data, kind)
    before = len(overlay.extra)
    overlay.extra = [e for e in overlay.extra if e.id != cue_id]
    if len(overlay.extra) == before:
        raise ValueError(f"Kein Extra-Eintrag {cue_id!r} zum Löschen (Katalog-Einträge nur entfernen via removed)")
    overlay.overrides.pop(cue_id, None)
    save_overrides(data)
