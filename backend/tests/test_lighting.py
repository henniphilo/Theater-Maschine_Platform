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
        id="panolatte_rechts",
        description="test",
        channels=["92", "94", "96", "98"],
    )
    bridge = LightingBridge(media_db=MagicMock(light_scenes=[scene]))

    bridge.execute(LightCue(scene_id="panolatte_rechts", fade_time=4.0), dry_run=False)

    tcp.open_session.assert_called_once_with(dry_run=False)
    assert tcp.send_osc.call_count == 4
    tcp.send_osc.assert_any_call("/eos/chan/92/full", [], dry_run=False)


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
