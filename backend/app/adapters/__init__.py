"""Adapter factory — build OutputAdapter instances for Device rows."""

from __future__ import annotations

from typing import Any

from app.adapters.base import OutputAdapter
from app.adapters.dry_run import DryRunAdapter
from app.adapters.eos_tcp import EosTcpAdapter
from app.adapters.midi import MidiAdapter
from app.adapters.osc import OscAdapter
from app.adapters.pixera import PixeraAdapter
from app.models.device import ADAPTER_TYPES, AdapterType, Device
from app.services.device_secrets import unpack_from_storage


class UnknownAdapterTypeError(ValueError):
    pass


def build_adapter_for_device(device: Device) -> OutputAdapter:
    config = unpack_from_storage(
        configuration=device.configuration,
        configuration_sealed=device.configuration_sealed,
    )
    return build_adapter(
        adapter_type=device.adapter_type,
        device_id=device.id,
        name=device.name,
        configuration=config,
        enabled=device.enabled,
    )


def build_adapter(
    *,
    adapter_type: str,
    device_id: str,
    name: str,
    configuration: dict[str, Any] | None = None,
    enabled: bool = True,
) -> OutputAdapter:
    if adapter_type not in ADAPTER_TYPES:
        raise UnknownAdapterTypeError(f"unknown adapter_type: {adapter_type}")

    config = dict(configuration or {})
    if adapter_type == AdapterType.DRY_RUN.value:
        return DryRunAdapter(device_id=device_id, name=name, configuration=config)
    if adapter_type == AdapterType.OSC.value:
        return OscAdapter(
            device_id=device_id,
            name=name,
            configuration=config,
            enabled=enabled,
        )
    if adapter_type == AdapterType.MIDI.value:
        return MidiAdapter(
            device_id=device_id,
            name=name,
            configuration=config,
            enabled=enabled,
        )
    if adapter_type == AdapterType.PIXERA.value:
        return PixeraAdapter(
            device_id=device_id,
            name=name,
            configuration=config,
            enabled=enabled,
        )
    if adapter_type == AdapterType.EOS_TCP.value:
        return EosTcpAdapter(
            device_id=device_id,
            name=name,
            configuration=config,
            enabled=enabled,
        )
    raise UnknownAdapterTypeError(f"unknown adapter_type: {adapter_type}")
