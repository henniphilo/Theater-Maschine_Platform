#!/usr/bin/env python3
"""Translate Theatermaschine OSC to QLab (/cue/{name}/start).

Video: Pixera /pixera/args/cue/apply on PIXERA_LISTEN_PORT (default 8990).
Light:  /light/set_scene and /light/blackout on LIGHT_LISTEN_PORT (default 7000)
        when LIGHT_OSC_MIRROR=true in backend/.env.

Optional reverse path (avatar done gate):
  QLab show-control cue/stop → /avatar/done → Theatermaschine :8991

Forwards to QLab on QLAB_PORT (default 53000).
See docs/qlab_setup.md and docs/avatar_done_gate.md.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import sys
import threading
import time

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_message import OscMessage
from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

PIXERA_APPLY_ADDRESS = "/pixera/args/cue/apply"
LIGHT_SET_SCENE_ADDRESS = "/light/set_scene"
LIGHT_BLACKOUT_ADDRESS = "/light/blackout"
AVATAR_DONE_ADDRESS = "/avatar/done"
QLAB_CUE_STOP_SUFFIX = "/cue/stop"
QLAB_LISTEN_ADDRESS = "/listen"
QLAB_UDP_KEEPALIVE_ADDRESS = "/udpKeepAlive"

DEFAULT_LISTEN_HOST = "127.0.0.1"
DEFAULT_PIXERA_LISTEN_PORT = 8990
DEFAULT_LIGHT_LISTEN_PORT = 7000
DEFAULT_QLAB_HOST = "127.0.0.1"
DEFAULT_QLAB_PORT = 53000
DEFAULT_AVATAR_DONE_HOST = "127.0.0.1"
DEFAULT_AVATAR_DONE_PORT = 8991
DEFAULT_QLAB_FEEDBACK_KEEPALIVE_S = 30.0

logger = logging.getLogger("pixera_qlab_relay")


def qlab_start_address(pixera_address: str, args: list[object]) -> str | None:
    """Map Pixera apply message to QLab start address, or None if not applicable."""
    if pixera_address != PIXERA_APPLY_ADDRESS:
        return None
    if not args:
        return None
    cue_name = args[0]
    if not isinstance(cue_name, str) or not cue_name.strip():
        return None
    return f"/cue/{cue_name.strip()}/start"


def qlab_light_start_addresses(address: str, args: list[object]) -> list[str]:
    """Map light mirror OSC to QLab start addresses (one per scene_id)."""
    if address == LIGHT_BLACKOUT_ADDRESS:
        return ["/cue/blackout/start"]
    if address != LIGHT_SET_SCENE_ADDRESS:
        return []
    if not args:
        return []
    scene_spec = args[0]
    if not isinstance(scene_spec, str) or not scene_spec.strip():
        return []
    scene_ids = [part.strip() for part in scene_spec.split(",") if part.strip()]
    return [f"/cue/{scene_id}/start" for scene_id in scene_ids]


def cue_name_from_qlab_stop(address: str, args: list[object]) -> str | None:
    """Extract cue number/name from a QLab show-control stop event."""
    if not address.endswith(QLAB_CUE_STOP_SUFFIX):
        return None
    if not args:
        return None
    cue = args[0]
    if not isinstance(cue, str) or not cue.strip():
        return None
    return cue.strip()


def build_pixera_handler(qlab_client: SimpleUDPClient):
    def _handler(address: str, *args: object) -> None:
        qlab_address = qlab_start_address(address, list(args))
        if qlab_address is None:
            logger.debug("ignore pixera %s %s", address, args)
            return
        qlab_client.send_message(qlab_address, [])
        logger.info("relay pixera %s %s -> %s", address, args, qlab_address)

    return _handler


def build_light_handler(qlab_client: SimpleUDPClient):
    def _handler(address: str, *args: object) -> None:
        qlab_addresses = qlab_light_start_addresses(address, list(args))
        if not qlab_addresses:
            logger.debug("ignore light %s %s", address, args)
            return
        for qlab_address in qlab_addresses:
            qlab_client.send_message(qlab_address, [])
            logger.info("relay light %s %s -> %s", address, args, qlab_address)

    return _handler


def build_qlab_stop_forwarder(backend_client: SimpleUDPClient):
    """Forward QLab cue/stop show-control events as /avatar/done <cue>."""

    def _forward(address: str, args: list[object]) -> None:
        cue_name = cue_name_from_qlab_stop(address, args)
        if cue_name is None:
            logger.debug("ignore qlab event %s %s", address, args)
            return
        backend_client.send_message(AVATAR_DONE_ADDRESS, [cue_name])
        logger.info("relay qlab stop %s -> %s %s", address, AVATAR_DONE_ADDRESS, cue_name)

    return _forward


# Backwards-compatible alias used in tests.
build_relay_handler = build_pixera_handler


def _assert_udp_port_free(host: str, port: int, label: str) -> None:
    """Fail fast with a helpful message when a relay listener port is taken."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind((host, port))
    except OSError as exc:
        logger.error(
            "Port %s:%s (%s) bereits belegt — alter Relay noch aktiv?\n"
            "  Prüfen: lsof -nP -iUDP:%s\n"
            "  Beenden: kill -9 $(lsof -tiUDP:%s)",
            host,
            port,
            label,
            port,
            port,
        )
        raise SystemExit(1) from exc
    finally:
        probe.close()


