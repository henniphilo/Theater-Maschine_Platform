"""Runtime overrides for video/light output targets (Technik UI, global until restart)."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class _Overrides:
    video_host: str | None = None
    video_port: int | None = None
    light_host: str | None = None
    light_port: int | None = None


_lock = threading.Lock()
_overrides = _Overrides()


def default_video_target() -> tuple[str, int]:
    host = settings.pixera_osc_host or settings.osc_host
    port = settings.pixera_osc_port or settings.osc_port
    return host, port


def default_light_target() -> tuple[str, int]:
    if settings.light_output == "mirror":
        return settings.osc_host, settings.osc_port
    return settings.light_desk_host(), settings.light_desk_port()


def effective_video_target() -> tuple[str, int]:
    with _lock:
        host = _overrides.video_host
        port = _overrides.video_port
    default_host, default_port = default_video_target()
    return host or default_host, port if port is not None else default_port


def effective_light_target() -> tuple[str, int]:
    with _lock:
        host = _overrides.light_host
        port = _overrides.light_port
    default_host, default_port = default_light_target()
    return host or default_host, port if port is not None else default_port


def get_override_state() -> _Overrides:
    with _lock:
        return _Overrides(
            video_host=_overrides.video_host,
            video_port=_overrides.video_port,
            light_host=_overrides.light_host,
            light_port=_overrides.light_port,
        )


def apply_overrides(
    *,
    video_host: str | None = None,
    video_port: int | None = None,
    light_host: str | None = None,
    light_port: int | None = None,
    reset: bool = False,
) -> tuple[bool, bool]:
    """Apply overrides. Returns (video_changed, light_changed)."""
    with _lock:
        if reset:
            _overrides.video_host = None
            _overrides.video_port = None
            _overrides.light_host = None
            _overrides.light_port = None
            return True, True

        prev_video = (_overrides.video_host, _overrides.video_port)
        prev_light = (_overrides.light_host, _overrides.light_port)

        if video_host is not None:
            _overrides.video_host = video_host.strip() or None
        if video_port is not None:
            _overrides.video_port = video_port
        if light_host is not None:
            _overrides.light_host = light_host.strip() or None
        if light_port is not None:
            _overrides.light_port = light_port

        video_changed = (prev_video != (_overrides.video_host, _overrides.video_port)) or reset
        light_changed = (prev_light != (_overrides.light_host, _overrides.light_port)) or reset

    if light_changed:
        _disconnect_light_tcp()

    return video_changed, light_changed


def _disconnect_light_tcp() -> None:
    from app.director.outputs.light_tcp import get_light_tcp_session

    session = get_light_tcp_session()
    if session.connected:
        session.close_session(dry_run=settings.osc_dry_run)


def refresh_pipeline_targets() -> None:
    from app.director.pipeline import get_director_pipeline

    get_director_pipeline().refresh_output_targets()
