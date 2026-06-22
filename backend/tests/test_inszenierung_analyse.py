from app.schemas.inszenierung import AnarchyCurve
from app.services.inszenierung_validation import anarchy_level_for_index


def test_anarchy_curve_endpoints() -> None:
    curve = AnarchyCurve(start=0.15, end=0.95)
    assert anarchy_level_for_index(0, 4, curve) == 0.15
    assert anarchy_level_for_index(3, 4, curve) == 0.95
