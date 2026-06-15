from fastapi import APIRouter

from app.core.config import settings
from app.director.media.database import MediaDatabase
from app.schemas.sound_cues import SoundCueCatalog
from app.schemas.video_cues import VideoCueCatalog
from app.services.sound_cue_catalog import get_sound_cue_catalog_service
from app.services.video_cue_catalog import get_video_cue_catalog_service

router = APIRouter(prefix="/media", tags=["media"])
_sound_catalog = get_sound_cue_catalog_service()
_video_catalog = get_video_cue_catalog_service()


@router.get("/sound-cues", response_model=SoundCueCatalog)
def get_sound_cues() -> SoundCueCatalog:
    return _sound_catalog.load()


@router.get("/video-cues", response_model=VideoCueCatalog)
def get_video_cues() -> VideoCueCatalog:
    return _video_catalog.load()


@router.get("/catalog")
def get_media_catalog() -> dict:
    db = MediaDatabase()
    video_catalog = _video_catalog.load()
    return {
        "videos": [v.model_dump() for v in db.videos],
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
                "light_scene": "/eos/chan/{channel}/full",
                "light_blackout": "/eos/key/out",
            },
            "docs": "touchdesigner/README_touchdesigner_setup.md",
        },
        "pixera": {
            "output": settings.visual_output,
            "osc_host": settings.pixera_osc_host or settings.osc_host,
            "osc_port": settings.pixera_osc_port or settings.osc_port,
            "osc_dry_run": settings.osc_dry_run,
            "address": video_catalog.osc_address,
            "overview_clips": "media/video/Video Übersicht.csv",
            "overview_projectors": "media/video/Projektor Übersicht.csv",
            "cues_catalog": settings.video_cues_path,
        },
        "lighting": {
            "output": settings.light_output,
            "osc_mirror": settings.light_osc_mirror,
            "tcp_host": settings.light_tcp_host,
            "tcp_port": settings.light_tcp_port,
            "tcp_protocol": settings.light_tcp_protocol,
            "osc_host": settings.light_tcp_host if settings.light_output == "tcp" else (settings.light_osc_host or settings.light_tcp_host),
            "osc_port": settings.light_tcp_port if settings.light_output == "tcp" else settings.light_osc_port,
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
