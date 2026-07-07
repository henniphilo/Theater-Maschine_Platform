from app.director.cues.cue_models import VisualAction, VisualCue
from app.services.video_cue_catalog import get_video_cue_catalog_service
from app.services.video_scope import VideoScope


def _available_projectors_for_clip(clip_id: str, *, video_scope: VideoScope = "part2") -> list[str]:
    catalog_service = get_video_cue_catalog_service()
    return catalog_service.projectors_for_clip(clip_id, scope=video_scope)


def _resolve_output_id(
    output_id: str,
    clip_id: str | None,
    *,
    video_scope: VideoScope = "part2",
) -> str:
    if not clip_id:
        return output_id
    available = _available_projectors_for_clip(clip_id, video_scope=video_scope)
    if output_id in available:
        return output_id
    for candidate in ("adam", "eva", "rz21", "led"):
        if candidate in available:
            return candidate
    return output_id


def _target_output_ids(visual: VisualCue, *, video_scope: VideoScope = "part2") -> list[str]:
    """Resolve projector targets: explicit outputs/projector win; else all beamers for clip."""
    catalog_service = get_video_cue_catalog_service()
    catalog = catalog_service.load(video_scope)

    if visual.projector:
        resolved = _resolve_output_id(visual.projector, visual.clip_id, video_scope=video_scope)
        return [resolved]

    if visual.clip_id:
        clip = catalog_service.clip_by_id(visual.clip_id, catalog, scope=video_scope)
        if clip and clip.projector_preference:
            resolved = _resolve_output_id(
                clip.projector_preference, visual.clip_id, video_scope=video_scope
            )
            return [resolved]
        return _available_projectors_for_clip(visual.clip_id, video_scope=video_scope)

    return [p.id for p in catalog.projectors] or ["rz21"]


def resolve_visual_assignments(
    visual: VisualCue,
    *,
    video_scope: VideoScope = "part2",
) -> list[tuple[str, str, VisualAction]]:
    """Return (output_id, clip_id, action) for each projector assignment."""
    action = visual.action
    if visual.outputs:
        resolved: list[tuple[str, str, VisualAction]] = []
        for assignment in visual.outputs:
            clip_id = assignment.clip_id or visual.clip_id
            item_action = assignment.action or action
            output_id = _resolve_output_id(
                assignment.output_id, clip_id, video_scope=video_scope
            )
            if item_action in (VisualAction.FADE_TO_BLACK, VisualAction.STOP_CLIP):
                resolved.append((output_id, "black", item_action))
                continue
            if clip_id:
                resolved.append((output_id, clip_id, item_action))
        return resolved

    if action in (VisualAction.FADE_TO_BLACK, VisualAction.STOP_CLIP):
        return [(output_id, "black", action) for output_id in _target_output_ids(visual, video_scope=video_scope)]

    if visual.clip_id:
        return [
            (_resolve_output_id(output_id, visual.clip_id, video_scope=video_scope), visual.clip_id, action)
            for output_id in _target_output_ids(visual, video_scope=video_scope)
        ]

    return []


def format_visual_outputs_label(visual: VisualCue | None) -> str:
    if not visual:
        return ""
    assignments = resolve_visual_assignments(visual)
    if not assignments:
        return visual.clip_id or ""
    parts = [f"{output}:{clip}" for output, clip, _ in assignments]
    return ", ".join(parts)
