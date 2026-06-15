from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision, VisualAction, VisualCue, VisualOutputAssignment
from app.director.outputs.osc_commands import build_osc_commands, send_osc_commands
from app.director.outputs.pixera import PixeraBridge
from app.services.video_cue_catalog import get_video_cue_catalog_service


def test_video_catalog_loads_pixera_clips() -> None:
    catalog = get_video_cue_catalog_service().load()
    assert len(catalog.projectors) == 4
    assert {p.id for p in catalog.projectors} == {"rz21", "adam", "eva", "led"}
    assert any(c.id == "clyde" for c in catalog.clips)


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
