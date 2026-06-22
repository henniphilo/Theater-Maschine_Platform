from unittest.mock import MagicMock, patch

from app.director.cues.cue_models import LightCue
from app.director.media.database import LightScene
from app.director.outputs.lighting import LightingBridge


@patch("app.director.outputs.lighting.settings")
@patch("app.director.outputs.lighting.get_light_tcp_session")
def test_lighting_opens_tcp_then_sends_eos_chan_full(
    mock_tcp_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_settings.light_output = "tcp"
    mock_settings.light_osc_mirror = False
    mock_settings.osc_dry_run = False
    mock_settings.light_tcp_host = "10.101.90.112"
    mock_settings.light_tcp_port = 3032

    tcp = MagicMock()
    mock_tcp_session.return_value = tcp
    scene = LightScene(
        id="seitenlicht_hart",
        description="test",
        channels=["91-94"],
    )
    bridge = LightingBridge(media_db=MagicMock(light_scenes=[scene]))

    bridge.execute(LightCue(scene_id="seitenlicht_hart", fade_time=4.0), dry_run=False)

    tcp.open_session.assert_called_once_with(dry_run=False)
    assert tcp.send_osc.call_count == 5
    tcp.send_osc.assert_any_call("/eos/key/out", [], dry_run=False)
    tcp.send_osc.assert_any_call("/eos/chan/91/full", [], dry_run=False)


@patch("app.director.outputs.lighting.settings")
@patch("app.director.outputs.lighting.get_light_tcp_session")
def test_lighting_scene_at_partial_intensity(
    mock_tcp_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_settings.light_output = "tcp"
    mock_settings.light_osc_mirror = False
    mock_settings.osc_dry_run = False
    mock_settings.light_tcp_host = "10.101.90.112"
    mock_settings.light_tcp_port = 3032

    tcp = MagicMock()
    tcp.connected = True
    mock_tcp_session.return_value = tcp
    scene = LightScene(
        id="seitenlicht_hart",
        description="test",
        channels=["91", "92"],
    )
    bridge = LightingBridge(media_db=MagicMock(light_scenes=[scene]))

    bridge.execute(LightCue(scene_id="seitenlicht_hart", fade_time=4.0, intensity=0.6), dry_run=False)

    tcp.send_osc.assert_any_call("/eos/key/out", [], dry_run=False)
    tcp.send_osc.assert_any_call("/eos/chan/91/at", [60.0], dry_run=False)
    tcp.send_osc.assert_any_call("/eos/chan/92/at", [60.0], dry_run=False)


@patch("app.director.outputs.lighting.settings")
@patch("app.director.outputs.lighting.get_light_tcp_session")
def test_lighting_blackout_sends_eos_key_out(
    mock_tcp_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_settings.light_output = "tcp"
    mock_settings.light_osc_mirror = False
    mock_settings.osc_dry_run = False
    mock_settings.light_tcp_host = "10.101.90.112"
    mock_settings.light_tcp_port = 3032

    tcp = MagicMock()
    tcp.connected = True
    mock_tcp_session.return_value = tcp
    bridge = LightingBridge(media_db=MagicMock(light_scenes=[]))

    bridge.blackout(dry_run=False)

    tcp.send_osc.assert_called_once_with("/eos/key/out", [], dry_run=False)
    tcp.close_session.assert_called_once()


@patch("app.director.outputs.lighting.settings")
@patch("app.director.outputs.lighting.get_light_tcp_session")
def test_lighting_apply_channel_skips_when_tcp_unreachable(
    mock_tcp_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    from app.director.outputs.light_tcp import LightDeskConnectionError

    mock_settings.light_output = "tcp"
    mock_settings.light_osc_mirror = False
    mock_settings.osc_dry_run = False
    tcp = MagicMock()
    tcp.open_session.side_effect = LightDeskConnectionError("timed out")
    mock_tcp_session.return_value = tcp
    bridge = LightingBridge(media_db=MagicMock(light_scenes=[]))

    bridge.apply_channel(6, dry_run=False)

    tcp.send_osc.assert_not_called()
