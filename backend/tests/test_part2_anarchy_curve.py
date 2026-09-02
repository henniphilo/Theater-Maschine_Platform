from app.services.part2_cue_density import (
    atmosphere_intervals_for_anarchy,
    cue_intervals_for_anarchy,
    light_fade_seconds,
    light_min_interval_seconds,
)


def test_anarchy_curve_tightens_intervals() -> None:
    start = cue_intervals_for_anarchy(0.35)
    end = cue_intervals_for_anarchy(0.9)
    assert end["video"][0] < start["video"][0]
    assert end["sound"][1] < start["sound"][1]
    assert end["light"][0] < start["light"][0]
    assert start["sound"][0] <= 8.0
    assert end["sound"][0] < start["sound"][0]
    assert end["sound"][0] <= 3.5


def test_atmosphere_is_denser_than_keyword_video_early() -> None:
    keyword = cue_intervals_for_anarchy(0.2)["video"]
    atmosphere = atmosphere_intervals_for_anarchy(0.2)
    assert atmosphere[0] < keyword[0]
    assert atmosphere[1] < keyword[1]


def test_light_min_interval_blocks_rapid_fire_but_allows_frequent_changes() -> None:
    early = light_min_interval_seconds(0.3, base_min=8.0)
    late = light_min_interval_seconds(0.9, base_min=8.0)
    assert early >= 6.0
    assert early <= 10.0
    assert late < early
    assert late <= 4.0


def test_light_fade_longer_early_than_in_chaos() -> None:
    assert light_fade_seconds(4.0, 0.2) > light_fade_seconds(4.0, 0.9)
