from app.director.outputs.eos_light import eos_chan_full, eos_key_out, expand_channels, parse_eos_chan_address


def test_expand_channel_ranges_and_lists() -> None:
    assert expand_channels(["11-19"]) == list(range(11, 20))
    assert expand_channels(["92", "94", "96", "98"]) == [92, 94, 96, 98]
    assert expand_channels(["6"]) == [6]
    assert expand_channels(["40-46", "48"]) == list(range(40, 47)) + [48]


def test_eos_chan_full_format() -> None:
    address, args = eos_chan_full(6)
    assert address == "/eos/chan/6/full"
    assert args == []


def test_parse_eos_chan_address() -> None:
    assert parse_eos_chan_address("/eos/chan/6/full") == 6
    assert parse_eos_chan_address("/eos/chan/6=full") is None

    address, args = eos_key_out()
    assert address == "/eos/key/out"
    assert args == []
