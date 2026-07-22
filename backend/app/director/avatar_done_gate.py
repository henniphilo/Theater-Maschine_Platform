"""Wait for avatar video completion OSC (/avatar/done) when sync would drift.

Frontend keeps TTS parallel with the clip and only blocks before the next avatar
(or show end) while a previous clip is still pending.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field


AVATAR_DONE_ADDRESS = "/avatar/done"


@dataclass
class AvatarDoneWaitResult:
    status: str  # disabled | skipped | done | timeout | cancelled
    received: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    wait_ms: int = 0


@dataclass
class _ArmedWait:
    expected: set[str]
    received: set[str] = field(default_factory=set)
    event: threading.Event = field(default_factory=threading.Event)
    cancelled: bool = False

    def note(self, cue_name: str) -> None:
        if cue_name in self.expected:
            self.received.add(cue_name)
            if self.expected <= self.received:
                self.event.set()


class AvatarDoneGate:
    """Thread-safe gate: arm expected cue names, signal on OSC, wait until complete/timeout."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._waits: dict[str, _ArmedWait] = {}
        self._orphan_done: set[str] = set()
        self._last_done: str | None = None
        self._last_done_at: float | None = None

    def reset(self) -> None:
        with self._lock:
            for wait in self._waits.values():
                wait.cancelled = True
                wait.event.set()
            self._waits.clear()
            self._orphan_done.clear()
            self._last_done = None
            self._last_done_at = None

    def signal_done(self, cue_name: str | None) -> None:
        name = (cue_name or "").strip()
        if not name:
            return
        with self._lock:
            self._last_done = name
            self._last_done_at = time.monotonic()
            matched = False
            for wait in self._waits.values():
                before = len(wait.received)
                wait.note(name)
                if len(wait.received) > before:
                    matched = True
            if not matched:
                self._orphan_done.add(name)

    def status_snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "armed_waits": len(self._waits),
                "last_done": self._last_done,
                "last_done_age_ms": (
                    None
                    if self._last_done_at is None
                    else int((time.monotonic() - self._last_done_at) * 1000)
                ),
                "orphan_done_count": len(self._orphan_done),
            }

    def wait_for(
        self,
        cue_names: list[str],
        *,
        timeout_ms: int,
        should_cancel: threading.Event | None = None,
    ) -> AvatarDoneWaitResult:
        expected = {name.strip() for name in cue_names if isinstance(name, str) and name.strip()}
        if not expected:
            return AvatarDoneWaitResult(status="skipped")

        wait_id = str(uuid.uuid4())
        armed = _ArmedWait(expected=set(expected))
        started = time.monotonic()

        with self._lock:
            # Consume early arrivals that raced the arm call.
            for name in list(self._orphan_done):
                if name in expected:
                    armed.received.add(name)
                    self._orphan_done.discard(name)
            if expected <= armed.received:
                return AvatarDoneWaitResult(
                    status="done",
                    received=sorted(armed.received),
                    wait_ms=0,
                )
            self._waits[wait_id] = armed

        timeout_s = max(0.0, timeout_ms / 1000.0)
        deadline = started + timeout_s
        try:
            while True:
                if should_cancel is not None and should_cancel.is_set():
                    armed.cancelled = True
                    return AvatarDoneWaitResult(
                        status="cancelled",
                        received=sorted(armed.received),
                        missing=sorted(expected - armed.received),
                        wait_ms=int((time.monotonic() - started) * 1000),
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                armed.event.wait(timeout=min(0.1, remaining))
                if expected <= armed.received:
                    return AvatarDoneWaitResult(
                        status="done",
                        received=sorted(armed.received),
                        wait_ms=int((time.monotonic() - started) * 1000),
                    )
                armed.event.clear()
            return AvatarDoneWaitResult(
                status="timeout",
                received=sorted(armed.received),
                missing=sorted(expected - armed.received),
                wait_ms=int((time.monotonic() - started) * 1000),
            )
        finally:
            with self._lock:
                self._waits.pop(wait_id, None)


_gate = AvatarDoneGate()


def get_avatar_done_gate() -> AvatarDoneGate:
    return _gate