def _run_server(
    *,
    listen_host: str,
    listen_port: int,
    dispatcher: Dispatcher,
    label: str,
) -> None:
    server = BlockingOSCUDPServer((listen_host, listen_port), dispatcher)
    logger.info("listening %s (%s:%s)", label, listen_host, listen_port)
    try:
        server.serve_forever()
    except OSError as exc:
        logger.error("failed to bind %s:%s (%s)", listen_host, listen_port, exc)
        raise SystemExit(1) from exc


def _osc_dgram(address: str, *args: object) -> bytes:
    builder = OscMessageBuilder(address=address)
    for arg in args:
        builder.add_arg(arg)
    return builder.build().dgram


def run_qlab_feedback_loop(
    *,
    qlab_host: str,
    qlab_port: int,
    backend_host: str,
    backend_port: int,
    keepalive_s: float,
    stop_event: threading.Event,
) -> None:
    """Subscribe to QLab show-control and forward cue/stop → /avatar/done."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(1.0)
    local_port = sock.getsockname()[1]
    backend = SimpleUDPClient(backend_host, backend_port)
    forward = build_qlab_stop_forwarder(backend)

    def _send_to_qlab(address: str, *args: object) -> None:
        sock.sendto(_osc_dgram(address, *args), (qlab_host, qlab_port))

    _send_to_qlab(QLAB_LISTEN_ADDRESS)
    _send_to_qlab("/listen/cue/stop")
    logger.info(
        "qlab feedback: listening replies on :%s, forwarding stops to %s:%s %s",
        local_port,
        backend_host,
        backend_port,
        AVATAR_DONE_ADDRESS,
    )

    next_keepalive = time.monotonic() + keepalive_s
    try:
        while not stop_event.is_set():
            now = time.monotonic()
            if now >= next_keepalive:
                _send_to_qlab(QLAB_UDP_KEEPALIVE_ADDRESS)
                _send_to_qlab(QLAB_LISTEN_ADDRESS)
                _send_to_qlab("/listen/cue/stop")
                next_keepalive = now + keepalive_s
            try:
                data, _addr = sock.recvfrom(65535)
            except TimeoutError:
                continue
            except OSError:
                break
            try:
                message = OscMessage(data)
            except Exception:
                logger.debug("ignore non-OSC qlab datagram (%s bytes)", len(data))
                continue
            forward(message.address, list(message.params))
    finally:
        sock.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Theatermaschine OSC ↔ QLab OSC relay")
    parser.add_argument(
        "--listen-host",
        default=os.environ.get("PIXERA_LISTEN_HOST", DEFAULT_LISTEN_HOST),
        help="Bind address for Pixera + light listeners",
    )
    parser.add_argument(
        "--listen-port",
        type=int,
        default=int(os.environ.get("PIXERA_LISTEN_PORT", DEFAULT_PIXERA_LISTEN_PORT)),
        help="Pixera listen port (= PIXERA_OSC_PORT in backend/.env)",
    )
    parser.add_argument(
        "--light-listen-port",
        type=int,
        default=int(os.environ.get("LIGHT_LISTEN_PORT", DEFAULT_LIGHT_LISTEN_PORT)),
        help="Light mirror listen port (= OSC_PORT when LIGHT_OSC_MIRROR=true)",
    )
    parser.add_argument(
        "--no-light",
        action="store_true",
        help="Disable light listener (video only)",
    )
    parser.add_argument(
        "--qlab-host",
        default=os.environ.get("QLAB_HOST", DEFAULT_QLAB_HOST),
    )
    parser.add_argument(
        "--qlab-port",
        type=int,
        default=int(os.environ.get("QLAB_PORT", DEFAULT_QLAB_PORT)),
    )
    parser.add_argument(
        "--avatar-done-host",
        default=os.environ.get("AVATAR_DONE_HOST", DEFAULT_AVATAR_DONE_HOST),
        help="Theatermaschine avatar-done listener host",
    )
    parser.add_argument(
        "--avatar-done-port",
        type=int,
        default=int(os.environ.get("AVATAR_DONE_PORT", DEFAULT_AVATAR_DONE_PORT)),
        help="Theatermaschine avatar-done listener port (= AVATAR_DONE_OSC_PORT)",
    )
    parser.add_argument(
        "--no-qlab-feedback",
        action="store_true",
        help="Disable QLab show-control → /avatar/done forwarding",
    )
    parser.add_argument(
        "--qlab-feedback-keepalive",
        type=float,
        default=float(
            os.environ.get("QLAB_FEEDBACK_KEEPALIVE_S", DEFAULT_QLAB_FEEDBACK_KEEPALIVE_S)
        ),
        help="Re-send /listen + /udpKeepAlive interval (seconds)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    qlab_client = SimpleUDPClient(args.qlab_host, args.qlab_port)

    pixera_dispatcher = Dispatcher()
    pixera_dispatcher.map(
        PIXERA_APPLY_ADDRESS,
        build_pixera_handler(qlab_client),
        needs_reply_address=False,
    )

    threads: list[threading.Thread] = []
    stop_event = threading.Event()
    threads.append(
        threading.Thread(
            target=_run_server,
            kwargs={
                "listen_host": args.listen_host,
                "listen_port": args.listen_port,
                "dispatcher": pixera_dispatcher,
                "label": "pixera",
            },
            daemon=True,
        )
    )

    if not args.no_light:
        light_dispatcher = Dispatcher()
        light_handler = build_light_handler(qlab_client)
        light_dispatcher.map(LIGHT_SET_SCENE_ADDRESS, light_handler, needs_reply_address=False)
        light_dispatcher.map(LIGHT_BLACKOUT_ADDRESS, light_handler, needs_reply_address=False)
        threads.append(
            threading.Thread(
                target=_run_server,
                kwargs={
                    "listen_host": args.listen_host,
                    "listen_port": args.light_listen_port,
                    "dispatcher": light_dispatcher,
                    "label": "light",
                },
                daemon=True,
            )
        )

    if not args.no_qlab_feedback:
        threads.append(
            threading.Thread(
                target=run_qlab_feedback_loop,
                kwargs={
                    "qlab_host": args.qlab_host,
                    "qlab_port": args.qlab_port,
                    "backend_host": args.avatar_done_host,
                    "backend_port": args.avatar_done_port,
                    "keepalive_s": max(5.0, args.qlab_feedback_keepalive),
                    "stop_event": stop_event,
                },
                daemon=True,
                name="qlab-feedback",
            )
        )

    _assert_udp_port_free(args.listen_host, args.listen_port, "pixera")
    if not args.no_light:
        _assert_udp_port_free(args.listen_host, args.light_listen_port, "light")

    logger.info(
        "forwarding to QLab %s:%s (pixera :%s%s%s)",
        args.qlab_host,
        args.qlab_port,
        args.listen_port,
        "" if args.no_light else f", light :{args.light_listen_port}",
        ""
        if args.no_qlab_feedback
        else f", feedback → {args.avatar_done_host}:{args.avatar_done_port}",
    )

    def _shutdown(_signum: int, _frame: object) -> None:
        logger.info("shutting down")
        stop_event.set()
        sys.exit(0)

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
