import io
import shutil
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.director.cues.cue_models import DramaturgyDecision, LightCue, SoundCue, VisualCue, VisualAction
from app.main import app
from app.schemas.script import DiscussionTurn, ProductionScript, ScriptBeat
from app.services.performance_bundle_service import PerformanceBundleService
from app.services.script_store import ScriptStore

client = TestClient(app)


def _seed_data_dir(target: Path) -> None:
    repo_data = Path(__file__).resolve().parents[2] / "data"
    if not repo_data.exists():
        repo_data = Path(__file__).resolve().parents[1] / "data"
    for name in ("media.json", "light_scenes.json", "light_inventory.json", "dramaturgy_rules.json"):
        shutil.copy(repo_data / name, target / name)


def _decision() -> DramaturgyDecision:
    return DramaturgyDecision(
        visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde"),
        sound=SoundCue(cue_id="maschinen_grundader"),
        light=LightCue(scene_id="blendung_zuschauerraum"),
        reason="Test",
        mood="neutral",
        intensity=0.5,
    )


def _ready_script(tmp_path: Path) -> ProductionScript:
    _seed_data_dir(tmp_path)
    store = ScriptStore(data_dir=tmp_path)
    beat = ScriptBeat(
        id="beat-1",
        order=0,
        text="Erinnerung ist eine Störung im System.",
        speaker="AI_A",
        dramaturgy=_decision(),
        discussion_turns=[DiscussionTurn(speaker="openai", content="Kurzer Dramaturg-Kommentar.")],
    )
    script = ProductionScript(
        id="script-test",
        title="Teststück",
        source_text=beat.text,
        beats=[beat],
        status="ready",
    )
    return store.save(script)


def _fake_audio(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(b"fake-audio")
    return path


@pytest.fixture
def bundle_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PerformanceBundleService:
    _seed_data_dir(tmp_path)
    store = ScriptStore(data_dir=tmp_path)
    tts = MagicMock()
    tts.is_available.return_value = True
    tts.resolve_provider.return_value = "edge"

    async def fake_synth(
        text: str,
        speaker: str,
        *,
        profile: str | None = None,
    ) -> Path:
        safe = speaker.replace("/", "_")
        return _fake_audio(tmp_path, f"{safe}-{len(text)}.mp3")

    tts.synthesize = AsyncMock(side_effect=fake_synth)
    return PerformanceBundleService(store=store, tts=tts, data_dir=tmp_path)


def test_render_and_zip_roundtrip(bundle_service: PerformanceBundleService, tmp_path: Path) -> None:
    import asyncio

    script = _ready_script(tmp_path)
    manifest = asyncio.run(bundle_service.render_and_save(script.id))
    performance_entries = [e for e in manifest.audio_files if e.kind == "performance"]
    assert len(performance_entries) == 1
    assert performance_entries[0].turn_index == 0
    assert performance_entries[0].speaker == "AI_A"
    zip_bytes, filename = bundle_service.build_zip_bytes(script.id)
    assert filename.endswith(".tmshow.zip")
    assert zipfile.is_zipfile(io.BytesIO(zip_bytes))

    imported = bundle_service.import_zip(zip_bytes)
    assert imported.title == "Teststück"
    assert imported.has_rendered_audio is True
    assert imported.status == "ready"
    assert len(imported.beats) == 1
    assert (bundle_service.bundle_dir(imported.id) / "manifest.json").exists()


def test_import_via_api(bundle_service: PerformanceBundleService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from app.api.routes import script as script_routes

    script = _ready_script(tmp_path)
    monkeypatch.setattr(script_routes, "_performance", bundle_service)
    asyncio.run(bundle_service.render_and_save(script.id))
    zip_bytes, _ = bundle_service.build_zip_bytes(script.id)

    res = client.post(
        "/api/v1/scripts/performance/import",
        files={"file": ("test.tmshow.zip", zip_bytes, "application/zip")},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["has_rendered_audio"] is True
    assert body["status"] == "ready"


def test_audio_endpoint(bundle_service: PerformanceBundleService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from app.api.routes import script as script_routes

    script = _ready_script(tmp_path)
    store = ScriptStore(data_dir=tmp_path)
    monkeypatch.setattr(script_routes, "_store", store)
    monkeypatch.setattr(script_routes, "_performance", bundle_service)
    asyncio.run(bundle_service.render_and_save(script.id))

    res = client.get(f"/api/v1/scripts/{script.id}/performance/audio/beat-1/discussion-0")
    assert res.status_code == 200
    assert res.content == b"fake-audio"

    res_perf = client.get(f"/api/v1/scripts/{script.id}/performance/audio/beat-1/performance-0")
    assert res_perf.status_code == 200
    assert res_perf.content == b"fake-audio"
