from app.services.catalog_media_resolver import get_catalog_media_matcher
from app.services.media_mentions import (
    MediaAllowlist,
    build_media_alias_index,
    build_spoken_playback_with_mentions,
    decision_for_media_mention,
    extract_media_mentions,
    keywords_for_performance,
)
from app.schemas.media_mentions import MediaMention


def test_extract_bullet_mention_with_quote() -> None:
    allowlist = MediaAllowlist(
        sounds=frozenset({"maschinen_grundader", "kaefigecho"}),
        music=frozenset(),
        videos=frozenset(),
        lights=frozenset(),
    )
    text = "- maschinen_grundader — «Erinnerung als Störung» / Thema: Kälte"
    mentions = extract_media_mentions(text, allowlist)
    assert len(mentions) == 1
    assert mentions[0].media_id == "maschinen_grundader"
    assert mentions[0].keyword == "Erinnerung als Störung"
    assert mentions[0].char_offset == 0


def test_keywords_for_performance_matches_scene() -> None:
    mentions = [
        MediaMention(medium="sound", media_id="kaefigecho", keyword="Maschine", char_offset=0),
        MediaMention(medium="video", media_id="clyde", keyword="Fuchs", char_offset=10),
    ]
    matched = keywords_for_performance(mentions, "Die Maschine arbeitet leise.")
    assert len(matched) == 1
    assert matched[0].media_id == "kaefigecho"


def test_extract_backtick_bullet_mention() -> None:
    allowlist = MediaAllowlist(
        sounds=frozenset({"maschinen_grundader"}),
        music=frozenset(),
        videos=frozenset({"clyde"}),
        lights=frozenset(),
    )
    text = "- `clyde` — «Fuchs» / Thema: Tier\n- `maschinen_grundader`: Grundton"
    mentions = extract_media_mentions(text, allowlist)
    assert len(mentions) == 2
    ids = {m.media_id for m in mentions}
    assert ids == {"clyde", "maschinen_grundader"}


def test_mood_keyword_spoken_without_catalog_ids() -> None:
    allowlist = MediaAllowlist(
        sounds=frozenset({c.id for c in get_catalog_media_matcher().sound_play if c.action == "play"}),
        music=frozenset(),
        videos=frozenset({v["id"] for v in get_catalog_media_matcher().videos}),
        lights=frozenset(),
    )
    raw = "«Bärenklau» — maschinelles Summen, Grundader-Ton (Sound)."
    spoken, mentions = build_spoken_playback_with_mentions(raw, allowlist, {})
    assert "maschinen_grundader" not in spoken
    assert "Beim Stichwort" in spoken
    assert len(mentions) >= 1
    assert mentions[0].keyword == "Bärenklau"


def test_extract_mood_keyword_mentions() -> None:
    allowlist = MediaAllowlist(
        sounds=frozenset({c.id for c in get_catalog_media_matcher().sound_play if c.action == "play"}),
        music=frozenset(),
        videos=frozenset(),
        lights=frozenset(),
    )
    text = "«Keller» — Sound: knurrend, unheimlich; Video: kalte Flächen"
    from app.services.media_mentions import extract_mood_keyword_mentions

    mentions = extract_mood_keyword_mentions(text, allowlist)
    assert len(mentions) >= 1
    assert mentions[0].keyword == "Keller"


def test_build_spoken_playback_aligns_offsets() -> None:
    allowlist = MediaAllowlist(
        sounds=frozenset({"maschinen_grundader"}),
        music=frozenset(),
        videos=frozenset({"clyde", "macbook"}),
        lights=frozenset(),
    )
    raw = (
        "Medienpaket:\n"
        "- `clyde` — «Fuchs»\n"
        "- `macbook` — Bürokratie\n"
        "```json\n{\"sounds\": []}\n```"
    )
    spoken, mentions = build_spoken_playback_with_mentions(raw, allowlist, {})
    assert "clyde" in spoken
    assert "macbook" in spoken
    assert len(mentions) == 2
    assert all(m.char_offset < len(spoken) for m in mentions)


def test_resolve_invented_growl_in_mentions() -> None:
    allowlist = MediaAllowlist(
        sounds=frozenset({c.id for c in get_catalog_media_matcher().sound_play if c.action == "play"}),
        music=frozenset(),
        videos=frozenset(),
        lights=frozenset(),
    )
    alias_index = build_media_alias_index(
        {
            "sounds": [
                {
                    "id": s.id,
                    "tags": s.tags,
                    "moods": s.moods,
                    "description": s.description,
                }
                for s in get_catalog_media_matcher().sound_play
            ],
            "videos": [],
            "lights": [],
        }
    )
    text = "- `animal_growl`: knurrend, tierisch im Ökonomischen"
    mentions = extract_media_mentions(text, allowlist, alias_index)
    assert len(mentions) == 1
    assert mentions[0].media_id == "tierstimme_verzerrt"


def test_decision_for_sound_mention() -> None:
    decision = decision_for_media_mention(
        MediaMention(medium="sound", media_id="maschinen_grundader", char_offset=0)
    )
    assert decision.sound is not None
    assert decision.sound.cue_id == "maschinen_grundader"
