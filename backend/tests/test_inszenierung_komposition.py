from app.schemas.inszenierung import Gesamtkonzept, SceneCorpus
from app.services.inszenierung_komposition_service import InszenierungKompositionService
from app.services.teil2_script_service import SCRIPT_SOURCE, load_canonical_script_text


def test_compose_plan_uses_avatar_video_for_all_beats() -> None:
    service = InszenierungKompositionService()
    corpus = SceneCorpus(
        id="c1",
        title="AVATAR Text Delfin bis Wolf",
        script_source=SCRIPT_SOURCE,
        script_text=load_canonical_script_text(),
        gesamtkonzept=Gesamtkonzept(thesis="Geld"),
    )
    plan = service.compose_plan(corpus)
    assert len(plan.moments) >= 30
    assert all(moment.speech_mode == "avatar_video" for moment in plan.moments)
    assert plan.moments[0].avatar_layers


def test_compose_plan_includes_dramaturgy_per_beat() -> None:
    service = InszenierungKompositionService()
    corpus = SceneCorpus(
        id="c2",
        title="AVATAR Text Delfin bis Wolf",
        script_source=SCRIPT_SOURCE,
        script_text=load_canonical_script_text(),
    )
    plan = service.compose_plan(corpus)
    assert all(moment.dramaturgy is not None for moment in plan.moments)
