from dataclasses import dataclass


@dataclass
class TextAnalysis:
    tags: list[str]
    mood: str
    intensity: float


DEFAULT_MOOD = "neutral"


def analyze_text(text: str, topic: str = "") -> TextAnalysis:
    combined = f"{topic} {text}".lower()
    tags: list[str] = []
    mood_scores: dict[str, int] = {}

    keyword_tags = {
        "memory": ["memory", "erinnerung", "vergangen", "archive", "vergessen"],
        "body": ["body", "körper", "haut", "atmen", "hand", "herz"],
        "machine": ["machine", "maschine", "technik", "code", "algorithmus", "digital"],
        "fear": ["fear", "angst", "schrecken", "panik", "dunkel"],
        "silence": ["silence", "stille", "pause", "leer", "schweigen"],
    }
    mood_keywords = {
        "melancholisch": ["vielleicht", "verloren", "traurig", "wehmütig", "einsam", "störung"],
        "unheimlich": ["störung", "fremd", "schatten", "unbekannt", "kalt", "technisch"],
        "warm": ["nähe", "warm", "berührung", "herz", "menschlich", "haut"],
        "spannung": ["plötzlich", "alarm", "gefahr", "schnell"],
        "leer": ["nichts", "leer", "stille", "pause", "schweigen"],
    }

    for tag, keywords in keyword_tags.items():
        if any(kw in combined for kw in keywords):
            tags.append(tag)

    for mood, keywords in mood_keywords.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score:
            mood_scores[mood] = score

    mood = max(mood_scores, key=mood_scores.get) if mood_scores else DEFAULT_MOOD
    if not tags and mood != DEFAULT_MOOD:
        mood_to_tag = {
            "melancholisch": "memory",
            "warm": "body",
            "spannung": "fear",
            "leer": "silence",
            "unheimlich": "machine",
        }
        tags.append(mood_to_tag.get(mood, "memory"))

    if not tags:
        tags = ["memory"]

    intensity = _estimate_intensity(text)
    return TextAnalysis(tags=tags, mood=mood, intensity=intensity)


def _estimate_intensity(text: str) -> float:
    score = 0.35
    score += min(len(text) / 400, 0.25)
    score += text.count("!") * 0.08
    if text.isupper() and len(text) > 10:
        score += 0.15
    boosters = ["niemals", "immer", "explosion", "panik", "schrecken"]
    lower = text.lower()
    score += sum(0.06 for b in boosters if b in lower)
    return round(min(max(score, 0.0), 1.0), 2)
