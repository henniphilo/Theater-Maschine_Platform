"""Named venue network profiles (Burgtheater / Hallein) for operator toggle."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_persist_path_override: Path | None = None


class VenueProfile(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=80)
    self_host: str | None = None
    video_hosts: list[str] = Field(min_length=1)
    video_port: int = Field(ge=1, le=65535, default=8990)
    light_host: str | None = None
    light_port: int | None = Field(default=None, ge=1, le=65535)
    notes: str = ""

    @field_validator("video_hosts")
    @classmethod
    def _normalize_hosts(cls, value: list[str]) -> list[str]:
        hosts = [h.strip() for h in value if h and h.strip()]
        if not hosts:
            raise ValueError("video_hosts must not be empty")
        return hosts

    @property
    def light_configured(self) -> bool:
        return bool(self.light_host and self.light_port)


class VenueProfilesState(BaseModel):
    version: int = 1
    active_id: str = "burgtheater"
    # Extra video hosts after the first are backups (e.g. Hallein .12).
    video_backup_enabled: bool = False
    profiles: list[VenueProfile] = Field(default_factory=list)


def _repo_data_candidates() -> list[Path]:
    module_root = Path(__file__).resolve()
    data_dir = Path(settings.director_data_dir)
    if not data_dir.is_absolute():
        data_dir = module_root.parents[1] / data_dir
    return [data_dir, module_root.parents[2] / "data", Path.cwd() / "data"]


def persist_path() -> Path:
    if _persist_path_override is not None:
        return _persist_path_override
    for candidate in _repo_data_candidates():
        path = candidate / "venue_profiles.json"
        if path.is_file():
            return path
    return _repo_data_candidates()[0] / "venue_profiles.json"


def set_persist_path_override(path: Path | None) -> None:
    global _persist_path_override
    _persist_path_override = path


def _default_state() -> VenueProfilesState:
    return VenueProfilesState(
        active_id="burgtheater",
        profiles=[
            VenueProfile(
                id="burgtheater",
                label="Burgtheater",
                self_host=None,
                video_hosts=["172.27.27.1"],
                video_port=8990,
                light_host="10.101.90.112",
                light_port=3032,
                notes="Pixera 172.27.27.1:8990 · EOS 10.101.90.112:3032",
            ),
            VenueProfile(
                id="hallein",
                label="Hallein",
                self_host="192.168.14.15",
                video_hosts=["192.168.14.11", "192.168.14.12"],
                video_port=8990,
                light_host="192.168.4.9",
                light_port=8000,
                notes=(
                    "Primär Pixera 192.168.14.11; .12 ist Backup (Toggle). "
                    "Show-Mac: 192.168.14.15. Licht 192.168.4.9:8000 (EOS TCP)."
                ),
            ),
        ],
    )


def resolve_video_hosts(profile: VenueProfile, *, backup_enabled: bool | None = None) -> list[str]:
    """Primary host always; additional hosts only when backup fan-out is enabled."""
    hosts = list(profile.video_hosts)
    if len(hosts) <= 1:
        return hosts
    enabled = video_backup_enabled() if backup_enabled is None else backup_enabled
    if enabled:
        return hosts
    return [hosts[0]]


def video_backup_enabled() -> bool:
    with _lock:
        return bool(load_state().video_backup_enabled)


def video_backup_available(profile: VenueProfile | None = None) -> bool:
    active = profile or get_active_profile()
    return len(active.video_hosts) > 1


def set_video_backup_enabled(enabled: bool, *, refresh_pipeline: bool = True) -> VenueProfilesState:
    """Persist backup toggle and re-apply active venue video targets."""
    from app.director.output_targets import apply_overrides, refresh_pipeline_targets

    with _lock:
        state = load_state()
        state.video_backup_enabled = bool(enabled)
        save_state(state)
        profile = next((p for p in state.profiles if p.id == state.active_id), state.profiles[0])
        hosts = resolve_video_hosts(profile, backup_enabled=state.video_backup_enabled)
        port = profile.video_port

    apply_overrides(video_hosts=hosts, video_port=port)
    if refresh_pipeline:
        refresh_pipeline_targets()
    logger.info(
        "venue_profiles: video_backup_enabled=%s video=%s",
        enabled,
        ",".join(hosts),
    )
    return list_profiles()


def load_state() -> VenueProfilesState:
    path = persist_path()
    if not path.is_file():
        state = _default_state()
        save_state(state)
        return state
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        state = VenueProfilesState.model_validate(raw)
    except Exception:
        logger.exception("venue_profiles: failed to load %s — using defaults", path)
        return _default_state()
    if not state.profiles:
        return _default_state()
    ids = {p.id for p in state.profiles}
    if state.active_id not in ids:
        state.active_id = state.profiles[0].id
    return state


def save_state(state: VenueProfilesState) -> None:
    path = persist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = state.model_dump()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def list_profiles() -> VenueProfilesState:
    with _lock:
        return load_state()


def get_active_profile() -> VenueProfile:
    state = list_profiles()
    for profile in state.profiles:
        if profile.id == state.active_id:
            return profile
    return state.profiles[0]


def activate_profile(profile_id: str, *, refresh_pipeline: bool = True) -> VenueProfile:
    """Persist active venue and apply video/light targets."""
    from app.director.output_targets import apply_overrides, refresh_pipeline_targets

    normalized = profile_id.strip().lower()
    with _lock:
        state = load_state()
        profile = next((p for p in state.profiles if p.id == normalized), None)
        if profile is None:
            raise KeyError(f"Unknown venue profile {profile_id!r}")
        state.active_id = profile.id
        save_state(state)
        hosts = resolve_video_hosts(profile, backup_enabled=state.video_backup_enabled)

    apply_overrides(
        video_hosts=hosts,
        video_port=profile.video_port,
        light_host=profile.light_host,
        light_port=profile.light_port,
        clear_light=not profile.light_configured,
    )
    if refresh_pipeline:
        refresh_pipeline_targets()
    logger.info(
        "venue_profiles: activated %s video=%s:%s light=%s backup=%s",
        profile.id,
        ",".join(hosts),
        profile.video_port,
        f"{profile.light_host}:{profile.light_port}" if profile.light_configured else "unset",
        state.video_backup_enabled,
    )
    return profile


def apply_active_profile_on_startup() -> None:
    """Re-apply persisted venue on backend start (after runtime_settings)."""
    try:
        activate_profile(get_active_profile().id, refresh_pipeline=True)
    except Exception:
        logger.exception("venue_profiles: failed to apply active profile on startup")


def update_profile_light(profile_id: str, light_host: str, light_port: int) -> VenueProfile:
    """Fill in light once known (e.g. Hallein) and optionally re-apply if active."""
    normalized = profile_id.strip().lower()
    host = light_host.strip()
    if not host:
        raise ValueError("light_host must not be empty")
    with _lock:
        state = load_state()
        updated: VenueProfile | None = None
        profiles: list[VenueProfile] = []
        for profile in state.profiles:
            if profile.id == normalized:
                updated = profile.model_copy(
                    update={"light_host": host, "light_port": light_port}
                )
                profiles.append(updated)
            else:
                profiles.append(profile)
        if updated is None:
            raise KeyError(f"Unknown venue profile {profile_id!r}")
        state.profiles = profiles
        save_state(state)
        active = state.active_id == updated.id
    if active:
        activate_profile(updated.id)
    return updated
