"""Tests for tools/pixera_qlab_relay.py mapping and UDP forwarding."""

from __future__ import annotations

import importlib.util
import socket
import threading
import time
from pathlib import Path

from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

ROOT = Path(__file__).resolve().parents[2]
RELAY_PATH = ROOT / "tools" / "pixera_qlab_relay.py"


def _load_relay_module():
    spec = importlib.util.spec_from_file_location("pixera_qlab_relay", RELAY_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


relay = _load_relay_module()


def test_qlab_start_address_maps_pixera_cue() -> None:
    assert relay.qlab_start_address("/pixera/args/cue/apply", ["KI_RZ21.Clyde"]) == "/cue/KI_RZ21.Clyde/start"


def test_qlab_start_address_ignores_other_addresses() -> None:
    assert relay.qlab_start_address("/visual/play_clip", ["clyde"]) is None


def test_qlab_start_address_requires_non_empty_string() -> None:
    assert relay.qlab_start_address("/pixera/args/cue/apply", []) is None
    assert relay.qlab_start_address("/pixera/args/cue/apply", ["  "]) is None
    assert relay.qlab_start_address("/pixera/args/cue/apply", [123]) is None


def test_relay_handler_forwards_to_qlab_client() -> None:
    sent: list[tuple[str, list[object]]] = []

    class _FakeClient:
        def send_message(self, address: str, args: list[object]) -> None:
            sent.append((address, args))

    handler = relay.build_relay_handler(_FakeClient())
    handler("/pixera/args/cue/apply", "KI_RZ21.Clyde")
    assert sent == [("/cue/KI_RZ21.Clyde/start", [])]


def test_qlab_light_start_addresses_maps_single_scene() -> None:
    assert relay.qlab_light_start_addresses("/light/set_scene", ["saallicht", 4.0]) == [
        "/cue/saallicht/start"
    ]


def test_qlab_light_start_addresses_maps_multiple_scenes() -> None:
    assert relay.qlab_light_start_addresses(
        "/light/set_scene",
        ["saallicht,gegenlicht_weich", 4.0],
    ) == ["/cue/saallicht/start", "/cue/gegenlicht_weich/start"]


def test_qlab_light_start_addresses_maps_blackout() -> None:
    assert relay.qlab_light_start_addresses("/light/blackout", []) == ["/cue/blackout/start"]


def test_light_handler_forwards_all_scenes_to_qlab_client() -> None:
    sent: list[tuple[str, list[object]]] = []

    class _FakeClient:
        def send_message(self, address: str, args: list[object]) -> None:
            sent.append((address, args))

    handler = relay.build_light_handler(_FakeClient())
    handler("/light/set_scene", "saallicht,gegenlicht_weich", 4.0)
    assert sent == [
        ("/cue/saallicht/start", []),
        ("/cue/gegenlicht_weich/start", []),
    ]


def test_relay_forwards_pixera_to_qlab_format() -> None:
    received: list[tuple[str, list[object]]] = []
    lock = threading.Lock()

    def _capture(address: str, *args: object) -> None:
        with lock:
            received.append((address, list(args)))

    dispatcher = Dispatcher()
    dispatcher.set_default_handler(_capture)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    listen_port = sock.getsockname()[1]
    sock.close()

    server = BlockingOSCUDPServer(("127.0.0.1", listen_port), dispatcher)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    relay_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    relay_sock.bind(("127.0.0.1", 0))
    relay_port = relay_sock.getsockname()[1]
    relay_sock.close()

    relay_thread = threading.Thread(
        target=lambda: relay.main(
            [
                "--listen-port",
                str(relay_port),
                "--qlab-port",
                str(listen_port),
            ]
        ),
        daemon=True,
    )
    relay_thread.start()
    time.sleep(0.15)

    client = udp_client.SimpleUDPClient("127.0.0.1", relay_port)
    client.send_message("/pixera/args/cue/apply", ["KI_RZ21.Clyde"])

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        with lock:
            if received:
                break
        time.sleep(0.02)

    server.shutdown()
    thread.join(timeout=1.0)

    assert received == [("/cue/KI_RZ21.Clyde/start", [])]
