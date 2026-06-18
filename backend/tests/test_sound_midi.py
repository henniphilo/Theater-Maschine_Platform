from unittest.mock import MagicMock, patch

from app.director.cues.cue_models import SoundAction, SoundCue
from app.director.outputs.sound import SoundBridge
from app.director.outputs.sound_midi import SoundMidiBridge, load_sound_midi_map, resolve_midi_output_port


def test_load_sound_midi_map_reads_cues() -> None:
    mapping = load_sound_midi_map()
    assert mapping["maschinen_grundader"].note == 36
    assert mapping["maschinen_grundader_fade_in"].note == 52


def test_resolve_midi_port_accepts_german_iac_name() -> None:
    available = ["IAC-Treiber Bus 1"]
    assert resolve_midi_output_port("IAC Driver Bus 1", available) == "IAC-Treiber Bus 1"
    assert resolve_midi_output_port("iac-treiber bus 1", available) == "IAC-Treiber Bus 1"
    assert resolve_midi_output_port(None, available) == "IAC-Treiber Bus 1"


@patch("app.director.outputs.sound_midi.settings")
def test_sound_midi_trigger_sends_note_on(mock_settings: MagicMock) -> None:
    mock_settings.osc_dry_run = False
    mock_settings.sound_midi_port = "Test Port"
    mock_settings.sound_midi_channel = 1
    mock_settings.sound_midi_default_velocity = 100
    mock_settings.sound_midi_auto_note = False

    bridge = SoundMidiBridge()
    bridge._map = load_sound_midi_map()
    mock_port = MagicMock()

    with patch.object(bridge, "_open_port", return_value=mock_port):
        bridge.trigger("maschinen_grundader", 0.5, dry_run=False)

    mock_port.send.assert_called_once()
    message = mock_port.send.call_args[0][0]
    assert message.type == "note_on"
    assert message.note == 36
    assert message.channel == 0
    assert message.velocity == 63


@patch("app.director.outputs.sound.settings")
@patch("app.director.outputs.sound.get_sound_midi_bridge")
def test_sound_bridge_uses_midi_for_trigger(
    mock_get_midi: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_settings.sound_output = "midi"
    mock_settings.sound_osc_mirror = False
    mock_settings.osc_dry_run = True
    midi = MagicMock()
    mock_get_midi.return_value = midi

    bridge = SoundBridge()
    bridge.execute(SoundCue(action=SoundAction.TRIGGER_CUE, cue_id="maschinen_grundader", volume=0.8), dry_run=False)

    midi.trigger.assert_called_once_with("maschinen_grundader", 0.8, dry_run=False)


@patch("app.director.outputs.sound.settings")
@patch("app.director.outputs.sound.get_sound_midi_bridge")
def test_sound_bridge_stop_sends_note_off(
    mock_get_midi: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_settings.sound_output = "midi"
    mock_settings.sound_osc_mirror = False
    mock_settings.osc_dry_run = True
    midi = MagicMock()
    mock_get_midi.return_value = midi

    bridge = SoundBridge()
    bridge.execute(SoundCue(action=SoundAction.STOP_CUE, cue_id="maschinen_grundader"), dry_run=False)

    midi.stop.assert_called_once_with("maschinen_grundader", dry_run=False)
