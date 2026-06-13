from unittest.mock import MagicMock, patch

from app.director.outputs.touchdesigner import TouchDesignerBridge


@patch("app.director.outputs.touchdesigner.udp_client.SimpleUDPClient")
def test_play_clip_sends_osc(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    bridge = TouchDesignerBridge(host="127.0.0.1", port=7000, dry_run=False)
    bridge.play_clip("kuh", 0.8, 4.0)
    mock_client.send_message.assert_called_once_with(
        "/visual/play_clip",
        ["kuh", 0.8, 4.0],
    )


def test_dry_run_does_not_create_client() -> None:
    bridge = TouchDesignerBridge(dry_run=True)
    assert bridge._client is None
    bridge.play_clip("kuh")
    bridge.blackout()
