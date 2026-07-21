"""UDP OSC listener for /avatar/done completion feedback (QLab relay / future Pixera)."""

from __future__ import annotations

import logging
import threading

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

from app.director.avatar_done_gate import AVATAR_DONE_ADDRESS, get_avatar_done_gate
from app.director.outputs.signal_trace import emit_signal_trace_event

logger = logging.getLogger(__name__)


class AvatarDoneListener:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._server: BlockingOSCUDPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        dispatcher = Dispatcher()
        dispatcher.map(AVATAR_DONE_ADDRESS, self._on_done, needs_reply_address=False)
        self._server = BlockingOSCUDPServer((self.host, self.port), dispatcher)
        self._thread = threading.Thread(
            target=self._serve,
            name="avatar-done-listener",
            daemon=True,
        )
        self._thread.start()
        logger.info("avatar done OSC listening on %s:%s (%s)", self.host, self.port, AVATAR_DONE_ADDRESS)

    def stop(self, timeout: float = 1.0) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _serve(self) -> None:
        assert self._server is not None
        try:
            self._server.serve_forever()
        except OSError as exc:
            logger.error("avatar done listener failed: %s", exc)

    def _on_done(self, address: str, *args: object) -> None:
        cue_name: str | None = None
        if args and isinstance(args[0], str):
            cue_name = args[0].strip() or None
        get_avatar_done_gate().signal_done(cue_name)
        emit_signal_trace_event(
            "avatar.done_received",
            status="received",
            bridge="avatar_done",
            address=address,
            cue_name=cue_name,
        )
        logger.info("avatar done: %s", cue_name or "(empty)")


_listener: AvatarDoneListener | None = None
_listener_lock = threading.Lock()


def get_avatar_done_listener() -> AvatarDoneListener | None:
    return _listener


def start_avatar_done_listener(*, host: str, port: int) -> AvatarDoneListener:
    global _listener
    with _listener_lock:
        if _listener is not None and _listener.running:
            if _listener.host == host and _listener.port == port:
                return _listener
            _listener.stop()
        _listener = AvatarDoneListener(host, port)
        _listener.start()
        return _listener


def stop_avatar_done_listener() -> None:
    global _listener
    with _listener_lock:
        if _listener is not None:
            _listener.stop()
            _listener = None
