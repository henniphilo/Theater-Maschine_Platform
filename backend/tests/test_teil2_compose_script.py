"""Integration tests for compose-script flow."""

from app.schemas.inszenierung import AnarchyCurve, Gesamtkonzept, SceneCorpus
from app.services.inszenierung_komposition_service import InszenierungKompositionService
from app.services.teil2_script_service import load_canonical_script_text, SCRIPT_SOURCE


def test_compose_plan_from_script_corpus():
    corpus = SceneCorpus(
        id="test-corpus",
        title="AVATAR Text Delfin bis Wolf",
        script_source=SCRIPT_SOURCE,
        script_text=load_canonical_script_text(),
        gesamtkonzept=Gesamtkonzept(
            thesis="Geld als Maske",
            anarchy_curve=AnarchyCurve(start=0.35, end=1.0),
        ),
    )
    service = InszenierungKompositionService()
    plan = service.compose_plan(corpus)
    assert len(plan.moments) >= 33
    assert all(m.speech_mode == "avatar_video" for m in plan.moments)
    assert all(m.dramaturgy is not None for m in plan.moments)
    assert plan.moments[-1].anarchy_level >= plan.moments[0].anarchy_level
