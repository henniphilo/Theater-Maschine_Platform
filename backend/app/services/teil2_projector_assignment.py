"""Beamer-Zuweisung für Teil-2-Avatar-Beats."""

from __future__ import annotations

from app.director.cues.cue_models import VisualCue, VisualOutputAssignment
from app.schemas.inszenierung import AvatarSpeechLayer

ALL_PROJECTORS: tuple[str, ...] = ("rz21", "adam", "eva", "led")
# Side beamers first for atmosphere + avatar rotation (Adam/Eva Bühnenbeamer).
STAGE_BEAMER_ORDER: tuple[str, ...] = ("adam", "eva", "rz21", "led")

AVATAR_DEFAULT_PROJECTOR: dict[str, str] = {
    "delphin": "rz21",
    "baerenklau": "rz21",
    "lamm": "adam",
    "petya": "eva",
    "wolf": "led",
}


def projector_mode_for_anarchy(anarchy_level: float) -> str:
    """Blend/layer semantics for high anarchy — not «all beamers on one clip»."""
    return "all" if anarchy_level >= 0.5 else "single"


def _default_projector(avatar: str) -> str:
    return AVATAR_DEFAULT_PROJECTOR.get(avatar.lower(), "rz21")


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


def assign_projectors_for_layers(
    layers: list[AvatarSpeechLayer],
    *,
    anarchy_level: float,
    used: set[str] | None = None,
) -> list[AvatarSpeechLayer]:
    """Assign exactly one distinct projector per chorus layer."""
    del anarchy_level  # blend mode handled in build_avatar_visual_cue
    used_projectors = used if used is not None else set()
    updated: list[AvatarSpeechLayer] = []

    for index, layer in enumerate(layers):
        preferred = layer.projector or _default_projector(layer.avatar)
        projector = pick_distinct_projector(
            preferred=preferred,
            used=used_projectors,
            fallback_index=index,
        )
        used_projectors.add(projector)
        outputs = [VisualOutputAssignment(output_id=projector, clip_id=layer.video_clip_id)]
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
