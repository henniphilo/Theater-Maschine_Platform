"""Track active EOS light scenes so we can fade them out at intensity 0 (not /eos/key/out)."""

from __future__ import annotations

_active_scene_ids: list[str] = []


def active_light_scene_ids() -> list[str]:
    return list(_active_scene_ids)


def replace_active_light_scenes(scene_ids: list[str]) -> list[str]:
    """Return scenes being replaced; caller should send intensity 0 for them."""
    previous = list(_active_scene_ids)
    _active_scene_ids.clear()
    for scene_id in scene_ids:
        if scene_id and scene_id not in _active_scene_ids:
            _active_scene_ids.append(scene_id)
    return previous


def fade_out_scene(scene_id: str) -> None:
    if scene_id in _active_scene_ids:
        _active_scene_ids.remove(scene_id)


def clear_active_light_scenes() -> list[str]:
    previous = list(_active_scene_ids)
    _active_scene_ids.clear()
    return previous


def reset_light_scene_tracker() -> None:
    _active_scene_ids.clear()
