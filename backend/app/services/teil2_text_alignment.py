"""Align Avatar CSV text blocks to performance script sentence indices."""

from __future__ import annotations

import re
import unicodedata

from app.schemas.avatar_speech import AvatarSpeechCue
from app.schemas.inszenierung import AvatarSpeechLayer, AvatarTextSegment
from app.services.avatar_duration import layer_duration_ms
from app.services.avatar_speech_catalog import normalize_avatar_text
from app.services.inszenierung_validation import normalize_whitespace
from app.services.teil2_projector_assignment import assign_projectors_for_layers, build_avatar_visual_cue
from app.services.text_split import sentence_char_ranges, sentence_index_at_offset

_UNICODE_BREAK_CHARS = frozenset(
    {
        "\u00a0",  # NBSP (Numbers)
        "\u2028",  # line separator (Numbers «Zeilenumbruch»)
        "\u2029",  # paragraph separator
        "\u200b",  # zero-width space
        "\ufeff",  # BOM
    }
)


def _is_break_char(char: str) -> bool:
    if char in "\r\n\t":
        return True
    if char in _UNICODE_BREAK_CHARS:
        return True
    return unicodedata.category(char) == "Zs"


def _normalize_key(text: str) -> str:
    cleaned = normalize_whitespace(normalize_avatar_text(text))
    normalized = unicodedata.normalize("NFKD", cleaned.lower())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _build_normalized_map(script_text: str) -> tuple[str, list[int]]:
    """Return normalized script and index map norm_pos -> original_pos."""
    norm_chars: list[str] = []
    index_map: list[int] = []
    last_space = False
    for index, char in enumerate(script_text):
        if _is_break_char(char):
            if not last_space:
                norm_chars.append(" ")
                index_map.append(index)
                last_space = True
            continue
        if char == " ":
            if not last_space:
                norm_chars.append(" ")
                index_map.append(index)
                last_space = True
            continue
        last_space = False
        decomposed = unicodedata.normalize("NFKD", char)
        for piece in decomposed:
            if not unicodedata.combining(piece):
                norm_chars.append(piece.lower())
                index_map.append(index)
    return "".join(norm_chars).strip(), index_map


def _find_line_anchor_offset(script_text: str, cue_text: str) -> int | None:
    """Match short CSV snippets that are a full script line (e.g. «Ja,»)."""
    stripped = cue_text.strip()
    if not stripped:
        return None
    needle = _normalize_key(stripped)
    for line in script_text.splitlines():
        if _normalize_key(line) == needle:
            return script_text.find(line)
    return None


def find_text_offset(script_text: str, cue_text: str) -> int | None:
    line_offset = _find_line_anchor_offset(script_text, cue_text)
    if line_offset is not None:
        return line_offset
    needle = _normalize_key(cue_text)
    if len(needle) < 3:
        return None
    haystack, index_map = _build_normalized_map(script_text)
    pos = haystack.find(needle)
    if pos >= 0 and len(needle) < 12 and haystack.count(needle) != 1:
        pos = -1
    if pos < 0:
        first_line = needle.split(" ", 8)[0]
        if len(first_line) >= 8:
            pos = haystack.find(first_line)
    if pos < 0:
        tokens = [t for t in re.findall(r"[a-zäöüß]{5,}", needle) if len(t) >= 5]
        if len(tokens) >= 3:
            probe = " ".join(tokens[:4])
            pos = haystack.find(probe)
    if pos < 0 or pos >= len(index_map):
        return None
    return index_map[pos]


def _layers_from_cues(cues: list[AvatarSpeechCue]) -> list[AvatarSpeechLayer]:
    return [
        AvatarSpeechLayer(
            avatar_speech_id=cue.id,
            avatar=cue.avatar,
            video_clip_id=cue.video_clip_id,
        )
        for cue in cues
    ]


def group_cues_into_segments(cues: list[AvatarSpeechCue]) -> list[list[AvatarSpeechCue]]:
    groups: list[list[AvatarSpeechCue]] = []
    current: list[AvatarSpeechCue] = []
    current_key: str | None = None
    for cue in cues:
        key = _normalize_key(cue.text)
        if current and key == current_key:
            current.append(cue)
            continue
        current = [cue]
        groups.append(current)
        current_key = key
    return groups


def align_avatar_csv_to_script(
    script_text: str,
    cues: list[AvatarSpeechCue],
    *,
    anarchy_level: float = 0.2,
) -> tuple[list[AvatarTextSegment], list[str]]:
    ranges = sentence_char_ranges(script_text)
    warnings: list[str] = []
    segments: list[AvatarTextSegment] = []
    used_projectors: set[str] = set()

    for group in group_cues_into_segments(cues):
        cue_text = group[0].text
        offset = find_text_offset(script_text, cue_text)
        if offset is None:
            for cue in group:
                warnings.append(f"{cue.id}: Text nicht im Aufführungstext gefunden")
            continue

        start_index = sentence_index_at_offset(ranges, offset)
        end_offset = offset + max(20, len(normalize_whitespace(cue_text)) - 1)
        end_index = sentence_index_at_offset(ranges, min(end_offset, len(script_text) - 1))

        layers = assign_projectors_for_layers(
            _layers_from_cues(group),
            anarchy_level=anarchy_level,
            used=used_projectors,
        )
        enriched_layers: list[AvatarSpeechLayer] = []
        for layer_index, layer in enumerate(layers):
            cue = group[layer_index]
            visual = build_avatar_visual_cue(
                layer,
                anarchy_level=anarchy_level,
                duration_ms=layer_duration_ms(cue),
            )
            enriched_layers.append(layer.model_copy(update={"visual_cue": visual}))

        segments.append(
            AvatarTextSegment(
                csv_cue_ids=[c.id for c in group],
                text_excerpt=cue_text.strip(),
                char_offset=offset,
                start_sentence_index=start_index,
                end_sentence_index=max(start_index, end_index),
                avatar_layers=enriched_layers,
            )
        )

    return segments, warnings
