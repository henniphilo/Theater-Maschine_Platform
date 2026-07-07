"""Background OSC send queue — HTTP handlers return before hardware I/O finishes."""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.director.cues.cue_models import OscCommand
from app.director.outputs.osc_commands import send_osc_commands

CUE_STAGGER_SECONDS = 0.15
_logger = logging.getLogger("theatermaschine.osc")


@dataclass
class _OscBatch:
    commands: list[OscCommand]
    stagger: bool
    bridges: dict[str, Any]
    done: threading.Event = field(default_factory=threading.Event)
    sent: list[OscCommand] = field(default_factory=list)


class OscCommandQueue:
    def __init__(self) -> None:
        self._queue: queue.Queue[_OscBatch] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, name="osc-queue", daemon=True)
        self._started = False
        self._start_lock = threading.Lock()

    def start(self) -> None:
        with self._start_lock:
            if self._started:
                return
            self._thread.start()
            self._started = True

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    def enqueue(
        self,
        commands: list[OscCommand],
        *,
        stagger: bool,
        bridges: dict[str, Any],
        wait: bool = False,
        timeout: float | None = None,
    ) -> list[OscCommand]:
        """Queue OSC batch; return planned commands unless wait=True (tests)."""
        if not commands:
            return []
        self.start()
        batch = _OscBatch(commands=commands, stagger=stagger, bridges=bridges)
        wait_timeout = timeout if timeout is not None else 30.0
        enqueued_at = time.monotonic()
        _logger.info(
            "[OSC QUEUE] enqueue depth=%d cmds=%d stagger=%s",
            self.depth + 1,
            len(commands),
            stagger,
        )
        self._queue.put(batch)
        if wait:
            if not batch.done.wait(timeout=wait_timeout):
                raise TimeoutError("OSC queue batch did not complete in time")
            elapsed_ms = (time.monotonic() - enqueued_at) * 1000
            _logger.info(
                "[OSC QUEUE] done waited_ms=%.0f sent=%d",
                elapsed_ms,
                len(batch.sent),
            )
            return batch.sent
        return list(commands)

    def flush(self, timeout: float = 30.0) -> None:
        """Block until all queued batches finish (tests)."""
        self.start()
        sentinel = _OscBatch(commands=[], stagger=False, bridges={})
        self._queue.put(sentinel)
        if not sentinel.done.wait(timeout):
            raise TimeoutError("OSC queue flush timed out")

    def _worker(self) -> None:
        while True:
            batch = self._queue.get()
            try:
                if batch.commands:
                    batch.sent = self._send_batch(
                        batch.commands,
                        stagger=batch.stagger,
                        bridges=batch.bridges,
                    )
            except Exception:
                _logger.exception("[OSC QUEUE] batch failed")
            finally:
                batch.done.set()
                self._queue.task_done()

    @staticmethod
    def _send_batch(
        commands: list[OscCommand],
        *,
        stagger: bool,
        bridges: dict[str, Any],
    ) -> list[OscCommand]:
        return send_osc_batch(commands, stagger=stagger, bridges=bridges)


def send_osc_batch(
    commands: list[OscCommand],
    *,
    stagger: bool,
    bridges: dict[str, Any],
) -> list[OscCommand]:
    sent: list[OscCommand] = []
    last_bridge: str | None = None
    for cmd in commands:
        if stagger and last_bridge is not None and cmd.bridge != last_bridge:
            time.sleep(CUE_STAGGER_SECONDS)
        last_bridge = cmd.bridge
        try:
            send_osc_commands([cmd], bridges)
        except Exception as exc:
            _logger.warning(
                "[CUE FAILED] bridge=%s address=%s: %s",
                cmd.bridge,
                cmd.address,
                exc,
            )
        sent.append(cmd)
    return sent


_queue: OscCommandQueue | None = None


def get_osc_command_queue() -> OscCommandQueue:
    global _queue
    if _queue is None:
        _queue = OscCommandQueue()
    return _queue
