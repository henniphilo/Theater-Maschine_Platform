"""Shared dramaturgy runtime state for music/video mixing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.director.cues.cue_models import DecisionKind, DramaturgyDecision, VisualAction


@dataclass
class DramaturgyState:
    scene_intensity: float = 0.5
    text_density: float = 0.5
    emotional_tone: list[str] = field(default_factory=list)
    current_phase: str = "development"
    music_density: float = 0.0
    video_density: float = 0.0
    total_media_density: float = 0.0
    active_music_layers: int = 0
    active_video_layers: int = 0
    time_since_last_cue: float = 0.0
    time_since_last_silence: float = 0.0
    recent_cue_types: list[str] = field(default_factory=list)
    repeated_assets: dict[str, int] = field(default_factory=dict)
    _last_cue_at: datetime | None = field(default=None, repr=False)
    _last_silence_at: datetime | None = field(default=None, repr=False)

    def snapshot(self) -> dict[str, object]:
        return {
            "scene_intensity": round(self.scene_intensity, 3),
            "text_density": round(self.text_density, 3),
            "emotional_tone": list(self.emotional_tone),
            "current_phase": self.current_phase,
            "music_density": round(self.music_density, 3),
            "video_density": round(self.video_density, 3),
            "total_media_density": round(self.total_media_density, 3),
            "active_music_layers": self.active_music_layers,
            "active_video_layers": self.active_video_layers,
            "time_since_last_cue": round(self.time_since_last_cue, 1),
            "time_since_last_silence": round(self.time_since_last_silence, 1),
            "recent_cue_types": list(self.recent_cue_types[-8:]),
            "repeated_assets": dict(self.repeated_assets),
        }

    def tick(self) -> None:
        now = datetime.now(UTC)
        if self._last_cue_at is not None:
            self.time_since_last_cue = (now - self._last_cue_at).total_seconds()
        if self._last_silence_at is not None:
            self.time_since_last_silence = (now - self._last_silence_at).total_seconds()

    def apply_text_context(self, *, text: str, mood: str, intensity: float, tags: list[str]) -> None:
        length = len(text.strip())
        self.text_density = min(1.0, length / 400.0)
        self.scene_intensity = intensity
        self.emotional_tone = [mood, *tags[:2]]
        self.tick()

    def apply_decision(self, decision: DramaturgyDecision, *, executed: bool) -> None:
        now = datetime.now(UTC)
        self.tick()
        if not executed:
            return

        kind = decision.decision_kind or DecisionKind.EXECUTE
        if kind == DecisionKind.NONE:
            self._last_silence_at = now
            self.music_density = max(0.0, self.music_density - 0.15)
            self.video_density = max(0.0, self.video_density - 0.15)
            self._recompute_totals()
            return

        self._last_cue_at = now
        event_types: list[str] = []

        if decision.visual:
            action = decision.visual.action
            if action in {VisualAction.STOP_CLIP, VisualAction.FADE_TO_BLACK}:
                self.video_density = max(0.0, self.video_density - 0.25)
                self.active_video_layers = max(0, self.active_video_layers - 1)
                event_types.append("video_stop")
            else:
                delta = 0.2 if decision.visual.blend_mode == "layer" else 0.35
                self.video_density = min(1.0, self.video_density + delta)
                if decision.visual.blend_mode == "layer":
                    self.active_video_layers += 1
                else:
                    self.active_video_layers = 1
                event_types.append("video_start")
                if decision.visual.clip_id:
                    self._register_asset(decision.visual.clip_id)

        if decision.sound and decision.sound.cue_id:
            cue_id = decision.sound.cue_id
            if cue_id.endswith("_out") or "cut" in cue_id.lower():
                self.music_density = max(0.0, self.music_density - 0.2)
                self.active_music_layers = max(0, self.active_music_layers - 1)
                event_types.append("music_stop")
            else:
                self.music_density = min(1.0, self.music_density + 0.25)
                self.active_music_layers += 1
                event_types.append("music_layer")
                self._register_asset(cue_id)

        if decision.light:
            self.scene_intensity = min(1.0, max(self.scene_intensity, decision.intensity))
            event_types.append("light_change")

        self.recent_cue_types.extend(event_types)
        self.recent_cue_types = self.recent_cue_types[-12:]
        self._recompute_totals()

    def _register_asset(self, asset_id: str) -> None:
        self.repeated_assets[asset_id] = self.repeated_assets.get(asset_id, 0) + 1

    def _recompute_totals(self) -> None:
        self.total_media_density = min(1.0, self.music_density * 0.45 + self.video_density * 0.55)
