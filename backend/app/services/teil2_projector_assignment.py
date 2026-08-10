"""Beamer-Zuweisung für Teil-2-Avatar-Beats."""

from __future__ import annotations

from typing import TypeVar

from app.director.cues.cue_models import VisualCue, VisualOutputAssignment
from app.schemas.inszenierung import AvatarSpeechLayer

ALL_PROJECTORS: tuple[str, ...] = ("rz21", "adam", "eva", "led")
# Side beamers first for atmosphere + avatar rotation (Adam/Eva Bühnenbeamer).
STAGE_BEAMER_ORDER: tuple[str, ...] = ("adam", "eva", "rz21", "led")
# Adam/Eva must never go dark when free — atmosphere fills them whenever no avatar owns them.
STAGE_ALWAYS_ATMOSPHERE: tuple[str, ...] = ("adam", "eva")

AVATAR_DEFAULT_PROJECTOR: dict[str, str] = {
    "delphin": "rz21",
    "baerenklau": "rz21",
    "lamm": "adam",
    "petya": "eva",
    "wolf": "led",
}

T = TypeVar("T")


def projector_mode_for_anarchy(anarchy_level: float) -> str:
    """single = one primary beamer; all = primary may be mirrored to more surfaces."""
    return "all" if anarchy_level >= 0.5 else "single"


def chorus_performer_count(candidate_count: int, anarchy_level: float) -> int:
    """How many same-text avatar clips perform at this anarchy level.

    Multiple CSV rows can share identical text (chorus candidates). The rule is:
    low anarchy → one performer; mid → up to two; high → full chorus.
    """
    if candidate_count <= 1:
        return candidate_count
    if anarchy_level < 0.35:
        return 1
    if anarchy_level < 0.65:
        return min(2, candidate_count)
    return candidate_count


def select_chorus_candidates(
    candidates: list[T],
    *,
    anarchy_level: float,
    seed: int = 0,
) -> list[T]:
    """Pick which same-text avatar videos perform (one, some, or all)."""
    if not candidates:
        return []
    count = chorus_performer_count(len(candidates), anarchy_level)
    if count >= len(candidates):
        return list(candidates)
    start = seed % len(candidates)
    rotated = candidates[start:] + candidates[:start]
    return rotated[:count]


def mirror_count_for_anarchy(anarchy_level: float) -> int:
    """How many *additional* beamers get the same clip (besides primary)."""
    if anarchy_level >= 0.75:
        return 2
    if anarchy_level >= 0.3:
        return 1
    return 0


def _default_projector(avatar: str) -> str:
    return AVATAR_DEFAULT_PROJECTOR.get(avatar.lower(), "rz21")


def _rotated_preferred(avatar: str, seed: int) -> str:
    """Rotate character defaults so the same avatar does not stick to one beamer."""
    base = _default_projector(avatar)
    try:
        base_index = STAGE_BEAMER_ORDER.index(base)
    except ValueError:
        base_index = 0
    return STAGE_BEAMER_ORDER[(base_index + max(0, seed)) % len(STAGE_BEAMER_ORDER)]


def pick_distinct_projector(
    *,
    preferred: str | None = None,
    used: set[str] | None = None,
    reserved: set[str] | None = None,
    fallback_index: int = 0,
) -> str:
    """Pick one projector, preferring unused beamers (chorus + rotation)."""
    used_set = used or set()
    reserved_set = reserved or set()
    free = [p for p in STAGE_BEAMER_ORDER if p not in used_set and p not in reserved_set]
    if preferred and preferred in free:
        return preferred
    if free:
        return free[fallback_index % len(free)]
    pool = [p for p in STAGE_BEAMER_ORDER if p not in used_set]
    if pool:
        return pool[fallback_index % len(pool)]
    # All beamers already used in this rotation window — keep cycling, never sticky-adam.
    return STAGE_BEAMER_ORDER[fallback_index % len(STAGE_BEAMER_ORDER)]


def pick_atmosphere_projectors(
    count: int,
    *,
    reserved: set[str],
    seed: int = 0,
) -> list[str]:
    """Atmosphere/random clips on free beamers; prefer Adam/Eva side projectors."""
    pool = [p for p in STAGE_BEAMER_ORDER if p not in reserved]
    if not pool:
        return ["rz21"] * max(1, count)
    return [pool[(seed + index) % len(pool)] for index in range(max(1, count))]


