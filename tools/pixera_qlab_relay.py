#!/usr/bin/env python3
"""Translate Theatermaschine OSC to QLab (/cue/{name}/start).

Video: Pixera /pixera/args/cue/apply on PIXERA_LISTEN_PORT (default 8990).
Light:  /light/set_scene and /light/blackout on LIGHT_LISTEN_PORT (default 7000)
        when LIGHT_OSC_MIRROR=true in backend/.env.

Forwards to QLab on QLAB_PORT (default 53000).
See docs/qlab_setup.md for workspace and .env configuration.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import sys
import threading

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

PIXERA_APPLY_ADDRESS = "/pixera/args/cue/apply"
LIGHT_SET_SCENE_ADDRESS = "/light/set_scene"
LIGHT_BLACKOUT_ADDRESS = "/light/blackout"

DEFAULT_LISTEN_HOST = "127.0.0.1"
DEFAULT_PIXERA_LISTEN_PORT = 8990
DEFAULT_LIGHT_LISTEN_PORT = 7000
DEFAULT_QLAB_HOST = "127.0.0.1"
DEFAULT_QLAB_PORT = 53000

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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Theatermaschine OSC → QLab OSC relay")
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

    _assert_udp_port_free(args.listen_host, args.listen_port, "pixera")
    if not args.no_light:
        _assert_udp_port_free(args.listen_host, args.light_listen_port, "light")

    logger.info(
        "forwarding to QLab %s:%s (pixera :%s%s)",
        args.qlab_host,
        args.qlab_port,
        args.listen_port,
        "" if args.no_light else f", light :{args.light_listen_port}",
    )

    def _shutdown(_signum: int, _frame: object) -> None:
        logger.info("shutting down")
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
