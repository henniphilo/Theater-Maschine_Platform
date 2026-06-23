from app.services.spoken_text import spoken_discussion_text

MEDIA_TURN = """**Sounds/Musik**
- low_drone_01 — «billiger in der Anschaffung» / Thema: Verwaltungskälte
- cash_register — «Ist das Geld denn das alles wert?» / Thema: Ökonomie

```json
{"sounds":["low_drone_01","cash_register"],"music":["m1"],"videos":["v1"],"lights":["l1"]}
```
"""


def test_spoken_discussion_text_strips_media_bullets() -> None:
    spoken = spoken_discussion_text(MEDIA_TURN)
    assert "low_drone" not in spoken
    assert "cash_register" not in spoken
    assert "```json" not in spoken
    assert "Medienpaket" in spoken or len(spoken) >= 20


def test_spoken_discussion_text_keeps_theme_discussion() -> None:
    raw = "Das Thema ist Kälte — «billiger in der Anschaffung». Stimmung: bürokratisch."
    assert spoken_discussion_text(raw) == raw


def test_spoken_discussion_text_keeps_intro_before_bullets() -> None:
    raw = "Wir schlagen folgendes Paket vor.\n\n- sound_a — «Zitat» / Thema: Test"
    spoken = spoken_discussion_text(raw)
    assert "Wir schlagen folgendes Paket vor" in spoken
    assert "sound_a" not in spoken
