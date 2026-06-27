from app.schemas.discussion import DiscussionTurn
from app.schemas.media_mentions import MediaMention
from app.schemas.part1_selection import MediaSelectionLists, MIN_FINAL_SOUNDS
from app.services.part1_selection_builder import build_selection_from_discussion


def test_build_selection_from_mentions() -> None:
    turns = [
        DiscussionTurn(
            speaker="anthropic",
            content="spoken",
            media_mentions=[
                MediaMention(medium="sound", media_id="maschinen_grundader", keyword="Bärenklau"),
                MediaMention(medium="video", media_id="macbook", keyword="Keller"),
            ],
        )
    ]
    lists = build_selection_from_discussion(turns, "Der Bärenklau wächst im Keller.")
    assert "maschinen_grundader" in lists.sounds
    assert "macbook" in lists.videos
    assert len(lists.sounds) >= MIN_FINAL_SOUNDS


def test_build_selection_json_fallback() -> None:
    turns = [
        DiscussionTurn(
            speaker="anthropic",
            content="spoken",
            media_mentions=[],
        )
    ]
    fallback = MediaSelectionLists(
        sounds=[f"s{i}" for i in range(6)],
        music=["m1"],
        videos=[f"v{i}" for i in range(6)],
        lights=[f"l{i}" for i in range(6)],
    )
    lists = build_selection_from_discussion(turns, "Text", json_fallback=fallback)
    assert len(lists.sounds) == 6
    assert lists.music == ["m1"]
