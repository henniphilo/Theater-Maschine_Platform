from app.director.media.database import MediaDatabase
from app.director.media.selector import MediaSelector


def test_media_selector_returns_available_video() -> None:
    db = MediaDatabase()
    video_ids = {v.id for v in db.videos}
    selector = MediaSelector(db, history_size=3)

    first = selector.select_video(["clyde"], "neutral", 0.5)
    assert first is not None
    assert first.id in video_ids


def test_get_sound_by_tags_respects_intensity() -> None:
    db = MediaDatabase()
    sound = db.get_sound_by_tags(["glitch"], mood="spannung", intensity=0.9)
    assert sound is not None
    assert sound.id == "erinnerungsglitch"
