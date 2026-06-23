from app.schemas.inszenierung import (
    AnarchyCurve,
    AnimalScene,
    CompositionMoment,
    CompositionPlan,
    SceneCorpus,
)
from app.services.inszenierung_validation import (
    anarchy_level_for_index,
    apply_anarchy_curve,
    excerpt_in_scene,
    overlap_for_anarchy,
    validate_composition,
)


def _corpus() -> SceneCorpus:
    scene = AnimalScene(
        id="scene-1",
        animal="Bär",
        title="Geld",
        source_text="da wir also gar kein Geld haben, müssen wir uns dem Produzenten zuwenden.",
    )
    return SceneCorpus(id="c-1", title="Test", scenes=[scene])


def test_excerpt_in_scene() -> None:
    scene = _corpus().scenes[0]
    assert excerpt_in_scene(scene, "gar kein Geld haben")
    assert not excerpt_in_scene(scene, "nicht im Text")


def test_anarchy_level_monotonic() -> None:
    curve = AnarchyCurve(start=0.2, end=0.9)
    levels = [anarchy_level_for_index(i, 5, curve) for i in range(5)]
    assert levels == sorted(levels)
    assert levels[0] == 0.2
    assert levels[-1] == 0.9


def test_apply_anarchy_curve_sets_overlap() -> None:
    moments = [
        CompositionMoment(id="m1", order=0, scene_id="scene-1", text_excerpt="gar kein Geld haben"),
        CompositionMoment(
            id="m2",
            order=1,
            scene_id="scene-1",
            text_excerpt="dem Produzenten zuwenden",
            anarchy_level=0.8,
        ),
    ]
    apply_anarchy_curve(moments, AnarchyCurve())
    assert moments[0].overlap_with_previous == 0.0
    assert moments[1].overlap_with_previous == overlap_for_anarchy(moments[1].anarchy_level)


def test_validate_composition_rejects_bad_excerpt() -> None:
    corpus = _corpus()
    plan = CompositionPlan(
        moments=[
            CompositionMoment(
                id="m1",
                order=0,
                scene_id="scene-1",
                text_excerpt="erfundener Text",
            )
        ]
    )
    try:
        validate_composition(plan, corpus)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "not found" in str(exc).lower() or "Excerpt" in str(exc)


def test_validate_avatar_video_requires_clip_or_id() -> None:
    corpus = _corpus()
    plan = CompositionPlan(
        moments=[
            CompositionMoment(
                id="m1",
                order=0,
                scene_id="scene-1",
                text_excerpt="gar kein Geld haben",
                speech_mode="avatar_video",
            )
        ]
    )
    try:
        validate_composition(plan, corpus)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "avatar" in str(exc).lower()

