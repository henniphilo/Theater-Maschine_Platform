from app.director.cues.cue_models import VisualAction, VisualCue, VisualOutputAssignment
from app.services.video_cue_catalog import get_video_cue_catalog_service


def resolve_visual_assignments(visual: VisualCue) -> list[tuple[str, str, VisualAction]]:
    """Return (output_id, clip_id, action) for each projector assignment."""
    action = visual.action
    if visual.outputs:
        resolved: list[tuple[str, str, VisualAction]] = []
        for assignment in visual.outputs:
            clip_id = assignment.clip_id or visual.clip_id
            item_action = assignment.action or action
            if item_action in (VisualAction.FADE_TO_BLACK, VisualAction.STOP_CLIP):
                resolved.append((assignment.output_id, "black", item_action))
                continue
            if clip_id:
                resolved.append((assignment.output_id, clip_id, item_action))
        return resolved

    if action in (VisualAction.FADE_TO_BLACK, VisualAction.STOP_CLIP):
        catalog = get_video_cue_catalog_service().load()
        outputs = [p.id for p in catalog.projectors] or ["rz21"]
        return [(output_id, "black", action) for output_id in outputs]

    if visual.clip_id:
        return [("rz21", visual.clip_id, action)]

    return []


def format_visual_outputs_label(visual: VisualCue | None) -> str:
    if not visual:
        return ""
    assignments = resolve_visual_assignments(visual)
    if not assignments:
        return visual.clip_id or ""
    parts = [f"{output}:{clip}" for output, clip, _ in assignments]
    return ", ".join(parts)
