"""Light inventory / blocked-channel policy for Burgtheater Technik settings."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.director.outputs.eos_light import expand_channels
from app.main import app
from app.services import light_inventory_admin as lia
from app.services.light_inventory_admin import (
    LightChannelPolicy,
    LightChannelPolicyPatchRequest,
)

client = TestClient(app)


def test_default_blocked_channels_include_burgtheater(tmp_path: Path) -> None:
    """Fresh policy model (no file) seeds Burgtheater channels 11/19/22."""
    lia.reset_light_policy_for_tests(persist_path=tmp_path / "missing_policy.json")
    policy = lia.LightChannelPolicy()
    assert set(policy.blocked_channels) >= {11, 19, 22}


def test_expand_channels_respecting_policy_filters_blocked(tmp_path: Path) -> None:
    lia.reset_light_policy_for_tests(persist_path=tmp_path / "light_channel_policy.json")
    lia.save_policy(LightChannelPolicy(blocked_channels=[11, 19, 22]))
    expanded = expand_channels(["11-19", "22-26"])
    assert 11 in expanded and 19 in expanded and 22 in expanded
    filtered = lia.expand_channels_respecting_policy(["11-19", "22-26"])
    assert 11 not in filtered
    assert 19 not in filtered
    assert 22 not in filtered
    assert 12 in filtered
    assert 23 in filtered


def test_disable_inventory_group_blocks_its_channels(tmp_path: Path, monkeypatch) -> None:
    lia.reset_light_policy_for_tests(persist_path=tmp_path / "light_channel_policy.json")
    inv = {
        "source": "test",
        "venue": "test",
        "groups": [
            {"id": "demo_group", "channels": ["501", "502"], "fixtures": [], "location": "Test"},
        ],
    }
    inv_path = tmp_path / "light_inventory.json"
    inv_path.write_text(__import__("json").dumps(inv), encoding="utf-8")
    monkeypatch.setattr(lia, "inventory_path", lambda: inv_path)
    lia.save_policy(LightChannelPolicy(blocked_channels=[], disabled_inventory_group_ids=[]))
    lia.set_inventory_group_enabled("demo_group", False)
    blocked = lia.effective_blocked_channels()
    assert 501 in blocked and 502 in blocked


def test_light_inventory_api_roundtrip(tmp_path: Path, monkeypatch) -> None:
    lia.reset_light_policy_for_tests(persist_path=tmp_path / "light_channel_policy.json")
    inv = {"source": "test", "venue": "Burgtheater", "groups": []}
    inv_path = tmp_path / "light_inventory.json"
    inv_path.write_text(__import__("json").dumps(inv), encoding="utf-8")
    monkeypatch.setattr(lia, "inventory_path", lambda: inv_path)
    lia.save_policy(LightChannelPolicy(blocked_channels=[11, 19, 22]))

    res = client.get("/api/v1/media/light-inventory")
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body["blocked_channels"]) >= {11, 19, 22}

    res = client.patch(
        "/api/v1/media/light-inventory/policy",
        json={"blocked_channels": [11, 19, 22, 99]},
    )
    assert res.status_code == 200
    assert 99 in res.json()["blocked_channels"]

    res = client.post(
        "/api/v1/media/light-inventory/groups",
        json={"id": "extra_spot", "channels": ["901", "902"], "location": "Bühne"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["id"] == "extra_spot"

    res = client.patch(
        "/api/v1/media/light-inventory/groups/extra_spot",
        json={"enabled": False},
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is False

    res = client.delete("/api/v1/media/light-inventory/groups/extra_spot")
    assert res.status_code == 200


def test_patch_policy_helper(tmp_path: Path) -> None:
    lia.reset_light_policy_for_tests(persist_path=tmp_path / "light_channel_policy.json")
    next_policy = lia.patch_policy(
        LightChannelPolicyPatchRequest(blocked_channels=[11], notes="test")
    )
    assert next_policy.blocked_channels == [11]
    assert next_policy.notes == "test"
