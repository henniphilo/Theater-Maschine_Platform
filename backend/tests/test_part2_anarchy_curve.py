from app.services.part2_cue_density import atmosphere_intervals_for_anarchy, cue_intervals_for_anarchy


def test_anarchy_curve_tightens_intervals() -> None:
    start = cue_intervals_for_anarchy(0.35)
    end = cue_intervals_for_anarchy(0.9)
    assert end["video"][0] < start["video"][0]
    assert end["sound"][1] < start["sound"][1]


def test_atmosphere_is_denser_than_keyword_video_early() -> None:
    keyword = cue_intervals_for_anarchy(0.2)["video"]
    atmosphere = atmosphere_intervals_for_anarchy(0.2)
    assert atmosphere[0] < keyword[0]
    assert atmosphere[1] < keyword[1]
