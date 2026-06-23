from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_TEXT = (
    "Vielleicht ist Erinnerung nur eine technische Störung.\n"
    "Ein zweiter Gedanke dazu.\nDritter Satz im Block.\nVierter Satz im Block.\n\n"
    "---\n\n"
    "Der Körper erinnert sich anders als der Geist.\n"
    "Noch ein Satz.\nUnd ein weiterer.\nAbschluss hier."
)


def test_create_script_whole_text_beat() -> None:
    res = client.post(
        "/api/v1/scripts",
        json={"title": "Teststück", "source_text": SAMPLE_TEXT},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "Teststück"
    assert len(body["beats"]) == 1
    assert SAMPLE_TEXT.split("---")[0].strip() in body["beats"][0]["text"]
    assert body["status"] == "draft"


def test_get_and_patch_beat_speaker() -> None:
    created = client.post(
        "/api/v1/scripts",
        json={"title": "Patch", "source_text": "Ein Abschnitt."},
    ).json()
    beat_id = created["beats"][0]["id"]
    patched = client.patch(
        f"/api/v1/scripts/{created['id']}/beats/{beat_id}",
        json={"speaker": "narrator"},
    )
    assert patched.status_code == 200
    assert patched.json()["beats"][0]["speaker"] == "narrator"
