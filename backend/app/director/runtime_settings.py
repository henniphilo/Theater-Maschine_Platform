"""Operator-editable runtime overrides for selected Settings fields.

.env remains the default source. Overrides are applied in-process (mutate
``settings``) and persisted under ``data/runtime_settings.json`` so they
survive reloads without committing secrets or requiring a process restart.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Literal

from app.core.config import settings

logger = logging.getLogger(__name__)

# Only non-secret, operational knobs — never API keys, DB URLs, or paths.
RuntimeSettingKey = Literal[
    "director_dramaturgy_mode",
    "osc_dry_run",
    "light_output",
    "visual_output",
    "sound_output",
    "light_osc_mirror",
    "sound_osc_mirror",
    "teil2_prepare_model",
    "teil2_atmosphere_use_llm",
    "teil2_use_analyse_llm",
    "teil2_dramaturgy_chunk_size",
    "avatar_done_gate_enabled",
    "avatar_done_source",
    "part1_workshop_preview_hardware",
    "director_execute_mode",
    "signal_trace_enabled",
]

ALLOWLIST: frozenset[str] = frozenset(
    {
        "director_dramaturgy_mode",
        "osc_dry_run",
        "light_output",
        "visual_output",
        "sound_output",
        "light_osc_mirror",
        "sound_osc_mirror",
        "teil2_prepare_model",
        "teil2_atmosphere_use_llm",
        "teil2_use_analyse_llm",
        "teil2_dramaturgy_chunk_size",
        "avatar_done_gate_enabled",
        "avatar_done_source",
        "part1_workshop_preview_hardware",
        "director_execute_mode",
        "signal_trace_enabled",
    }
)

_VALIDATORS: dict[str, Any] = {
    "director_dramaturgy_mode": frozenset({"llm", "rules"}),
    "light_output": frozenset({"tcp", "osc", "mirror"}),
    "visual_output": frozenset({"pixera", "touchdesigner", "both"}),
    "sound_output": frozenset({"osc", "midi", "both"}),
    "avatar_done_source": frozenset({"qlab", "pixera", "manual"}),
    "director_execute_mode": frozenset({"immediate", "sequenced"}),
}

_lock = threading.Lock()
_env_defaults: dict[str, Any] | None = None
_overrides: dict[str, Any] = {}
_loaded = False
_persist_path_override: Path | None = None


def _persist_path() -> Path:
    if _persist_path_override is not None:
        return _persist_path_override
    return Path(settings.director_data_dir) / "runtime_settings.json"


def _capture_env_defaults() -> dict[str, Any]:
    return {key: getattr(settings, key) for key in sorted(ALLOWLIST)}


def _ensure_defaults_locked() -> dict[str, Any]:
    global _env_defaults
    if _env_defaults is None:
        _env_defaults = _capture_env_defaults()
    return _env_defaults


def _write_persist_locked() -> None:
    path = _persist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not _overrides:
        if path.is_file():
            path.unlink()
        return
    path.write_text(
        json.dumps(_overrides, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_value(key: str, value: Any) -> Any:
    if key not in ALLOWLIST:
        raise ValueError(f"Setting nicht editierbar: {key}")
    allowed = _VALIDATORS.get(key)
    if allowed is not None:
        if value not in allowed:
            raise ValueError(f"Ungültiger Wert für {key}: {value!r}")
        return value
    if key == "teil2_prepare_model":
        text = str(value).strip()
        if not text or len(text) > 80:
            raise ValueError("teil2_prepare_model ungültig")
        return text
    if key == "teil2_dramaturgy_chunk_size":
        size = int(value)
        if size < 6 or size > 40:
            raise ValueError("teil2_dramaturgy_chunk_size muss 6–40 sein")
        return size
    if key in {
        "osc_dry_run",
        "light_osc_mirror",
        "sound_osc_mirror",
        "teil2_atmosphere_use_llm",
        "teil2_use_analyse_llm",
        "avatar_done_gate_enabled",
        "part1_workshop_preview_hardware",
        "signal_trace_enabled",
    }:
        if not isinstance(value, bool):
            raise ValueError(f"{key} muss bool sein")
        return value
    raise ValueError(f"Kein Validator für {key}")


def _apply_to_settings(key: str, value: Any) -> None:
    setattr(settings, key, value)


def _side_effects(changed: set[str]) -> None:
    if changed & {"light_output", "osc_dry_run"}:
        try:
            from app.director.outputs.light_tcp import get_light_tcp_session

            session = get_light_tcp_session()
            if session.connected:
                session.close_session(dry_run=bool(settings.osc_dry_run))
        except Exception:
            logger.exception("Failed to disconnect light TCP after settings change")

    if changed & {"light_output", "visual_output", "sound_output"}:
        try:
            from app.director.output_targets import refresh_pipeline_targets

            refresh_pipeline_targets()
        except Exception:
            logger.exception("Failed to refresh pipeline targets after settings change")

    if "avatar_done_gate_enabled" in changed or "avatar_done_source" in changed:
        try:
            from app.director.outputs.avatar_done_listener import (
                start_avatar_done_listener,
                stop_avatar_done_listener,
            )

            stop_avatar_done_listener()
            if settings.avatar_done_gate_enabled:
                start_avatar_done_listener(
                    host=settings.avatar_done_osc_host,
                    port=settings.avatar_done_osc_port,
                )
        except Exception:
            logger.exception("Failed to restart avatar-done listener")


def load_persisted_overrides() -> None:
    """Load overrides from disk once (call from app lifespan)."""
    global _loaded
    with _lock:
        if _loaded:
            return
        _ensure_defaults_locked()
        path = _persist_path()
        raw: dict[str, Any] = {}
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    raw = data
            except (json.JSONDecodeError, OSError):
                logger.exception("Could not read %s", path)
        applied: dict[str, Any] = {}
        for key, value in raw.items():
            if key not in ALLOWLIST:
                continue
            try:
                validated = _validate_value(key, value)
            except ValueError:
                logger.warning("Ignoring invalid persisted setting %s=%r", key, value)
                continue
            _apply_to_settings(key, validated)
            applied[key] = validated
        _overrides.clear()
        _overrides.update(applied)
        _loaded = True


def ensure_loaded() -> None:
    load_persisted_overrides()


def reset_runtime_settings_for_tests(*, persist_path: Path | None = None) -> None:
    """Restore current settings as defaults and clear overrides (test helper)."""
    global _loaded, _env_defaults, _persist_path_override
    with _lock:
        if persist_path is not None:
            _persist_path_override = persist_path
        path = _persist_path()
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
        _env_defaults = _capture_env_defaults()
        _overrides.clear()
        _loaded = True


def get_snapshot() -> dict[str, Any]:
    """Return defaults / overrides / effective for API."""
    ensure_loaded()
    with _lock:
        defaults = dict(_ensure_defaults_locked())
        overrides = dict(_overrides)
    effective = {key: getattr(settings, key) for key in sorted(ALLOWLIST)}
    return {
        "defaults": defaults,
        "overrides": overrides,
        "effective": effective,
    }


def apply_runtime_settings(
    updates: dict[str, Any] | None = None,
    *,
    reset: bool = False,
    clear_keys: list[str] | None = None,
) -> set[str]:
    """Apply operator updates. Returns set of changed keys."""
    ensure_loaded()
    changed: set[str] = set()
    with _lock:
        defaults = _ensure_defaults_locked()
        if reset:
            for key, value in defaults.items():
                if getattr(settings, key) != value or key in _overrides:
                    _apply_to_settings(key, value)
                    changed.add(key)
            _overrides.clear()
            _write_persist_locked()
        else:
            for key in clear_keys or []:
                if key not in ALLOWLIST:
                    raise ValueError(f"Setting nicht editierbar: {key}")
                if key in _overrides:
                    del _overrides[key]
                    _apply_to_settings(key, defaults[key])
                    changed.add(key)
            for key, value in (updates or {}).items():
                validated = _validate_value(key, value)
                if getattr(settings, key) != validated or _overrides.get(key) != validated:
                    _apply_to_settings(key, validated)
                    _overrides[key] = validated
                    changed.add(key)
            if changed:
                _write_persist_locked()
    if changed:
        _side_effects(changed)
    return changed
