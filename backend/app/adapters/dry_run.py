"""Dry-run adapter — logs intent, never sends to hardware. Default for new devices."""

from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import (
    AdapterCommand,
    AdapterHealth,
    AdapterResult,
    HealthStatus,
    OutputAdapter,
)

logger = logging.getLogger(__name__)


class DryRunAdapter(OutputAdapter):
    adapter_type = "dry_run"

    def __init__(self, *, device_id: str, name: str, configuration: dict[str, Any] | None = None) -> None:
        self.device_id = device_id
        self.name = name
        self.configuration = dict(configuration or {})
        self._connected = False

    def connect(self) -> AdapterResult:
        self._connected = True
        logger.info("dry_run.connect device_id=%s name=%s", self.device_id, self.name)
        return AdapterResult(ok=True, message="dry-run: connected (no hardware)", dry_run=True)

    def disconnect(self) -> AdapterResult:
        self._connected = False
        logger.info("dry_run.disconnect device_id=%s", self.device_id)
        return AdapterResult(ok=True, message="dry-run: disconnected", dry_run=True)

    def test_connection(self) -> AdapterResult:
        logger.info("dry_run.test_connection device_id=%s", self.device_id)
        return AdapterResult(
            ok=True,
            message="dry-run: connection test ok (no hardware probe)",
            dry_run=True,
            details={"device_id": self.device_id, "adapter_type": self.adapter_type},
        )

    def execute(self, command: AdapterCommand) -> AdapterResult:
        logger.info(
            "dry_run.execute device_id=%s action=%s params=%s",
            self.device_id,
            command.action,
            command.params,
        )
        return AdapterResult(
            ok=True,
            message=f"dry-run: would execute {command.action}",
            dry_run=True,
            details={"action": command.action, "params": dict(command.params)},
        )

    def stop(self, command: AdapterCommand | None = None) -> AdapterResult:
        action = command.action if command else "stop"
        logger.info("dry_run.stop device_id=%s action=%s", self.device_id, action)
        return AdapterResult(ok=True, message=f"dry-run: would stop ({action})", dry_run=True)

    def emergency_stop(self) -> AdapterResult:
        logger.info("dry_run.emergency_stop device_id=%s", self.device_id)
        return AdapterResult(ok=True, message="dry-run: would emergency_stop", dry_run=True)

    def health_status(self) -> HealthStatus:
        return HealthStatus(
            status=AdapterHealth.OK,
            message="dry-run adapter healthy",
            connected=self._connected,
            details={"device_id": self.device_id},
        )
