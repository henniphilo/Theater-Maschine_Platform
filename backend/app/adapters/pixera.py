"""Pixera adapter — delegates to PixeraBridge (existing /pixera/args/cue/apply)."""

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
from app.director.outputs.pixera import PixeraBridge

logger = logging.getLogger(__name__)


class PixeraAdapter(OutputAdapter):
    adapter_type = "pixera"

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
        self._bridge: PixeraBridge | None = None
        self._connected = False

    def _resolve_dry_run(self) -> bool:
        if coerce_bool(self.configuration.get("force_dry_run"), False):
            return True
        if not self.enabled:
            return True
        return bool(settings.osc_dry_run)

    def _host_port(self) -> tuple[str, int]:
        host = (
            self.configuration.get("host")
            or settings.pixera_osc_host
            or settings.osc_host
        )
        port_raw = self.configuration.get("port")
        if port_raw is not None:
            port = int(port_raw)
        else:
            port = int(settings.pixera_osc_port or settings.osc_port)
        return str(host), port

    def _get_bridge(self) -> PixeraBridge:
        if self._bridge is None:
            host, port = self._host_port()
            self._bridge = PixeraBridge(host=host, port=port, dry_run=self._resolve_dry_run())
        return self._bridge

    def connect(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        bridge = self._get_bridge()
        self._connected = True
        return AdapterResult(
            ok=True,
            message="pixera: ready" + (" (dry-run)" if dry_run else ""),
            dry_run=dry_run,
            details={"host": bridge.host, "port": bridge.port},
        )

    def disconnect(self) -> AdapterResult:
        self._bridge = None
        self._connected = False
        return AdapterResult(ok=True, message="pixera: disconnected", dry_run=self._resolve_dry_run())

    def test_connection(self) -> AdapterResult:
        dry_run = self._resolve_dry_run()
        host, port = self._host_port()
        if not host or port <= 0:
            return AdapterResult(ok=False, message="pixera: host/port missing", dry_run=dry_run)
        bridge = self._get_bridge()
        logger.info(
            "pixera.test_connection device_id=%s host=%s port=%s dry_run=%s",
            self.device_id,
            bridge.host,
            bridge.port,
            dry_run,
        )
        return AdapterResult(
            ok=True,
            message="pixera: configuration valid"
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
            if action in {"apply_cue", "play_clip", "trigger_cue"}:
                cue_name = str(
                    params.get("pixera_cue_name")
                    or params.get("clip_id")
                    or params.get("cue_id")
                    or ""
                )
                if not cue_name:
                    return AdapterResult(ok=False, message="pixera: cue name required", dry_run=dry_run)
                bridge.apply_cue(cue_name)
            else:
                return AdapterResult(
                    ok=False,
                    message=f"pixera: unsupported action {action}",
                    dry_run=dry_run,
                )
        except Exception as exc:
            return AdapterResult(ok=False, message=f"pixera: execute failed: {exc}", dry_run=dry_run)
        return AdapterResult(ok=True, message=f"pixera: executed {action}", dry_run=dry_run)

    def stop(self, command: AdapterCommand | None = None) -> AdapterResult:
        # PixeraBridge has no stop API in current codebase — dry-run report only.
        dry_run = self._resolve_dry_run()
        return AdapterResult(
            ok=True,
            message="pixera: stop not mapped (no PixeraBridge.stop); no command sent",
            dry_run=dry_run,
        )

    def emergency_stop(self) -> AdapterResult:
        return self.stop()

    def health_status(self) -> HealthStatus:
        host, port = self._host_port()
        dry_run = self._resolve_dry_run()
        return HealthStatus(
            status=AdapterHealth.OK if self._connected or dry_run else AdapterHealth.DISCONNECTED,
            message="pixera adapter",
            connected=self._connected,
            details={"host": host, "port": port, "dry_run": dry_run},
        )
