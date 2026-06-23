from app.schemas.inszenierung import CompositionMoment
from app.services.inszenierung_komposition_service import InszenierungKompositionService


def test_apply_speech_fields_prefers_avatar_for_low_anarchy() -> None:
    service = InszenierungKompositionService()
    moment = CompositionMoment(
        id="m1",
        order=0,
        scene_id="s1",
        text_excerpt="die Kurse steigen rasant ich springe vor Freude in die Luft",
        anarchy_level=0.25,
    )
    service._apply_speech_fields(moment, None, 0)
    assert moment.speech_mode == "avatar_video"
    assert moment.avatar_speech_id == "DEL3"


def test_apply_speech_fields_uses_tts_when_no_match() -> None:
    service = InszenierungKompositionService()
    moment = CompositionMoment(
        id="m2",
        order=1,
        scene_id="s1",
        text_excerpt="xyz abc qqq einzigartig ohne treffer",
        anarchy_level=0.25,
    )
    service._apply_speech_fields(moment, None, 1)
    assert moment.speech_mode == "tts"
    assert moment.avatar_speech_id is None
