
from app.schemas.inszenierung import AnimalScene, SceneCorpus
from app.services.teil2_scene_filter import filter_teil2_scenes, is_baerenklau_scene


def test_is_baerenklau_scene() -> None:
    assert is_baerenklau_scene(AnimalScene(id="1", animal="Bärenklau", source_text="x"))
    assert not is_baerenklau_scene(AnimalScene(id="2", animal="Delphin", source_text="x"))


def test_filter_teil2_scenes() -> None:
    corpus = SceneCorpus(
        id="c1",
        title="Test",
        scenes=[
            AnimalScene(id="bk", animal="Bärenklau", source_text="bk"),
            AnimalScene(id="del", animal="Delphin", source_text="del"),
        ],
    )
    filtered = filter_teil2_scenes(corpus)
    assert [s.id for s in filtered] == ["del"]
