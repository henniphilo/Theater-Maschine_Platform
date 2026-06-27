"""Beamer-Zuweisung für Teil-2-Avatar-Beats."""

from __future__ import annotations

from app.director.cues.cue_models import VisualCue, VisualOutputAssignment
from app.schemas.inszenierung import AvatarSpeechLayer

ALL_PROJECTORS: tuple[str, ...] = ("rz21", "adam", "eva", "led")

AVATAR_DEFAULT_PROJECTOR: dict[str, str] = {
    "delphin": "rz21",
    "baerenklau": "rz21",
    "lamm": "adam",
    "petya": "eva",
    "wolf": "led",
}


def projector_mode_for_anarchy(anarchy_level: float) -> str:
    return "all" if anarchy_level >= 0.5 else "single"


def _default_projector(avatar: str) -> str:
    return AVATAR_DEFAULT_PROJECTOR.get(avatar.lower(), "rz21")


def assign_projectors_for_layers(
    layers: list[AvatarSpeechLayer],
    *,
    anarchy_level: float,
) -> list[AvatarSpeechLayer]:
    """Assign distinct projectors for chorus layers; escalate to all beamers when anarchic."""
    mode = projector_mode_for_anarchy(anarchy_level)
    used: set[str] = set()
    updated: list[AvatarSpeechLayer] = []

    for index, layer in enumerate(layers):
        if mode == "all":
            projector = None
            outputs = [
                VisualOutputAssignment(output_id=pid, clip_id=layer.video_clip_id)
                for pid in ALL_PROJECTORS
            ]
        else:
            preferred = layer.projector or _default_projector(layer.avatar)
            projector = preferred
            if preferred in used:
                for candidate in ALL_PROJECTORS:
                    if candidate not in used:
                        projector = candidate
                        break
            used.add(projector)
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
        can_be_interrupted=False,
        duration_ms=duration_ms,
        outputs=outputs,
    )
