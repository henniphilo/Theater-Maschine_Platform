from dataclasses import dataclass, field
from threading import Lock

from app.core.config import settings


@dataclass
class SafetyState:
    autopilot_enabled: bool = True
    visuals_enabled: bool = True
    sound_enabled: bool = True
    lights_enabled: bool = True
    blackout_locked: bool = True
    emergency_stop_active: bool = False
    _lock: Lock = field(default_factory=Lock, repr=False)

    @classmethod
    def from_settings(cls) -> "SafetyState":
        return cls(autopilot_enabled=settings.director_autopilot_default)

    def update(self, **kwargs: bool) -> "SafetyState":
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key) and isinstance(value, bool):
                    setattr(self, key, value)
            return self

    def to_dict(self) -> dict[str, bool]:
        with self._lock:
            return {
                "autopilot_enabled": self.autopilot_enabled,
                "visuals_enabled": self.visuals_enabled,
                "sound_enabled": self.sound_enabled,
                "lights_enabled": self.lights_enabled,
                "blackout_locked": self.blackout_locked,
                "emergency_stop_active": self.emergency_stop_active,
            }

    def emergency_stop(self) -> None:
        with self._lock:
            self.emergency_stop_active = True
            self.autopilot_enabled = False
            self.visuals_enabled = False
            self.sound_enabled = False
            self.lights_enabled = False

    def clear_emergency_stop(self) -> None:
        with self._lock:
            self.emergency_stop_active = False


_safety_state = SafetyState.from_settings()


def get_safety_state() -> SafetyState:
    return _safety_state
