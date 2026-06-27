"""Fester Skriptablauf AVATAR Text Delfin bis Wolf + CSV-Timeline."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.schemas.avatar_speech import AvatarSpeechCue
from app.schemas.inszenierung import (
    AnarchyCurve,
    AvatarSpeechLayer,
    CompositionMoment,
    CompositionPlan,
)
from app.services.avatar_duration import (
    layer_duration_ms,
    resolve_avatar_beat_duration_ms,
)
from app.services.avatar_speech_catalog import (
    get_avatar_speech_catalog_service,
    normalize_avatar_text,
    resolve_avatar_csv_path,
)
from app.services.inszenierung_validation import (
    apply_anarchy_curve,
    ensure_moment_ids,
    normalize_whitespace,
    overlap_for_anarchy,
)
from app.services.teil2_projector_assignment import (
    assign_projectors_for_layers,
    build_avatar_visual_cue,
    projector_mode_for_anarchy,
)

SCRIPT_SOURCE = "avatar_delfin_wolf"
SCRIPT_TXT_NAME = "AVATAR Text Delfin bis Wolf.txt"
SCRIPT_SCENE_ID = "avatar-delfin-wolf"


def _repo_roots() -> list[Path]:
    module_root = Path(__file__).resolve()
    return [module_root.parents[2], module_root.parents[3], Path.cwd()]


def resolve_script_txt_path() -> Path | None:
    for root in _repo_roots():
        candidate = root / "Stücktext" / SCRIPT_TXT_NAME
        if candidate.is_file():
            return candidate
    return None


def load_canonical_script_text() -> str:
    path = resolve_script_txt_path()
    if path is None:
        raise FileNotFoundError(f"Skriptdatei nicht gefunden: Stücktext/{SCRIPT_TXT_NAME}")
    return path.read_text(encoding="utf-8")


@dataclass
class ScriptBeatPreview:
    order: int
    text: str
    avatar_ids: list[str]
    avatars: list[str]
    is_chorus: bool


@dataclass
class ScriptBeatGroup:
    text: str
    cues: list[AvatarSpeechCue]


def group_catalog_cues_into_beats(cues: list[AvatarSpeechCue]) -> list[ScriptBeatGroup]:
    """Group consecutive CSV rows with identical normalized text into chorus beats."""
    groups: list[ScriptBeatGroup] = []
    current: ScriptBeatGroup | None = None
    current_key: str | None = None

    for cue in cues:
        key = normalize_avatar_text(cue.text)
        if current is not None and key == current_key:
            current.cues.append(cue)
            continue
        current = ScriptBeatGroup(text=cue.text, cues=[cue])
        groups.append(current)
        current_key = key
    return groups


def validate_cues_against_script(
    cues: list[AvatarSpeechCue],
    script_text: str,
) -> list[str]:
    """Return validation warnings for CSV texts not found in canonical script."""
    hay = normalize_whitespace(script_text)
    warnings: list[str] = []
    for cue in cues:
        needle = normalize_whitespace(normalize_avatar_text(cue.text))
        if len(needle) < 12:
            continue
        if needle not in hay:
            snippet = needle[:60] + ("…" if len(needle) > 60 else "")
            warnings.append(f"{cue.id}: Text nicht im Skript gefunden ({snippet})")
    return warnings


def estimate_duration_ms(text: str) -> int:
    chars = len(text)
    return max(4000, min(18000, 3500 + chars * 45))


def build_beat_previews(cues: list[AvatarSpeechCue] | None = None) -> list[ScriptBeatPreview]:
    catalog = get_avatar_speech_catalog_service().load()
    cue_list = cues if cues is not None else catalog.cues
    previews: list[ScriptBeatPreview] = []
    for index, group in enumerate(group_catalog_cues_into_beats(cue_list)):
        previews.append(
            ScriptBeatPreview(
                order=index,
                text=group.text,
                avatar_ids=[c.id for c in group.cues],
                avatars=[c.avatar for c in group.cues],
                is_chorus=len(group.cues) > 1,
            )
        )
    return previews


def _layers_from_cues(cues: list[AvatarSpeechCue]) -> list[AvatarSpeechLayer]:
    return [
        AvatarSpeechLayer(
            avatar_speech_id=cue.id,
            avatar=cue.avatar,
            video_clip_id=cue.video_clip_id,
        )
        for cue in cues
    ]


def build_timeline_from_csv(
    *,
    anarchy_curve: AnarchyCurve | None = None,
    script_text: str | None = None,
    strict_validation: bool = False,
    cues: list[AvatarSpeechCue] | None = None,
) -> CompositionPlan:
    curve = anarchy_curve or AnarchyCurve()
    script = script_text or load_canonical_script_text()
    cue_list = cues if cues is not None else get_avatar_speech_catalog_service().load().cues
    warnings = validate_cues_against_script(cue_list, script)
    if strict_validation and warnings:
        raise ValueError("; ".join(warnings[:3]))

    groups = group_catalog_cues_into_beats(cue_list)
    cue_by_id = {c.id: c for c in cue_list}
    moments: list[CompositionMoment] = []
    for index, group in enumerate(groups):
        layers = assign_projectors_for_layers(
            _layers_from_cues(group.cues),
            anarchy_level=0.0,
        )
        primary = group.cues[0]
        duration = resolve_avatar_beat_duration_ms(group.text, group.cues)
        visual_cues = [
            build_avatar_visual_cue(
                layer,
                anarchy_level=0.0,
                duration_ms=layer_duration_ms(group.cues[layer_index]),
            )
            for layer_index, layer in enumerate(layers)
        ]
        enriched_layers: list[AvatarSpeechLayer] = []
        for layer_index, layer in enumerate(layers):
            enriched_layers.append(
                layer.model_copy(update={"visual_cue": visual_cues[layer_index]})
            )
        layers = enriched_layers

        moment = CompositionMoment(
            id=str(uuid.uuid4()),
            order=index,
            scene_id=SCRIPT_SCENE_ID,
            text_excerpt=group.text.strip(),
            speech_mode="avatar_video",
            avatar_speech_id=primary.id if len(group.cues) == 1 else None,
            avatar_video_clip_id=primary.video_clip_id if len(group.cues) == 1 else None,
            avatar_layers=layers,
            avatar_video_cue=visual_cues[0] if len(visual_cues) == 1 else None,
            duration_hint_ms=duration,
            start_delay_ms=max(0, 800 - index * 15),
        )
        moments.append(moment)

    moments = apply_anarchy_curve(ensure_moment_ids(moments), curve)

    for moment in moments:
        mode = projector_mode_for_anarchy(moment.anarchy_level)
        moment.projector_mode = mode  # type: ignore[assignment]
        if moment.avatar_layers:
            assigned = assign_projectors_for_layers(
                moment.avatar_layers,
                anarchy_level=moment.anarchy_level,
            )
            duration = moment.duration_hint_ms
            visual_cues = [
                build_avatar_visual_cue(
                    layer,
                    anarchy_level=moment.anarchy_level,
                    duration_ms=layer_duration_ms(cue_by_id[layer.avatar_speech_id])
                    if layer.avatar_speech_id in cue_by_id
                    else duration,
                )
                for layer in assigned
            ]
            moment.avatar_layers = [
                layer.model_copy(update={"visual_cue": visual_cues[i]})
                for i, layer in enumerate(assigned)
            ]
            moment.avatar_video_cue = visual_cues[0]
            if len(assigned) == 1:
                moment.avatar_speech_id = assigned[0].avatar_speech_id
                moment.avatar_video_clip_id = assigned[0].video_clip_id
        moment.overlap_with_previous = (
            overlap_for_anarchy(moment.anarchy_level) if moment.order > 0 else 0.0
        )

    max_voices = max((len(m.avatar_layers) or 1 for m in moments), default=1)
    return CompositionPlan(
        moments=moments,
        total_estimated_duration_sec=sum((m.duration_hint_ms or 8000) / 1000 for m in moments),
        max_concurrent_voices=min(6, max(3, max_voices)),
        max_concurrent_videos=min(6, max(2, max_voices)),
    )


def script_digest_for_analyse(*, max_chars: int = 12000) -> str:
    text = load_canonical_script_text().strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def animal_sections_from_script(script_text: str | None = None) -> list[tuple[str, str]]:
    """Rough sections by scene numbers in the avatar script."""
    text = script_text or load_canonical_script_text()
    pattern = re.compile(r"(\d{2})\.\s+([^,\n]+)")
    matches = list(pattern.finditer(text))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(2).strip(), text[start:end].strip()))
    if not sections:
        return [("Avatar-Skript", text)]
    return sections
