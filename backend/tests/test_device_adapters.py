from __future__ import annotations

from app.adapters import build_adapter
from app.adapters.base import AdapterCommand
from app.services.device_secrets import (
    pack_for_storage,
    redact_configuration,
    seal_configuration,
    unseal_configuration,
)


def test_redact_configuration_strips_sensitive_keys() -> None:
    redacted = redact_configuration(
        {"host": "10.1.2.3", "port": 3032, "notes": "eos", "password": "x"}
    )
    assert redacted == {"notes": "eos"}
    assert "host" not in redacted
    assert "password" not in redacted


def test_seal_roundtrip_plain() -> None:
    sealed = seal_configuration({"host": "127.0.0.1", "port": 7000})
    assert sealed.startswith("plain:")
    restored = unseal_configuration(sealed)
    assert restored == {"host": "127.0.0.1", "port": 7000}


def test_pack_for_storage_splits_public(monkeypatch) -> None:
    monkeypatch.setattr("app.services.device_secrets.settings.device_config_key", None)
    public, sealed = pack_for_storage({"host": "pixera.local", "notes": "a", "force_dry_run": True})
    assert public == {"notes": "a", "force_dry_run": True}
    assert "host" not in public
    restored = unseal_configuration(sealed)
    assert restored["host"] == "pixera.local"
    assert restored["notes"] == "a"


def test_dry_run_adapter_default_behaviour() -> None:
    adapter = build_adapter(
        adapter_type="dry_run",
        device_id="dev-1",
        name="Safe",
        configuration={"host": "should-not-matter"},
    )
    assert adapter.test_connection().ok is True
    assert adapter.test_connection().dry_run is True
    executed = adapter.execute(AdapterCommand(action="apply_cue", params={"clip_id": "x"}))
    assert executed.ok is True
    assert executed.dry_run is True
    assert adapter.emergency_stop().dry_run is True


def test_osc_adapter_test_connection_respects_dry_run(monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.osc.settings.osc_dry_run", True)
    adapter = build_adapter(
        adapter_type="osc",
        device_id="dev-osc",
        name="TD",
        configuration={"host": "127.0.0.1", "port": 7000},
    )
    result = adapter.test_connection()
    assert result.ok is True
    assert result.dry_run is True


def test_pixera_adapter_execute_apply_cue(monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.pixera.settings.osc_dry_run", True)
    calls: list[str] = []

    class FakeBridge:
        host = "127.0.0.1"
        port = 8990

        def apply_cue(self, name: str) -> None:
            calls.append(name)

    adapter = build_adapter(
        adapter_type="pixera",
        device_id="dev-px",
        name="Pixera",
        configuration={"host": "127.0.0.1", "port": 8990},
    )
    adapter._bridge = FakeBridge()  # type: ignore[attr-defined]
    result = adapter.execute(AdapterCommand(action="apply_cue", params={"pixera_cue_name": "KI_Adam.BK1"}))
    assert result.ok is True
    assert calls == ["KI_Adam.BK1"]


def test_eos_tcp_adapter_dry_run_test(monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.eos_tcp.settings.osc_dry_run", True)

    class FakeLighting:
        def connect_desk(self, dry_run: bool = False) -> None:
            assert dry_run is True

        def disconnect_desk(self, dry_run: bool = False) -> None:
            assert dry_run is True

        def blackout(self, dry_run: bool = False) -> None:
            assert dry_run is True

    adapter = build_adapter(
        adapter_type="eos_tcp",
        device_id="dev-eos",
        name="EOS",
        configuration={"host": "10.101.90.112", "port": 3032},
    )
    adapter._lighting = FakeLighting()  # type: ignore[attr-defined]
    result = adapter.test_connection()
    assert result.ok is True
    assert result.dry_run is True
    assert adapter.emergency_stop().ok is True
