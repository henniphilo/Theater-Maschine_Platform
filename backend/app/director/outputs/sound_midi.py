"""Sound output via MIDI (Note On/Off) for QLab, Ableton, Mischpult, etc."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


@dataclass(frozen=True)
class MidiCueMapping:
    note: int
    channel: int = 1
    velocity: int | None = None


def _normalize_iac_port_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.lower().replace("driver", "treiber")).strip()


def _iac_bus_number(name: str) -> str | None:
    match = re.search(r"bus\s*(\d+)", name, flags=re.IGNORECASE)
    return match.group(1) if match else None


def resolve_midi_output_port(requested: str | None, available: list[str]) -> str | None:
    """Match configured MIDI port across macOS locales (Driver vs Treiber)."""
    if not available:
        return None
    if not requested:
        for name in available:
            if "iac" in name.lower():
                return name
        return available[0]
    if requested in available:
        return requested
    by_lower = {name.lower(): name for name in available}
    if requested.lower() in by_lower:
        return by_lower[requested.lower()]
    normalized_requested = _normalize_iac_port_name(requested)
    for name in available:
        if _normalize_iac_port_name(name) == normalized_requested:
            return name
    requested_bus = _iac_bus_number(requested)
    if requested_bus:
        for name in available:
            if "iac" in name.lower() and _iac_bus_number(name) == requested_bus:
                return name
    return None


def _repo_roots() -> list[Path]:
    module_root = Path(__file__).resolve()
    data_dir = Path(settings.director_data_dir)
    if not data_dir.is_absolute():
        data_dir = module_root.parents[3] / data_dir
    return [data_dir.parent, module_root.parents[3], module_root.parents[4], Path.cwd(), Path("/app")]


def _map_path() -> Path | None:
    configured = Path(settings.sound_midi_map_path)
    if configured.is_file():
        return configured
    for root in _repo_roots():
        candidate = root / settings.sound_midi_map_path
        if candidate.is_file():
            return candidate
        candidate = root / "data" / "sound_midi_map.json"
        if candidate.is_file():
            return candidate
    return None


def load_sound_midi_map() -> dict[str, MidiCueMapping]:
    from app.services.sound_cue_catalog import get_sound_cue_catalog_service

    catalog_service = get_sound_cue_catalog_service()
    catalog_path_file = catalog_service.load()
    if catalog_path_file.cues:
        return catalog_service.to_midi_map(catalog_path_file)

    path = _map_path()
    defaults = {"channel": settings.sound_midi_channel, "velocity": settings.sound_midi_default_velocity}
    cues: dict[str, MidiCueMapping] = {}
    if path is None:
        return cues
    data = json.loads(path.read_text(encoding="utf-8"))
    defaults.update(data.get("defaults") or {})
    default_channel = int(defaults.get("channel", settings.sound_midi_channel))
    default_velocity = int(defaults.get("velocity", settings.sound_midi_default_velocity))
    for cue_id, spec in (data.get("cues") or {}).items():
        if not isinstance(spec, dict):
            continue
        cues[cue_id] = MidiCueMapping(
            note=int(spec["note"]),
            channel=int(spec.get("channel", default_channel)),
            velocity=int(spec["velocity"]) if spec.get("velocity") is not None else default_velocity,
        )
    return cues


class SoundMidiBridge:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._port_name: str | None = None
        self._port: object | None = None
        self._map = load_sound_midi_map()

    def reload_map(self) -> None:
        self._map = load_sound_midi_map()

    def mapping_for(self, cue_id: str) -> MidiCueMapping | None:
        mapped = self._map.get(cue_id)
        if mapped is not None:
            return mapped
        if not settings.sound_midi_auto_note:
            return None
        base = settings.sound_midi_note_base
        index = abs(hash(cue_id)) % 80
        return MidiCueMapping(
            note=min(127, base + index),
            channel=settings.sound_midi_channel,
            velocity=settings.sound_midi_default_velocity,
        )

    def trigger(self, cue_id: str, volume: float, *, dry_run: bool = False) -> None:
        mapping = self._require_mapping(cue_id)
        velocity = self._velocity(volume, mapping)
        self._send(
            f"note_on ch={mapping.channel} note={mapping.note} vel={velocity}",
            self._build_message("note_on", mapping, velocity=velocity),
            dry_run=dry_run,
        )

    def stop(self, cue_id: str, *, dry_run: bool = False) -> None:
        mapping = self._require_mapping(cue_id)
        self._send(
            f"note_off ch={mapping.channel} note={mapping.note}",
            self._build_message("note_off", mapping, velocity=0),
            dry_run=dry_run,
        )

    def hold(self, cue_id: str, volume: float, *, dry_run: bool = False) -> None:
        self.trigger(cue_id, volume, dry_run=dry_run)

    def stop_all(self, *, dry_run: bool = False) -> None:
        channel = settings.sound_midi_channel
        from app.director.outputs.midi_log import log_midi_command

        port = self._port_label()
        log_midi_command(port, f"control_change ch={channel} cc=123 val=0 (all notes off)", dry_run=dry_run)
        if dry_run or self._is_dry_run():
            return
        out = self._open_port()
        import mido

        out.send(mido.Message("control_change", channel=channel - 1, control=123, value=0))

    def _require_mapping(self, cue_id: str) -> MidiCueMapping:
        mapping = self.mapping_for(cue_id)
        if mapping is None:
            raise ValueError(f"No MIDI mapping for sound cue: {cue_id}")
        return mapping

    @staticmethod
    def _velocity(volume: float, mapping: MidiCueMapping) -> int:
        base = mapping.velocity if mapping.velocity is not None else settings.sound_midi_default_velocity
        scaled = int(max(0.0, min(1.0, volume)) * 127)
        if volume > 0 and scaled == 0:
            scaled = 1
        return min(127, max(1, scaled)) if volume > 0 else base

    def _build_message(self, msg_type: str, mapping: MidiCueMapping, *, velocity: int):
        import mido

        return mido.Message(
            msg_type,
            channel=mapping.channel - 1,
            note=mapping.note,
            velocity=velocity,
        )

    def _send(self, label: str, message: object, *, dry_run: bool) -> None:
        from app.director.outputs.midi_log import log_midi_command

        port = self._port_label()
        log_midi_command(port, label, dry_run=dry_run or self._is_dry_run())
        if dry_run or self._is_dry_run():
            return
        try:
            out = self._open_port()
            out.send(message)
        except Exception as exc:
            hint = (
                "MIDI-Ausgabe nur mit Backend nativ auf dem Mac (IAC Driver) — "
                "nicht aus dem Docker-Container."
            )
            log_midi_command(port, f"FEHLER: {exc} · {hint}", dry_run=False)
            raise RuntimeError(f"MIDI send failed: {exc}. {hint}") from exc

    def _is_dry_run(self) -> bool:
        return settings.osc_dry_run

    def _port_label(self) -> str:
        if self._port_name:
            return self._port_name
        if settings.sound_midi_port:
            return settings.sound_midi_port
        try:
            import mido

            names = mido.get_output_names()
            return names[0] if names else "(no MIDI output)"
        except Exception:
            return "(midi unavailable)"

    def _open_port(self):
        import mido

        with self._lock:
            if self._port is not None:
                return self._port
            names = mido.get_output_names()
            if not names:
                raise RuntimeError("No MIDI output ports available")
            port_name = settings.sound_midi_port
            chosen = resolve_midi_output_port(port_name, names)
            if chosen is None:
                raise RuntimeError(
                    f"MIDI port not found: {port_name!r} (available: {names})"
                    if port_name
                    else f"No MIDI output ports available (available: {names})"
                )
            self._port = mido.open_output(chosen)
            self._port_name = chosen
            return self._port

    def close(self) -> None:
        with self._lock:
            if self._port is not None:
                try:
                    self._port.close()
                except Exception:
                    pass
                self._port = None
                self._port_name = None


_midi_bridge: SoundMidiBridge | None = None


def get_sound_midi_bridge() -> SoundMidiBridge:
    global _midi_bridge
    if _midi_bridge is None:
        _midi_bridge = SoundMidiBridge()
    return _midi_bridge


def close_sound_midi() -> None:
    global _midi_bridge
    if _midi_bridge is not None:
        _midi_bridge.close()
        _midi_bridge = None
