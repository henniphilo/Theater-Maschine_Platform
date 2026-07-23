from __future__ import annotations

import json


def _create_production(api_client, name: str = "Rule API Show") -> dict:
    resp = api_client.post("/api/v1/productions", json={"name": name})
    assert resp.status_code == 201
    return resp.json()


def test_api_rule_crud_evaluate_and_legacy(api_client, active_store) -> None:
    (active_store / "dramaturgy_rules.json").write_text(
        json.dumps(
            {
                "keyword_tags": {"memory": ["erinnerung"]},
                "mood_keywords": {},
                "intensity_boosters": [],
                "min_cue_interval_seconds": {"video": 5.0},
            }
        ),
        encoding="utf-8",
    )
    production = _create_production(api_client)

    created = api_client.post(
        "/api/v1/rules",
        json={
            "production_id": production["id"],
            "name": "Tag memory",
            "priority": 15,
            "cooldown_seconds": 5,
            "conditions": [{"type": "tag", "tag": "memory"}],
            "actions": [{"type": "select_random_by_tags", "tags": ["memory"]}],
        },
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["id"]
    assert created.json()["conditions"][0]["tag"] == "memory"

    bad = api_client.post(
        "/api/v1/rules",
        json={
            "production_id": production["id"],
            "name": "Bad",
            "conditions": [{"type": "text_contains"}],
            "actions": [{"type": "execute_cue", "cue_id": "x"}],
        },
    )
    assert bad.status_code == 422

    listed = api_client.get(f"/api/v1/rules?production_id={production['id']}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    evaluated = api_client.post(
        f"/api/v1/rules/evaluate?production_id={production['id']}",
        json={
            "tags": ["memory"],
            "available_cues": [
                {"id": "c1", "tags": ["memory"]},
                {"id": "c2", "tags": ["fear"]},
            ],
            "now_seconds": 0,
        },
    )
    assert evaluated.status_code == 200, evaluated.text
    body = evaluated.json()
    assert len(body["matches"]) == 1
    assert body["matches"][0]["planned_actions"][0]["cue_id"] == "c1"

    legacy = api_client.get("/api/v1/rules/legacy")
    assert legacy.status_code == 200
    assert isinstance(legacy.json(), list)
    assert len(legacy.json()) > 0

    patched = api_client.patch(
        f"/api/v1/rules/{rule_id}",
        json={"name": "Tag memory 2", "enabled": False},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Tag memory 2"
    assert patched.json()["enabled"] is False

    deleted = api_client.delete(f"/api/v1/rules/{rule_id}")
    assert deleted.status_code == 204

    missing = api_client.get(f"/api/v1/rules/{rule_id}")
    assert missing.status_code == 404


def test_api_rule_previous_cue_and_manual(api_client) -> None:
    production = _create_production(api_client, "Rule Manual Show")
    created = api_client.post(
        "/api/v1/rules",
        json={
            "production_id": production["id"],
            "name": "After blackout",
            "conditions": [
                {"type": "previous_cue", "cue_id": "blackout"},
                {"type": "manual", "activation_key": "operator-go"},
            ],
            "actions": [
                {"type": "execute_delayed", "cue_id": "fade-in", "delay_seconds": 1.5},
            ],
        },
    )
    assert created.status_code == 201, created.text

    miss = api_client.post(
        f"/api/v1/rules/evaluate?production_id={production['id']}",
        json={"previous_cue_id": "blackout", "manual_keys": []},
    )
    assert miss.status_code == 200
    assert miss.json()["matches"] == []

    hit = api_client.post(
        f"/api/v1/rules/evaluate?production_id={production['id']}",
        json={
            "previous_cue_id": "blackout",
            "manual_keys": ["operator-go"],
        },
    )
    assert hit.status_code == 200
    assert len(hit.json()["matches"]) == 1
    assert hit.json()["matches"][0]["planned_actions"][0]["delay_seconds"] == 1.5
