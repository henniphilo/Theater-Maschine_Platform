import pytest
from unittest.mock import MagicMock, patch

from app.director.cues.cue_models import DramaturgyDecision, VisualAction, VisualCue, VisualOutputAssignment
from app.director.outputs.osc_commands import build_osc_commands, send_osc_commands
from app.director.outputs.pixera import PixeraBridge
from app.director.media.video_inventory import (
    load_video_cues_from_csv,
    parse_osc_befehlliste,
    resolve_osc_befehlliste_path,
    resolve_video_overview_paths,
)
from app.services.video_cue_catalog import get_video_cue_catalog_service


def test_video_catalog_loads_pixera_clips() -> None:
    catalog = get_video_cue_catalog_service().load()
    assert len(catalog.projectors) == 4
    assert {p.id for p in catalog.projectors} == {"rz21", "adam", "eva", "led"}
    clip_ids = {c.id for c in catalog.clips}
    assert "clyde" in clip_ids
    assert "gehirn" in clip_ids
    assert "nicolas" in clip_ids
    assert len(catalog.clips) >= 26


def test_osc_befehlliste_matches_video_overview() -> None:
    from tests.repo_paths import repo_data_dir

    data_dir = repo_data_dir()
    clips_path, projectors_path = resolve_video_overview_paths(data_dir)
    osc_path = resolve_osc_befehlliste_path(data_dir)
    if not clips_path or not projectors_path or not osc_path:
        pytest.skip("media/video CSV fixtures not available in CI")

    catalog = load_video_cues_from_csv(clips_path, projectors_path)
    clip_names = {c.pixera_name for c in catalog.clips}
    prefix_by_id = {p.id: p.pixera_prefix for p in catalog.projectors}

    for prefix, clip_name in parse_osc_befehlliste(osc_path):
        assert clip_name in clip_names, f"Clip {clip_name!r} fehlt in Video Übersicht.csv"
        if prefix == "KI_KI_RZ21":
            prefix = prefix_by_id["rz21"]
        service = get_video_cue_catalog_service()
        output_id = next(k for k, v in prefix_by_id.items() if v == prefix)
        clip_id = next(c.id for c in catalog.clips if c.pixera_name == clip_name)
        assert service.pixera_cue_name(output_id, clip_id) == f"{prefix}.{clip_name}"


def test_pixera_cue_name_mapping() -> None:
    service = get_video_cue_catalog_service()
    assert service.pixera_cue_name("rz21", "clyde") == "KI_RZ21.Clyde"
    assert service.pixera_cue_name("led", "strand") == "KI_LED.Strand"


def test_multi_projector_osc_commands() -> None:
    decision = DramaturgyDecision(
        visual=VisualCue(
            action=VisualAction.PLAY_CLIP,
            clip_id="clyde",
            outputs=[
                VisualOutputAssignment(output_id="rz21", clip_id="clyde"),
                VisualOutputAssignment(output_id="adam", clip_id="black"),
            ],
        )
    )
    commands = build_osc_commands(decision, dry_run=True)
    pixera_cmds = [c for c in commands if c.bridge == "pixera"]
    assert len(pixera_cmds) == 2
    assert pixera_cmds[0].args == ["KI_RZ21.Clyde"]
    assert pixera_cmds[1].args == ["KI_Adam.Black"]


@patch("app.director.outputs.pixera.udp_client.SimpleUDPClient")
def test_pixera_bridge_sends_apply(mock_client_cls: MagicMock) -> None:
    client = MagicMock()
    mock_client_cls.return_value = client
    bridge = PixeraBridge(dry_run=False)
    bridge.apply_cue("KI_RZ21.Clyde")
    client.send_message.assert_called_once_with("/pixera/args/cue/apply", ["KI_RZ21.Clyde"])


def test_send_osc_commands_routes_pixera() -> None:
    pixera = MagicMock()
    commands = build_osc_commands(
        DramaturgyDecision(visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde")),
        dry_run=True,
    )
    assert commands
    assert commands[0].bridge == "pixera"
    sent = send_osc_commands(
        commands,
        {
            "pixera": pixera,
            "touchdesigner": MagicMock(),
            "sound": MagicMock(),
            "lighting": MagicMock(),
        },
    )
    assert sent == commands
    pixera.apply_cue.assert_called_once()
