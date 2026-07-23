"""EOS TCP adapter — delegates to LightTcpSession / LightingBridge session APIs."""

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
from app.director.outputs.light_tcp import get_light_tcp_session
from app.director.outputs.lighting import LightingBridge

logger = logging.getLogger(__name__)


class EosTcpAdapter(OutputAdapter):
    adapter_type = "eos_tcp"

    def __init__(
        self,
        *,
        device_id: str,
        name: str,
        configuration: dict[str, Any] | None = None,
        enabled: bool = True,
        lighting: LightingBridge | None = None,
    ) -> None:
        self.device_id = device_id
        self.name = name
        self.configuration = dict(configuration or {})
        self.enabled = enabled
        self._lighting = lighting
        self._connected = False

    def _resolve_dry_run(self) -> bool:
        if coerce_bool(self.configuration.get("force_dry_run"), False):
            return True
        if not self.enabled:
            return True
        return bool(settings.osc_dry_run)

    def _host_port(self) -> tuple[str, int]:
        host = self.configuration.get("host") or settings.light_tcp_host
        port_raw = self.configuration.get("port")
        port = int(port_raw) if port_raw is not None else int(settings.light_tcp_port)
        return str(host), port

    def _get_lighting(self) -> LightingBridge:
        if self._lighting is None:
            host, port = self._host_port()
            self._lighting = LightingBridge(host=host, port=port)
        return self._lighting

    def connect(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        try:
            self._get_lighting().connect_desk(dry_run=dry_run)
            self._connected = True
            return AdapterResult(
                ok=True,
                message="eos_tcp: desk session open" + (" (dry-run)" if dry_run else ""),
                dry_run=dry_run,
                details={"host": self._host_port()[0], "port": self._host_port()[1]},
            )
        except Exception as exc:
            return AdapterResult(ok=False, message=f"eos_tcp: connect failed: {exc}", dry_run=dry_run)

    def disconnect(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        try:
            self._get_lighting().disconnect_desk(dry_run=dry_run)
            self._connected = False
            return AdapterResult(ok=True, message="eos_tcp: disconnected", dry_run=dry_run)
        except Exception as exc:
            return AdapterResult(ok=False, message=f"eos_tcp: disconnect failed: {exc}", dry_run=dry_run)

    def test_connection(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        host, port = self._host_port()
        if not host or port <= 0:
            return AdapterResult(ok=False, message="eos_tcp: host/port missing", dry_run=dry_run)

        if dry_run:
            # Exercise the same connect path as LightDeskTestManager, but dry-run only.
            try:
                self._get_lighting().connect_desk(dry_run=True)
                self._get_lighting().disconnect_desk(dry_run=True)
            except Exception as exc:
                return AdapterResult(
                    ok=False,
                    message=f"eos_tcp: dry-run test failed: {exc}",
                    dry_run=True,
                )
            return AdapterResult(
                ok=True,
                message="eos_tcp: dry-run connection test ok (no TCP)",
                dry_run=True,
                details={"host": host, "port": port},
            )

        try:
            self._get_lighting().connect_desk(dry_run=False)
            connected = get_light_tcp_session().connected
            self._connected = connected
            if not connected:
                return AdapterResult(
                    ok=False,
                    message="eos_tcp: TCP session not connected",
                    dry_run=False,
                    details={"host": host, "port": port},
                )
            return AdapterResult(
                ok=True,
                message="eos_tcp: TCP session connected",
                dry_run=False,
                details={"host": host, "port": port},
            )
        except Exception as exc:
            return AdapterResult(ok=False, message=f"eos_tcp: test failed: {exc}", dry_run=False)

    def execute(self, command: AdapterCommand) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        from app.director.cues.cue_models import LightCue

        action = command.action
        params = command.params
        try:
            lighting = self._get_lighting()
            if action in {"set_scene", "send_scene"}:
                cue_kwargs: dict[str, Any] = {
                    "scene_id": str(params.get("scene_id") or "") or None,
                }
                if params.get("fade_time") is not None:
                    cue_kwargs["fade_time"] = float(params["fade_time"])
                if params.get("intensity") is not None:
                    cue_kwargs["intensity"] = float(params["intensity"])
                cue = LightCue(**cue_kwargs)
                lighting.execute(cue, dry_run=dry_run)
            elif action in {"fade_blackout", "blackout"}:
                lighting.blackout(dry_run=dry_run)
            else:
                return AdapterResult(
                    ok=False,
                    message=f"eos_tcp: unsupported action {action}",
                    dry_run=dry_run,
                )
        except Exception as exc:
            return AdapterResult(ok=False, message=f"eos_tcp: execute failed: {exc}", dry_run=dry_run)
        return AdapterResult(ok=True, message=f"eos_tcp: executed {action}", dry_run=dry_run)

    def stop(self, command: AdapterCommand | None = None) -> AdapterResult:
        return self.execute(AdapterCommand(action="fade_blackout", params={}))

    def emergency_stop(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        try:
            self._get_lighting().blackout(dry_run=dry_run)
            return AdapterResult(ok=True, message="eos_tcp: emergency blackout", dry_run=dry_run)
        except Exception as exc:
            return AdapterResult(ok=False, message=f"eos_tcp: emergency_stop failed: {exc}", dry_run=dry_run)

    def health_status(self) -> HealthStatus:
        session = get_light_tcp_session()
        connected = bool(session.connected) or self._connected
        dry_run = self._resolve_dry_run()
        host, port = self._host_port()
        return HealthStatus(
            status=AdapterHealth.OK if connected or dry_run else AdapterHealth.DISCONNECTED,
            message="eos_tcp adapter",
            connected=connected,
            details={"host": host, "port": port, "dry_run": dry_run},
        )
