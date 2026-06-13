from unittest.mock import MagicMock, patch

from app.director.technik_hold import TechnikHoldManager, TechnikHoldState


@patch("app.director.technik_hold.settings")
def test_technik_hold_start_and_stop(mock_settings: MagicMock) -> None:
    mock_settings.osc_dry_run = True
    mock_settings.technik_hold_interval_seconds = 0.05

    pipeline = MagicMock()
    manager = TechnikHoldManager(pipeline)

    state = TechnikHoldState(send_visual=True, clip_id="kuh", send_sound=True, sound_cue_id="dummy_drone")
    manager.start(state)
    assert manager.active is True

    manager.stop(send_visual=True, send_sound=True, send_light=False)
    assert manager.active is False
    pipeline.touchdesigner.stop_clip.assert_called_once()
    pipeline.sound.execute.assert_called()
