"""Runtime overrides for video/light output targets (Technik UI, global until restart)."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class _Overrides:
    video_hosts: list[str] | None = None
    video_port: int | None = None
    light_host: str | None = None
    light_port: int | None = None
    # When True, light overrides are intentionally cleared (venue without light yet).
    light_cleared: bool = False


_lock = threading.Lock()
_overrides = _Overrides()


def _normalize_hosts(hosts: list[str] | None) -> list[str] | None:
    if hosts is None:
        return None
    cleaned = [h.strip() for h in hosts if h and str(h).strip()]
    return cleaned or None


def parse_host_list(value: str | list[str] | None) -> list[str] | None:
    """Accept a single host, comma-separated string, or list."""
    if value is None:
        return None
    if isinstance(value, list):
        return _normalize_hosts([str(v) for v in value])
    text = str(value).strip()
    if not text:
        return None
    if "," in text:
        return _normalize_hosts(text.split(","))
    return _normalize_hosts([text])


def default_video_target() -> tuple[str, int]:
    host = settings.pixera_osc_host or settings.osc_host
    port = settings.pixera_osc_port or settings.osc_port
    return host, port


def default_video_targets() -> list[tuple[str, int]]:
    host, port = default_video_target()
    return [(host, port)]


def default_light_target() -> tuple[str, int]:
    if settings.light_output == "mirror":
        return settings.osc_host, settings.osc_port
    return settings.light_desk_host(), settings.light_desk_port()


def effective_video_targets() -> list[tuple[str, int]]:
    with _lock:
        hosts = list(_overrides.video_hosts) if _overrides.video_hosts else None
        port = _overrides.video_port
    default_host, default_port = default_video_target()
    resolved_port = port if port is not None else default_port
    if hosts:
        return [(h, resolved_port) for h in hosts]
    return [(default_host, resolved_port)]


def effective_video_target() -> tuple[str, int]:
    return effective_video_targets()[0]


def effective_light_target() -> tuple[str, int]:
    with _lock:
        host = _overrides.light_host
        port = _overrides.light_port
    default_host, default_port = default_light_target()
    return host or default_host, port if port is not None else default_port


def get_override_state() -> _Overrides:
    with _lock:
        return _Overrides(
            video_hosts=list(_overrides.video_hosts) if _overrides.video_hosts else None,
            video_port=_overrides.video_port,
            light_host=_overrides.light_host,
            light_port=_overrides.light_port,
            light_cleared=_overrides.light_cleared,
        )


def apply_overrides(
    *,
    video_host: str | None = None,
    video_hosts: list[str] | None = None,
    video_port: int | None = None,
    light_host: str | None = None,
    light_port: int | None = None,
    clear_light: bool = False,
    reset: bool = False,
) -> tuple[bool, bool]:
    """Apply overrides. Returns (video_changed, light_changed)."""
    with _lock:
        if reset:
            _overrides.video_hosts = None
            _overrides.video_port = None
            _overrides.light_host = None
            _overrides.light_port = None
            _overrides.light_cleared = False
            return True, True

        prev_video = (
            tuple(_overrides.video_hosts) if _overrides.video_hosts else None,
            _overrides.video_port,
        )
        prev_light = (
            _overrides.light_host,
            _overrides.light_port,
            _overrides.light_cleared,
        )

        hosts = video_hosts
        if hosts is None and video_host is not None:
            hosts = parse_host_list(video_host)
        if hosts is not None:
            _overrides.video_hosts = _normalize_hosts(hosts)
        if video_port is not None:
            _overrides.video_port = video_port

        if clear_light:
            _overrides.light_host = None
            _overrides.light_port = None
            _overrides.light_cleared = True
        else:
            if light_host is not None:
                cleaned = light_host.strip() or None
                _overrides.light_host = cleaned
                if cleaned:
                    _overrides.light_cleared = False
            if light_port is not None:
                _overrides.light_port = light_port
                _overrides.light_cleared = False

        video_changed = prev_video != (
            tuple(_overrides.video_hosts) if _overrides.video_hosts else None,
            _overrides.video_port,
        )
        light_changed = prev_light != (
            _overrides.light_host,
            _overrides.light_port,
            _overrides.light_cleared,
        )

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
