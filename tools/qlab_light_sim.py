"""Shared helpers for QLab light simulation (colors + command text)."""

from __future__ import annotations

from typing import Any

# QLab instrument names: no underscores (use alphanumeric only).
SIM_INSTRUMENT = "TMPREVIEW"


def _qlab_level(value_0_255: int) -> int:
    """QLab light commands use 0–100 for RGB and intensity."""
    return max(0, min(100, int(round(value_0_255 * 100 / 255))))


def sim_color_for_scene(scene: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return internal RGB 0–255 and intensity 0–100 for a light_scenes.json entry."""
    scene_id = str(scene.get("id") or "")
    moods = {str(m).lower() for m in (scene.get("moods") or [])}
    intensity_pct = int(round(float(scene.get("intensity_max") or 0.75) * 100))

    if scene_id == "blackout" or "leer" in moods or "stille" in moods:
        return (0, 0, 0, 0)
    if "magenta" in moods or "magenta" in scene_id:
        return (220, 40, 200, intensity_pct)
    if "rot" in moods or "teppich" in scene_id or "warm" in moods:
        return (220, 70, 35, intensity_pct)
    if "kalt" in moods or "kalt" in scene_id:
        return (150, 195, 255, intensity_pct)
    if "gegenlicht" in moods or scene_id.startswith("gegenlicht"):
        return (210, 225, 255, max(35, intensity_pct - 15))
    if "seitenlicht" in moods or "hart" in moods:
        return (255, 255, 240, intensity_pct)
    if "saal" in moods or scene_id == "saallicht":
        return (255, 215, 170, intensity_pct)
    if "boden" in moods or "wolken" in moods or "neon" in moods:
        return (120, 255, 210, intensity_pct)
    if "spot" in moods or "fokus" in moods:
        return (255, 248, 230, intensity_pct)
    if "luster" in moods or "intim" in moods:
        return (255, 180, 90, intensity_pct)
    if "palmen" in moods or "exotisch" in moods:
        return (180, 255, 120, intensity_pct)
    if "blendung" in moods:
        return (255, 200, 255, intensity_pct)
    return (255, 240, 220, intensity_pct)


def build_command_text(scene: dict[str, Any]) -> str:
    red, green, blue, intensity = sim_color_for_scene(scene)
    return "\n".join(
        [
            f"{SIM_INSTRUMENT}.red = {_qlab_level(red)}",
            f"{SIM_INSTRUMENT}.green = {_qlab_level(green)}",
            f"{SIM_INSTRUMENT}.blue = {_qlab_level(blue)}",
            f"{SIM_INSTRUMENT}.intensity = {max(0, min(100, intensity))}",
        ]
    )
