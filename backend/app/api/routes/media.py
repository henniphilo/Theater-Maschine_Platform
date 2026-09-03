from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.director.output_targets import (
    effective_light_target,
    effective_video_target,
    effective_video_targets,
)
from app.director.media.database import MediaDatabase
from app.schemas.avatar_speech import AvatarSpeechCatalog
from app.schemas.extra_media import (
    CueAdminPatchRequest,
    CueAdminResponse,
    CueKind,
    ExtraLightCreateRequest,
    ExtraSoundCreateRequest,
    ExtraVideoCreateRequest,
)
from app.schemas.sound_cues import SoundCueCatalog
from app.schemas.video_cues import VideoCueCatalog
from app.services import extra_media_overrides as extra_media
from app.services import light_inventory_admin as light_inventory
from app.services.light_inventory_admin import (
    LightChannelPolicyPatchRequest,
    LightInventoryAdminResponse,
    LightInventoryGroupCreateRequest,
    LightInventoryGroupEnabledPatch,
)
from app.services.sound_cue_catalog import get_sound_cue_catalog_service
from app.services.video_cue_catalog import get_video_cue_catalog_service
from app.services.avatar_speech_catalog import get_avatar_speech_catalog_service
from app.services.video_scope import VideoScope

router = APIRouter(prefix="/media", tags=["media"])
_sound_catalog = get_sound_cue_catalog_service()
_video_catalog = get_video_cue_catalog_service()
_avatar_catalog = get_avatar_speech_catalog_service()


@router.get("/sound-cues", response_model=SoundCueCatalog)
def get_sound_cues() -> SoundCueCatalog:
    return _sound_catalog.load()


@router.get("/video-cues", response_model=VideoCueCatalog)
def get_video_cues(video_scope: VideoScope = Query(default="part2")) -> VideoCueCatalog:
    return _video_catalog.load(video_scope)


@router.get("/avatar-speech", response_model=AvatarSpeechCatalog)
def get_avatar_speech() -> AvatarSpeechCatalog:
    return _avatar_catalog.load()


@router.get("/cue-admin", response_model=CueAdminResponse)
def get_cue_admin() -> CueAdminResponse:
    return extra_media.build_cue_admin_response()


@router.post("/cue-admin/video")
def create_extra_video(body: ExtraVideoCreateRequest) -> dict:
    try:
        entry = extra_media.add_extra_video(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return entry.model_dump()


@router.post("/cue-admin/sound")
def create_extra_sound(body: ExtraSoundCreateRequest) -> dict:
    try:
        entry = extra_media.add_extra_sound(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return entry.model_dump()


@router.post("/cue-admin/light")
def create_extra_light(body: ExtraLightCreateRequest) -> dict:
    try:
        entry = extra_media.add_extra_light(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return entry.model_dump()


@router.patch("/cue-admin/{kind}/{cue_id}")
def patch_cue_admin(kind: CueKind, cue_id: str, body: CueAdminPatchRequest) -> dict:
    try:
        flags = extra_media.patch_cue(kind, cue_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return flags.model_dump()


@router.delete("/cue-admin/{kind}/{cue_id}")
def delete_cue_admin(kind: CueKind, cue_id: str) -> dict:
    try:
        extra_media.delete_extra(kind, cue_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": cue_id, "kind": kind}


@router.get("/light-inventory", response_model=LightInventoryAdminResponse)
def get_light_inventory_admin() -> LightInventoryAdminResponse:
    return light_inventory.build_admin_response()


@router.patch("/light-inventory/policy")
def patch_light_channel_policy(body: LightChannelPolicyPatchRequest) -> dict:
    try:
        policy = light_inventory.patch_policy(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return policy.model_dump()


@router.patch("/light-inventory/groups/{group_id}")
def patch_light_inventory_group(group_id: str, body: LightInventoryGroupEnabledPatch) -> dict:
    try:
        group = light_inventory.set_inventory_group_enabled(group_id, body.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return group.model_dump()


@router.post("/light-inventory/groups")
def create_light_inventory_group(body: LightInventoryGroupCreateRequest) -> dict:
    try:
        group = light_inventory.add_inventory_group(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return group.model_dump()


@router.delete("/light-inventory/groups/{group_id}")
def delete_light_inventory_group(group_id: str) -> dict:
    try:
        light_inventory.delete_inventory_group(group_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": group_id}


@router.get("/catalog")
def get_media_catalog(video_scope: VideoScope = Query(default="part2")) -> dict:
    db = MediaDatabase()
    video_catalog = _video_catalog.load(video_scope)
    allowed_video_ids = {clip.id for clip in video_catalog.clips}
    video_host, video_port = effective_video_target()
    video_targets = effective_video_targets()
    light_host, light_port = effective_light_target()
    return {
        "videos": [v.model_dump() for v in db.videos if v.id in allowed_video_ids],
        "projectors": [p.model_dump() for p in video_catalog.projectors],
        "recordings": [r.model_dump() for r in db.recordings],
        "sounds": [s.model_dump() for s in db.sounds],
        "lights": [s.model_dump() for s in db.light_scenes],
        "light_inventory": db.light_inventory,
        "media_root": str(db.media_root),
        "touchdesigner": {
            "osc_host": settings.osc_host,
            "osc_port": settings.osc_port,
            "osc_dry_run": settings.osc_dry_run,
            "addresses": {
                "play_clip": "/visual/play_clip",
                "stop_clip": "/visual/stop_clip",
                "blackout": "/visual/blackout",
                "sound_trigger": "/sound/trigger",
                "light_scene": "/eos/chan/{channel}/full | /eos/chan/{channel} (0–100 %)",
                "light_blackout": "/eos/key/out",
            },
            "docs": "touchdesigner/README_touchdesigner_setup.md",
        },
        "pixera": {
            "output": settings.visual_output,
            "osc_host": video_host,
            "osc_hosts": [host for host, _port in video_targets],
            "osc_port": video_port,
            "osc_dry_run": settings.osc_dry_run,
            "address": video_catalog.osc_address,
            "overview_clips": "media/video/Video Übersicht.csv",
            "overview_projectors": "media/video/Projektor Übersicht.csv",
            "cues_catalog": settings.video_cues_path,
        },
        "lighting": {
            "output": settings.light_output,
            "osc_mirror": settings.light_osc_mirror,
            "tcp_host": light_host if settings.light_output == "tcp" else settings.light_tcp_host,
            "tcp_port": light_port if settings.light_output == "tcp" else settings.light_tcp_port,
            "tcp_protocol": settings.light_tcp_protocol,
            "osc_host": light_host,
            "osc_port": light_port,
            "preview_osc_host": light_host if settings.light_output == "mirror" else None,
            "preview_osc_port": light_port if settings.light_output == "mirror" else None,
            "preview_set_scene": "/light/set_scene",
            "preview_blackout": "/light/blackout",
            "qlab_relay_port": settings.osc_port if settings.light_output == "mirror" else None,
        },
        "sound": {
            "output": settings.sound_output,
            "osc_mirror": settings.sound_osc_mirror,
            "osc_host": settings.osc_host,
            "osc_port": settings.osc_port,
            "midi_port": settings.sound_midi_port,
            "midi_channel": settings.sound_midi_channel,
            "midi_map": settings.sound_midi_map_path,
            "overview": "media/sound/Sound Übersicht.csv",
            "cues_catalog": settings.sound_cues_path,
        },
        "data_dir": str(db.data_dir),
    }
