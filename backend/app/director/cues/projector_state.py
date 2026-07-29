"""Per-output-slot lock state for Teil-2 avatar vs atmosphere routing.

Slot ids come from the active Production Device configuration when available;
otherwise legacy Burgtheater ids (adam/eva/rz21/led) are used.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.director.cues.cue_models import VideoType, VisualCue
from app.services.output_slots import (
    LEGACY_ATMOSPHERE_FREE_SLOT,
    LEGACY_OUTPUT_SLOTS,
    resolve_atmosphere_free_slots,
    resolve_output_slots,
)

# Back-compat export for older imports.
PROJECTORS = LEGACY_OUTPUT_SLOTS
ProjectorTarget = str


def estimate_avatar_duration_ms(text: str | None, duration_ms: int | None) -> int:
    if duration_ms is not None and duration_ms > 0:
        return duration_ms
    words = len((text or "").split())
    return max(8000, int(words / 2.2 * 1000))


@dataclass
class ProjectorSlot:
    projector: str
    active_clip_id: str | None = None
    locked_until: datetime | None = None
    video_type: VideoType = "atmosphere"

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and now < self.locked_until


@dataclass
class ProjectorState:
    slots: dict[str, ProjectorSlot] = field(default_factory=dict)
    allow_avatar_interrupt: bool = False
    atmosphere_free_slots: frozenset[str] = field(
        default_factory=lambda: frozenset({LEGACY_ATMOSPHERE_FREE_SLOT})
    )
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.slots:
            self.reconfigure_from_active_production()

    def reconfigure_from_active_production(self) -> None:
        """Reload slot ids from active Production devices (legacy fallback)."""
        slot_ids = resolve_output_slots()
        free = resolve_atmosphere_free_slots()
        with self._lock:
            self.atmosphere_free_slots = free
            self.slots = {p: ProjectorSlot(projector=p) for p in slot_ids}

    def configure_slots(
        self,
        slot_ids: tuple[str, ...] | list[str],
        *,
        atmosphere_free_slots: frozenset[str] | None = None,
    ) -> None:
        with self._lock:
            self.atmosphere_free_slots = (
                atmosphere_free_slots
                if atmosphere_free_slots is not None
                else frozenset({LEGACY_ATMOSPHERE_FREE_SLOT})
            )
            self.slots = {p: ProjectorSlot(projector=p) for p in slot_ids}

    def can_play(
        self,
        cue: VisualCue,
        *,
        now: datetime | None = None,
        text_excerpt: str | None = None,
    ) -> tuple[bool, str | None]:
        with self._lock:
            return self._can_play_unlocked(cue, now=now, text_excerpt=text_excerpt)

    def _can_play_unlocked(
        self,
        cue: VisualCue,
        *,
        now: datetime | None = None,
        text_excerpt: str | None = None,
    ) -> tuple[bool, str | None]:
        now = now or datetime.now(UTC)
        projector = cue.projector
        if projector is None and cue.outputs:
            projector = cue.outputs[0].output_id
        if projector not in self.slots:
            return True, None

        slot = self.slots[projector]
        if not slot.is_locked(now):
            return True, None

        if cue.video_type == "avatar" and cue.lock_until_finished:
            if self.allow_avatar_interrupt and cue.can_be_interrupted:
                return True, None
            return False, f"projector_locked:{projector}"

        if cue.video_type == "atmosphere" and projector in self.atmosphere_free_slots:
            return True, None

        if slot.video_type == "avatar" and not self.allow_avatar_interrupt:
            return False, f"avatar_active:{projector}"

        return True, None

    def lock_after_play(
        self,
        cue: VisualCue,
        *,
        now: datetime | None = None,
        text_excerpt: str | None = None,
    ) -> None:
        with self._lock:
            self._lock_after_play_unlocked(cue, now=now, text_excerpt=text_excerpt)

    def _lock_after_play_unlocked(
        self,
        cue: VisualCue,
        *,
        now: datetime | None = None,
        text_excerpt: str | None = None,
    ) -> None:
        now = now or datetime.now(UTC)
        projector = cue.projector
        if projector is None and cue.outputs:
            projector = cue.outputs[0].output_id
        if projector not in self.slots:
            return

        slot = self.slots[projector]
        slot.active_clip_id = cue.clip_id
        slot.video_type = cue.video_type

        if cue.video_type == "avatar" and cue.lock_until_finished:
            ms = estimate_avatar_duration_ms(text_excerpt, cue.duration_ms)
            slot.locked_until = now + timedelta(milliseconds=ms)
        elif cue.video_type == "atmosphere" and projector in self.atmosphere_free_slots:
            slot.locked_until = None
        elif cue.duration_ms:
            slot.locked_until = now + timedelta(milliseconds=cue.duration_ms)

    def release(self, projector: str) -> None:
        with self._lock:
            slot = self.slots.get(projector)
            if slot is None:
                return
            slot.active_clip_id = None
            slot.locked_until = None
            slot.video_type = "atmosphere"

    def reset(self) -> None:
        with self._lock:
            for slot in self.slots.values():
                slot.active_clip_id = None
                slot.locked_until = None
                slot.video_type = "atmosphere"
