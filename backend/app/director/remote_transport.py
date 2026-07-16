"""In-memory mailbox for remote Play/Pause/Stop from a phone to the stage browser."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Literal

RemoteTransportAction = Literal["play", "pause", "stop"]

# Commands older than this are ignored (phone pressed before Mac tab was ready).
COMMAND_TTL_SEC = 30.0
# Listener is "connected" if it polled within this window.
LISTENER_FRESH_SEC = 2.5


@dataclass(frozen=True)
class RemoteTransportCommand:
    id: str
    action: RemoteTransportAction
    created_at: float


class RemoteTransportMailbox:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: RemoteTransportCommand | None = None
        self._listener_heartbeat_at: float = 0.0

    def reset(self) -> None:
        with self._lock:
            self._pending = None
            self._listener_heartbeat_at = 0.0

    def post(self, action: RemoteTransportAction) -> RemoteTransportCommand:
        cmd = RemoteTransportCommand(
            id=str(uuid.uuid4()),
            action=action,
            created_at=time.monotonic(),
        )
        with self._lock:
            self._pending = cmd
        return cmd

    def heartbeat(self) -> None:
        with self._lock:
            self._listener_heartbeat_at = time.monotonic()

    def _drop_stale_locked(self, now: float) -> None:
        if self._pending is None:
            return
        if now - self._pending.created_at > COMMAND_TTL_SEC:
            self._pending = None

    def snapshot(self, *, consume: bool, heartbeat: bool) -> dict[str, object]:
        now = time.monotonic()
        with self._lock:
            if heartbeat:
                self._listener_heartbeat_at = now
            self._drop_stale_locked(now)
            pending = self._pending
            if consume and pending is not None:
                self._pending = None
            listener_at = self._listener_heartbeat_at

        listener_connected = (
            listener_at > 0.0 and (now - listener_at) <= LISTENER_FRESH_SEC
        )
        return {
            "pending": (
                None
                if pending is None
                else {
                    "id": pending.id,
                    "action": pending.action,
                    "created_at": pending.created_at,
                }
            ),
            "listener_connected": listener_connected,
            "listener_heartbeat_age_sec": (
                None if listener_at <= 0.0 else round(now - listener_at, 3)
            ),
        }


_mailbox = RemoteTransportMailbox()


def get_remote_transport_mailbox() -> RemoteTransportMailbox:
    return _mailbox
