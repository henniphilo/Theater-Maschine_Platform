from fastapi import APIRouter

from app.core.config import settings
from app.director.media.database import MediaDatabase

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/catalog")
def get_media_catalog() -> dict:
    db = MediaDatabase()
    return {
        "videos": [v.model_dump() for v in db.videos],
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
        "lighting": {
            "output": settings.light_output,
            "osc_mirror": settings.light_osc_mirror,
            "tcp_host": settings.light_tcp_host,
            "tcp_port": settings.light_tcp_port,
            "tcp_protocol": settings.light_tcp_protocol,
            "osc_host": settings.light_tcp_host if settings.light_output == "tcp" else (settings.light_osc_host or settings.light_tcp_host),
            "osc_port": settings.light_tcp_port if settings.light_output == "tcp" else settings.light_osc_port,
        },
        "data_dir": str(db.data_dir),
    }
