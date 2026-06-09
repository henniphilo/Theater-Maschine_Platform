from app.director.media.database import MediaDatabase
from app.director.media.selector import MediaSelector


def test_media_selector_avoids_recent_ids() -> None:
    db = MediaDatabase()
    selector = MediaSelector(db, history_size=3)

    first = selector.select_video(["memory"], "melancholisch", 0.6)
    assert first is not None
    assert first.id == "memory_noise_03"

    second = selector.select_video(["memory"], "melancholisch", 0.6)
    assert second is not None
    assert second.id != first.id


def test_get_sound_by_tags_respects_intensity() -> None:
    db = MediaDatabase()
    sound = db.get_sound_by_tags(["fear", "angst"], mood="spannung", intensity=0.9)
    assert sound is not None
    assert sound.id == "fear_stinger_01"
