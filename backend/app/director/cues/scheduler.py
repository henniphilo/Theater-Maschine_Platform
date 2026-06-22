from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.director.cues.cue_models import DramaturgyDecision, LightAction, VisualAction
from app.director.cues.safety import SafetyState
from app.director.media.database import DramaturgyRules


@dataclass
class CueScheduler:
    rules: DramaturgyRules
    safety: SafetyState
    _last_light_change: datetime | None = field(default=None, init=False)
    _last_video_change: datetime | None = field(default=None, init=False)
    _last_sound_change: datetime | None = field(default=None, init=False)
    active_cues: list[str] = field(default_factory=list)

    def can_execute(
        self,
        decision: DramaturgyDecision,
        *,
        anarchy_level: float = 0.0,
        skip_interval_check: bool = False,
    ) -> tuple[bool, str | None]:
        if self.safety.emergency_stop_active:
            return False, "emergency_stop_active"

        if not self.safety.autopilot_enabled:
            return False, "autopilot_disabled"

        now = datetime.now(UTC)

        if decision.visual and not self.safety.visuals_enabled:
            return False, "visuals_disabled"

        if decision.sound and not self.safety.sound_enabled:
            return False, "sound_disabled"

        if decision.light and not self.safety.lights_enabled:
            return False, "lights_disabled"

        if skip_interval_check:
            return True, None

        scale = max(0.05, 1.0 - anarchy_level * 0.95)

        if decision.visual:
            blocked = self._check_interval(
                self._last_video_change,
                self.rules.min_cue_interval_seconds.get("video", 5.0) * scale,
                now,
            )
            if blocked:
                return False, "video_cue_too_soon"

            if (
                decision.visual.action == VisualAction.FADE_TO_BLACK
                and self.safety.blackout_locked
            ):
                return False, "blackout_locked"

        if decision.light:
            blocked = self._check_interval(
                self._last_light_change,
                self.rules.min_cue_interval_seconds.get("light", 10.0) * scale,
                now,
            )
            if blocked:
                return False, "light_cue_too_soon"

            if (
                decision.light.action == LightAction.FADE_BLACKOUT
                and self.safety.blackout_locked
            ):
                return False, "blackout_locked"

        if decision.sound:
            blocked = self._check_interval(
                self._last_sound_change,
                self.rules.min_cue_interval_seconds.get("sound", 3.0) * scale,
                now,
            )
            if blocked:
                return False, "sound_cue_too_soon"

        return True, None

    def mark_executed(self, decision: DramaturgyDecision) -> None:
        now = datetime.now(UTC)
        if decision.visual:
            self._last_video_change = now
            if decision.visual.clip_id:
                self._register_active(decision.visual.clip_id)
        if decision.sound and decision.sound.cue_id:
            self._last_sound_change = now
            self._register_active(decision.sound.cue_id)
        if decision.light and decision.light.scene_id:
            self._last_light_change = now
            self._register_active(decision.light.scene_id)

    def clear_active(self) -> None:
        self.active_cues.clear()

    def _register_active(self, cue_id: str) -> None:
        if cue_id not in self.active_cues:
            self.active_cues.append(cue_id)
        self.active_cues = self.active_cues[-10:]

    @staticmethod
    def _check_interval(last: datetime | None, min_seconds: float, now: datetime) -> bool:
        if last is None:
            return False
        elapsed = (now - last).total_seconds()
        return elapsed < min_seconds
