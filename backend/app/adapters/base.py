"""OutputAdapter interface and shared result types.

Adapters wrap existing director bridges (OSC / MIDI / Pixera / EOS TCP).
They must not invent new hardware command addresses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class AdapterHealth(StrEnum):
    UNKNOWN = "unknown"
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class AdapterCommand:
    """Abstract command passed to execute/stop — bridge-specific payload in ``params``."""

    action: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterResult:
    ok: bool
    message: str
    dry_run: bool = True
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HealthStatus:
    status: AdapterHealth
    message: str
    connected: bool = False
    details: dict[str, Any] = field(default_factory=dict)


class OutputAdapter(ABC):
    """Protocol communication for one device type."""

    adapter_type: str

    @abstractmethod
    def connect(self) -> AdapterResult:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> AdapterResult:
        raise NotImplementedError

    @abstractmethod
    def test_connection(self) -> AdapterResult:
        raise NotImplementedError

    @abstractmethod
    def execute(self, command: AdapterCommand) -> AdapterResult:
        raise NotImplementedError

    @abstractmethod
    def stop(self, command: AdapterCommand | None = None) -> AdapterResult:
        raise NotImplementedError

    @abstractmethod
    def emergency_stop(self) -> AdapterResult:
        raise NotImplementedError

    @abstractmethod
    def health_status(self) -> HealthStatus:
        raise NotImplementedError


def coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


DryRunMode = Literal["always", "settings", "never"]
