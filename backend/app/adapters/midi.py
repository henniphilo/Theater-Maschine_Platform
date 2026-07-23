"""MIDI adapter — delegates to SoundMidiBridge (existing MIDI messages)."""

from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import (
    AdapterCommand,
    AdapterHealth,
    AdapterResult,
    HealthStatus,
    OutputAdapter,
    coerce_bool,
)
from app.core.config import settings
from app.director.outputs.sound_midi import SoundMidiBridge, get_sound_midi_bridge

logger = logging.getLogger(__name__)


class MidiAdapter(OutputAdapter):
    adapter_type = "midi"

    def __init__(
        self,
        *,
        device_id: str,
        name: str,
        configuration: dict[str, Any] | None = None,
        enabled: bool = True,
        bridge: SoundMidiBridge | None = None,
    ) -> None:
        self.device_id = device_id
        self.name = name
        self.configuration = dict(configuration or {})
        self.enabled = enabled
        self._bridge = bridge
        self._connected = False

    def _resolve_dry_run(self) -> bool:
        if coerce_bool(self.configuration.get("force_dry_run"), False):
            return True
        if not self.enabled:
            return True
        return bool(settings.osc_dry_run)

    def _get_bridge(self) -> SoundMidiBridge:
        if self._bridge is None:
            self._bridge = get_sound_midi_bridge()
        return self._bridge

    def connect(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        if dry_run:
            self._connected = True
            return AdapterResult(ok=True, message="midi: connected (dry-run)", dry_run=True)
        try:
            bridge = self._get_bridge()
            # Opening the port validates availability without changing MIDI protocol.
            bridge._open_port()  # noqa: SLF001
            self._connected = True
            return AdapterResult(
                ok=True,
                message=f"midi: opened port {bridge._port_name}",  # noqa: SLF001
                dry_run=False,
                details={"port": bridge._port_name},  # noqa: SLF001
            )
        except Exception as exc:
            return AdapterResult(ok=False, message=f"midi: connect failed: {exc}", dry_run=False)

    def disconnect(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        # Do not close the process-wide SoundMidiBridge singleton — other callers share it.
        self._connected = False
        return AdapterResult(ok=True, message="midi: disconnected", dry_run=dry_run)

    def test_connection(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        configured = self.configuration.get("midi_port") or settings.sound_midi_port
        if dry_run:
            return AdapterResult(
                ok=True,
                message="midi: dry-run connection test ok (no port open)",
                dry_run=True,
                details={"midi_port": configured},
            )
        try:
            import mido

            from app.director.outputs.sound_midi import resolve_midi_output_port

            names = mido.get_output_names()
            chosen = resolve_midi_output_port(
                str(configured) if configured else None,
                list(names),
            )
            if chosen is None:
                return AdapterResult(
                    ok=False,
                    message=f"midi: no matching output (available={list(names)})",
                    dry_run=False,
                )
            return AdapterResult(
                ok=True,
                message=f"midi: port available ({chosen})",
                dry_run=False,
                details={"midi_port": chosen, "available": list(names)},
            )
        except Exception as exc:
            return AdapterResult(ok=False, message=f"midi: test failed: {exc}", dry_run=False)

    def execute(self, command: AdapterCommand) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        bridge = self._get_bridge()
        action = command.action
        params = command.params
        try:
            if action in {"trigger_cue", "note_on"}:
                cue_id = str(params.get("catalog_cue_id") or params.get("cue_id") or "")
                if not cue_id and "note" in params:
                    # Direct note — log via temporary mapping path is not in SoundMidiBridge;
                    # keep protocol by using trigger only for mapped cues.
                    return AdapterResult(
                        ok=False,
                        message="midi: use catalog_cue_id / cue_id for note_on via SoundMidiBridge",
                        dry_run=dry_run,
                    )
                volume = float(params.get("volume", 0.8))
                bridge.trigger(cue_id, volume, dry_run=dry_run)
            elif action in {"stop_cue", "note_off"}:
                cue_id = str(params.get("catalog_cue_id") or params.get("cue_id") or "")
                bridge.stop(cue_id, dry_run=dry_run)
            else:
                return AdapterResult(ok=False, message=f"midi: unsupported action {action}", dry_run=dry_run)
        except Exception as exc:
            return AdapterResult(ok=False, message=f"midi: execute failed: {exc}", dry_run=dry_run)
        return AdapterResult(ok=True, message=f"midi: executed {action}", dry_run=dry_run)

    def stop(self, command: AdapterCommand | None = None) -> AdapterResult:
        if command and (command.params.get("catalog_cue_id") or command.params.get("cue_id")):
            return self.execute(
                AdapterCommand(action="stop_cue", params=dict(command.params)),
            )
        dry_run = self._resolve_dry_run()
        self._get_bridge().stop_all(dry_run=dry_run)
        return AdapterResult(ok=True, message="midi: stop_all", dry_run=dry_run)

    def emergency_stop(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        self._get_bridge().stop_all(dry_run=dry_run)
        return AdapterResult(ok=True, message="midi: emergency stop (stop_all)", dry_run=dry_run)

    def health_status(self) -> HealthStatus:
        return HealthStatus(
            status=AdapterHealth.OK if self._connected else AdapterHealth.DISCONNECTED,
            message="midi adapter",
            connected=self._connected,
            details={"dry_run": self._resolve_dry_run()},
        )