def atmosphere_targets_for_free(
    free: list[str],
    *,
    anarchy: float,
    seed: int = 0,
) -> list[str]:
    """Beamers that get atmosphere at this tick.

    Adam and Eva are always filled when free (no avatar). Additional free surfaces
    (rz21, led) escalate with anarchy.
    """
    free_set = set(free)
    always = [p for p in STAGE_ALWAYS_ATMOSPHERE if p in free_set]
    others = [p for p in STAGE_BEAMER_ORDER if p in free_set and p not in always]
    if anarchy < 0.35:
        extra_n = 0
    elif anarchy < 0.55:
        extra_n = min(1, len(others))
    else:
        extra_n = len(others)
    if not others or extra_n <= 0:
        return always
    start = seed % len(others)
    ordered = others[start:] + others[:start]
    return always + ordered[:extra_n]


def mirror_outputs_for_clip(
    primary: str,
    clip_id: str,
    *,
    occupied: set[str],
    mirror_count: int,
    seed: int = 0,
) -> list[VisualOutputAssignment]:
    """Same clip on primary + up to mirror_count additional free beamers."""
    outputs = [VisualOutputAssignment(output_id=primary, clip_id=clip_id)]
    if mirror_count <= 0:
        return outputs
    candidates = [p for p in STAGE_BEAMER_ORDER if p not in occupied]
    if not candidates:
        return outputs
    start = seed % len(candidates)
    ordered = candidates[start:] + candidates[:start]
    for projector in ordered[:mirror_count]:
        outputs.append(VisualOutputAssignment(output_id=projector, clip_id=clip_id))
    return outputs


def assign_projectors_for_layers(
    layers: list[AvatarSpeechLayer],
    *,
    anarchy_level: float,
    used: set[str] | None = None,
    seed: int = 0,
) -> list[AvatarSpeechLayer]:
    """Assign projectors per chorus layer; optionally mirror the same clip to more beamers.

    Within one call, each layer gets a distinct *primary* projector.
    When anarchy is moderate/high, the same clip may also run on additional free surfaces.
    """
    used_projectors = used if used is not None else set()
    # Rotation window: once all beamers were primary targets, free them for the next cycle.
    if len(used_projectors) >= len(ALL_PROJECTORS):
        used_projectors.clear()

    primaries: list[str] = []
    for index, layer in enumerate(layers):
        preferred = layer.projector or _rotated_preferred(layer.avatar, seed + index)
        projector = pick_distinct_projector(
            preferred=preferred,
            used=used_projectors,
            fallback_index=seed + index,
        )
        used_projectors.add(projector)
        primaries.append(projector)

    occupied: set[str] = set(primaries)
    mirrors = mirror_count_for_anarchy(anarchy_level)
    updated: list[AvatarSpeechLayer] = []

    for index, (layer, projector) in enumerate(zip(layers, primaries, strict=True)):
        outputs = mirror_outputs_for_clip(
            projector,
            layer.video_clip_id,
            occupied=occupied - {projector},
            mirror_count=mirrors,
            seed=seed + index * 3,
        )
        for assignment in outputs:
            occupied.add(assignment.output_id)
        updated.append(
            layer.model_copy(
                update={
                    "projector": projector,
                    "outputs": outputs,
                }
            )
        )
    return updated


def build_avatar_visual_cue(
    layer: AvatarSpeechLayer,
    *,
    anarchy_level: float,
    duration_ms: int | None,
) -> VisualCue:
    blend_layer = anarchy_level > 0.55
    primary = layer.projector or (layer.outputs[0].output_id if layer.outputs else "rz21")
    outputs = layer.outputs or [
        VisualOutputAssignment(output_id=primary, clip_id=layer.video_clip_id)
    ]
    return VisualCue(
        clip_id=layer.video_clip_id,
        blend_mode="layer" if blend_layer else "replace",
        video_type="avatar",
        projector=primary,  # type: ignore[arg-type]
        lock_until_finished=True,
        can_be_interrupted=True,
        duration_ms=duration_ms,
        outputs=outputs,
    )
