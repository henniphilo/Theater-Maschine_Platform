import re
import uuid

from app.schemas.script import ScriptBeat, ScriptSpeaker

MIN_BEAT_LINES = 4
MAX_BEAT_CHARS = 1800
MAX_SCENE_TITLE_CHARS = 80

_SCENE_TITLE_PATTERN = re.compile(
    r"^(?:"
    r"szene\s[\dIVXLC]+[.:].*|"
    r"szene[.:].*|"
    r"akt\s[\dIVXLC]+[.:].*|"
    r"\d+\.\s*(?:szene|scene).*|"
    r"#+\s*.+"
    r")$",
    re.IGNORECASE,
)


def split_source_text(source_text: str) -> list[str]:
    text = source_text.strip()
    if not text:
        return []

    if re.search(r"^\s*---\s*$", text, re.MULTILINE):
        parts = [p.strip() for p in re.split(r"^\s*---\s*$", text, flags=re.MULTILINE)]
        return [p for p in parts if p]

    parts = [p.strip() for p in re.split(r"\n\s*\n+", text)]
    return [p for p in parts if p] or [text]


def split_sentences(text: str) -> list[str]:
    trimmed = text.strip()
    if not trimmed:
        return []
    parts = re.findall(r"[^.!?…]+[.!?…]+[\s]*", trimmed)
    if not parts:
        return [trimmed]
    joined = "".join(parts)
    tail = trimmed[len(joined) :].strip()
    sentences = [p.strip() for p in parts]
    if tail:
        sentences.append(tail)
    return sentences


def count_lines(text: str) -> int:
    return len([ln for ln in text.splitlines() if ln.strip()])


def is_section_long_enough(text: str) -> bool:
    if count_lines(text) >= MIN_BEAT_LINES:
        return True
    return len(split_sentences(text)) >= MIN_BEAT_LINES


def merge_short_chunks(chunks: list[str]) -> list[str]:
    if not chunks:
        return []

    merged: list[str] = []
    current = chunks[0]
    for chunk in chunks[1:]:
        combined = f"{current}\n\n{chunk}"
        if not is_section_long_enough(current) and len(combined) <= MAX_BEAT_CHARS:
            current = combined
        else:
            merged.append(current)
            current = chunk
    merged.append(current)

    if len(merged) >= 2 and not is_section_long_enough(merged[-1]):
        tail = merged.pop()
        candidate = f"{merged[-1]}\n\n{tail}"
        if len(candidate) <= MAX_BEAT_CHARS:
            merged[-1] = candidate
        else:
            merged.append(tail)

    return merged


def split_long_chunk(chunk: str) -> list[str]:
    if len(chunk) <= MAX_BEAT_CHARS:
        return [chunk]
    sentences = split_sentences(chunk)
    if len(sentences) <= 1:
        return [chunk[:MAX_BEAT_CHARS].rstrip()]
    groups: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        sentence_len = len(sentence)
        if current and current_len + sentence_len > MAX_BEAT_CHARS:
            groups.append(" ".join(current))
            current = [sentence]
            current_len = sentence_len
        else:
            current.append(sentence)
            current_len += sentence_len + 1
    if current:
        groups.append(" ".join(current))
    return groups or [chunk]


def default_speaker(order: int) -> ScriptSpeaker:
    if order % 2 == 0:
        return "AI_A"
    return "AI_B"


def extract_scene_title_and_body(text: str) -> tuple[str | None, str]:
    """Split an optional scene heading from the beat body."""
    trimmed = text.strip()
    if not trimmed:
        return None, trimmed

    lines = trimmed.splitlines()
    first = lines[0].strip()
    rest = "\n".join(lines[1:]).strip()

    if not first:
        return None, trimmed

    if _SCENE_TITLE_PATTERN.match(first):
        title = first.rstrip(":")
        return title, rest if rest else trimmed

    if rest and len(first) <= MAX_SCENE_TITLE_CHARS:
        if first.endswith(":"):
            return first.rstrip(":"), rest
        letters = [c for c in first if c.isalpha()]
        if letters and first.isupper() and len(first) <= 60:
            return first, rest
        if len(first.split()) <= 10 and not first.endswith((".", "!", "?")):
            second = lines[1].strip() if len(lines) > 1 else ""
            if second and (second[0].islower() or len(second) > len(first) * 2):
                return first, rest

    return None, trimmed


def beat_scene_label(beat: ScriptBeat) -> str:
    if beat.scene_title:
        return beat.scene_title
    return f"Abschnitt {beat.order + 1}"


def part1_scene_label(beat: ScriptBeat) -> str:
    if beat.scene_title:
        return beat.scene_title
    return "Gesamttext"


def dramaturgy_quote_excerpts(
    text: str,
    *,
    max_excerpts: int = 8,
    max_chars: int = 100,
) -> list[str]:
    sentences = [s.strip() for s in split_sentences(text) if len(s.strip()) >= 12]
    if not sentences:
        return []

    count = len(sentences)
    if count <= max_excerpts:
        indices = list(range(count))
    else:
        step = (count - 1) / (max_excerpts - 1)
        indices = [round(i * step) for i in range(max_excerpts)]

    excerpts: list[str] = []
    for index in dict.fromkeys(indices):
        excerpt = sentences[index]
        if len(excerpt) > max_chars:
            cut = excerpt[: max_chars - 1]
            last_space = cut.rfind(" ")
            excerpt = (cut[:last_space] if last_space >= max_chars // 2 else cut).strip() + "…"
        excerpts.append(excerpt)
        if len(excerpts) >= max_excerpts:
            break
    return excerpts


def build_beats_from_text(source_text: str) -> list[ScriptBeat]:
    chunks = merge_short_chunks(split_source_text(source_text))
    expanded: list[str] = []
    for chunk in chunks:
        expanded.extend(split_long_chunk(chunk))

    beats: list[ScriptBeat] = []
    for index, chunk in enumerate(expanded):
        scene_title, body = extract_scene_title_and_body(chunk)
        beats.append(
            ScriptBeat(
                id=str(uuid.uuid4()),
                order=index,
                text=body,
                scene_title=scene_title,
                speaker=default_speaker(index),
            )
        )
    return beats


def build_part1_whole_beat(source_text: str) -> list[ScriptBeat]:
    """Teil 1: ein Beat mit dem vollen Stücktext (kein Abschnitts-Split)."""
    trimmed = source_text.strip()
    if not trimmed:
        return []

    scene_title, body = extract_scene_title_and_body(trimmed)
    return [
        ScriptBeat(
            id=str(uuid.uuid4()),
            order=0,
            text=body,
            scene_title=scene_title,
            speaker=default_speaker(0),
        )
    ]
