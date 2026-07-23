"""OSC adapter — delegates to TouchDesignerBridge (existing OSC addresses)."""

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
from app.director.outputs.touchdesigner import TouchDesignerBridge

logger = logging.getLogger(__name__)


class OscAdapter(OutputAdapter):
    adapter_type = "osc"

    def __init__(
        self,
        *,
        device_id: str,
        name: str,
        configuration: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> None:
        self.device_id = device_id
        self.name = name
        self.configuration = dict(configuration or {})
        self.enabled = enabled
        self._bridge: TouchDesignerBridge | None = None
        self._connected = False

    def _resolve_dry_run(self) -> bool:
        if coerce_bool(self.configuration.get("force_dry_run"), False):
            return True
        if not self.enabled:
            return True
        return bool(settings.osc_dry_run)

    def _host_port(self) -> tuple[str, int]:
        host = self.configuration.get("host") or settings.osc_host
        port_raw = self.configuration.get("port")
        port = int(port_raw) if port_raw is not None else int(settings.osc_port)
        return str(host), port

    def _get_bridge(self) -> TouchDesignerBridge:
        if self._bridge is None:
            host, port = self._host_port()
            self._bridge = TouchDesignerBridge(host=host, port=port, dry_run=self._resolve_dry_run())
        return self._bridge

    def connect(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        bridge = self._get_bridge()
        self._connected = True
        return AdapterResult(
            ok=True,
            message="osc: ready" + (" (dry-run)" if dry_run else ""),
            dry_run=dry_run,
            details={"host": bridge.host, "port": bridge.port},
        )

    def disconnect(self) -> AdapterResult:
        self._bridge = None
        self._connected = False
        return AdapterResult(ok=True, message="osc: disconnected", dry_run=self._resolve_dry_run())

    def test_connection(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        host, port = self._host_port()
        if not host or port <= 0:
            return AdapterResult(
                ok=False,
                message="osc: host/port missing or invalid",
                dry_run=dry_run,
            )
        # UDP has no handshake — validate config and instantiate client path.
        bridge = self._get_bridge()
        logger.info(
            "osc.test_connection device_id=%s host=%s port=%s dry_run=%s",
            self.device_id,
            bridge.host,
            bridge.port,
            dry_run,
        )
        return AdapterResult(
            ok=True,
            message="osc: configuration valid"
            + (" (dry-run, no UDP send)" if dry_run else " (UDP client ready)"),
            dry_run=dry_run,
            details={"host": bridge.host, "port": bridge.port},
        )

    def execute(self, command: AdapterCommand) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        bridge = self._get_bridge()
        action = command.action
        params = command.params
        try:
            if action == "play_clip":
                bridge.play_clip(
                    str(params.get("clip_id", "")),
                    opacity=float(params.get("opacity", 0.8)),
                    fade_time=float(params.get("fade_time", 4.0)),
                )
            elif action == "stop_clip":
                bridge.stop_clip()
            elif action == "set_opacity":
                bridge.set_opacity(float(params.get("opacity", 0.0)))
            elif action == "fade":
                bridge.fade(float(params.get("fade_time", 4.0)))
            elif action == "blackout":
                bridge.blackout()
            elif action == "send":
                address = str(params.get("address", ""))
                args = list(params.get("args") or [])
                if not address.startswith("/"):
                    return AdapterResult(ok=False, message="osc: address must start with /", dry_run=dry_run)
                bridge.send_message(address, *args)
            else:
                return AdapterResult(ok=False, message=f"osc: unsupported action {action}", dry_run=dry_run)
        except Exception as exc:
            return AdapterResult(ok=False, message=f"osc: execute failed: {exc}", dry_run=dry_run)
        return AdapterResult(ok=True, message=f"osc: executed {action}", dry_run=dry_run)

    def stop(self, command: AdapterCommand | None = None) -> AdapterResult:
        return self.execute(AdapterCommand(action="stop_clip", params={}))

    def emergency_stop(self) -> AdapterResult:
        return self.execute(AdapterCommand(action="blackout", params={}))

    def health_status(self) -> HealthStatus:
        dry_run = self._resolve_dry_run()
        host, port = self._host_port()
        return HealthStatus(
            status=AdapterHealth.OK if self._connected or dry_run else AdapterHealth.DISCONNECTED,
            message="osc adapter",
            connected=self._connected,
            details={"host": host, "port": port, "dry_run": dry_run},
        )
