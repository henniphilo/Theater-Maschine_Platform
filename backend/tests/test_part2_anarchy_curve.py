from app.services.part2_cue_density import cue_intervals_for_anarchy


def test_anarchy_curve_tightens_intervals() -> None:
    start = cue_intervals_for_anarchy(0.35)
    end = cue_intervals_for_anarchy(0.9)
    assert end["video"][0] < start["video"][0]
    assert end["sound"][1] < start["sound"][1]
