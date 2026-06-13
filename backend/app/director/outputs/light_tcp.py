import json
import socket
import struct
import threading
import time

from app.core.config import settings

_SESSION_COMMANDS = frozenset({"connect", "disconnect"})


def build_light_message(
    command: str,
    *,
    scene_id: str | None = None,
    fade_time: float = 4.0,
    channels: list[str] | None = None,
) -> str:
    payload: dict[str, object] = {
        "protocol": settings.light_tcp_protocol,
        "command": command,
    }
    if command not in _SESSION_COMMANDS:
        payload["fade_time"] = fade_time
    if scene_id is not None:
        payload["scene_id"] = scene_id
    if channels:
        payload["channels"] = channels
    return json.dumps(payload, ensure_ascii=False) + "\n"


def build_light_osc_message(address: str, args: list[object] | None = None) -> str:
    payload: dict[str, object] = {
        "protocol": settings.light_tcp_protocol,
        "command": "osc",
        "address": address,
        "args": list(args or []),
    }
    return json.dumps(payload, ensure_ascii=False) + "\n"


def slip_encode(packet: bytes) -> bytes:
    """RFC 1055 SLIP framing for EOS OSC 1.1 TCP mode."""
    out = bytearray([0xC0])
    for byte in packet:
        if byte == 0xC0:
            out.extend((0xDB, 0xDC))
        elif byte == 0xDB:
            out.extend((0xDB, 0xDD))
        else:
            out.append(byte)
    out.append(0xC0)
    return bytes(out)


def encode_osc_binary(address: str, args: list[object]) -> bytes:
    from pythonosc.osc_message_builder import OscMessageBuilder

    builder = OscMessageBuilder(address=address)
    for arg in args:
        if isinstance(arg, bool):
            builder.add_arg(arg)
        elif isinstance(arg, int):
            builder.add_arg(arg)
        elif isinstance(arg, float):
            builder.add_arg(arg)
        elif isinstance(arg, bytes):
            builder.add_arg(arg)
        elif isinstance(arg, str):
            builder.add_arg(arg)
        else:
            builder.add_arg(str(arg))
    msg = builder.build()
    packet = msg.dgram if isinstance(msg.dgram, bytes) else msg.dgram()
    framing = settings.light_osc_tcp_framing
    if framing == "length_prefix":
        return struct.pack(">I", len(packet)) + packet
    if framing == "slip":
        return slip_encode(packet)
    return packet


def describe_tcp_osc_payload(payload: bytes) -> str:
    return f"{settings.light_osc_tcp_format}+{settings.light_osc_tcp_framing} {len(payload)}B"


def build_osc_tcp_payload(address: str, args: list[object]) -> bytes:
    if settings.light_osc_tcp_format == "binary":
        return encode_osc_binary(address, args)
    message = build_light_osc_message(address, args)
    payload = message.encode("utf-8")
    if settings.light_osc_tcp_framing == "length_prefix":
        return struct.pack(">I", len(payload)) + payload
    if settings.light_osc_tcp_framing == "slip":
        return slip_encode(payload)
    return payload


class LightTcpSession:
    """TCP 1.0 session to the venue desk — connect, then EOS OSC on the same socket."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conn: socket.socket | None = None
        self._session_open = False

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._session_open

    def open_session(self, *, dry_run: bool = False) -> None:
        host = settings.light_tcp_host
        port = settings.light_tcp_port
        use_json = settings.light_tcp_handshake == "json"
        message = build_light_message("connect") if use_json else None

        from app.director.outputs.osc_log import log_osc_command

        log_address = "tcp/connect" if use_json else "tcp/connect (EOS socket)"
        log_args: list[object] = [message.strip()] if message else []
        log_osc_command(
            host,
            port,
            log_address,
            log_args,
            dry_run=dry_run,
            bridge="light",
        )
        if dry_run:
            with self._lock:
                self._session_open = True
            return

        with self._lock:
            if self._session_open and self._conn is not None:
                return
            self._ensure_connected_unlocked()
            assert self._conn is not None
            if use_json and message is not None:
                self._conn.sendall(message.encode("utf-8"))
                if settings.light_tcp_read_ack:
                    self._read_ack_unlocked()
            delay = settings.light_tcp_connect_delay
            if delay > 0:
                time.sleep(delay)
            self._session_open = True

    def send_osc(
        self,
        address: str,
        args: list[object] | None = None,
        *,
        dry_run: bool = False,
    ) -> None:
        host = settings.light_tcp_host
        port = settings.light_tcp_port
        payload = build_osc_tcp_payload(address, list(args or []))
        transport = describe_tcp_osc_payload(payload)

        from app.director.outputs.osc_log import log_osc_command

        log_osc_command(
            host,
            port,
            f"tcp/osc {transport} {address}",
            list(args or []),
            dry_run=dry_run,
            bridge="light",
        )
        if dry_run:
            return

        with self._lock:
            if not self._session_open:
                raise RuntimeError("Light desk TCP session not connected")
            if self._conn is None:
                raise RuntimeError("Light desk TCP socket not available")
            self._conn.sendall(payload)
        delay = settings.light_osc_send_delay
        if delay > 0:
            time.sleep(delay)

    def close_session(self, *, dry_run: bool = False) -> None:
        host = settings.light_tcp_host
        port = settings.light_tcp_port
        use_json = settings.light_tcp_handshake == "json"
        message = build_light_message("disconnect") if use_json else None

        from app.director.outputs.osc_log import log_osc_command

        log_address = "tcp/disconnect" if use_json else "tcp/disconnect (EOS socket)"
        log_args: list[object] = [message.strip()] if message else []
        log_osc_command(
            host,
            port,
            log_address,
            log_args,
            dry_run=dry_run,
            bridge="light",
        )
        if dry_run:
            with self._lock:
                self._session_open = False
            return

        with self._lock:
            if self._conn is None:
                self._session_open = False
                return
            if use_json and message is not None:
                try:
                    self._conn.sendall(message.encode("utf-8"))
                except OSError:
                    pass
            self._close_unlocked()
            self._session_open = False

    def close(self) -> None:
        with self._lock:
            self._close_unlocked()
            self._session_open = False

    def _read_ack_unlocked(self) -> str | None:
        if self._conn is None:
            return None
        timeout = settings.light_tcp_ack_timeout
        previous = self._conn.gettimeout()
        try:
            self._conn.settimeout(timeout)
            data = self._conn.recv(4096)
            if not data:
                return None
            return data.decode("utf-8", errors="replace").strip()
        except (OSError, socket.timeout):
            return None
        finally:
            self._conn.settimeout(previous)

    def _ensure_connected_unlocked(self) -> None:
        if self._conn is not None:
            return
        conn = socket.create_connection(
            (settings.light_tcp_host, settings.light_tcp_port),
            timeout=settings.light_tcp_timeout,
        )
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self._conn = conn

    def _close_unlocked(self) -> None:
        if self._conn is None:
            return
        try:
            conn = self._conn
            self._conn = None
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            conn.close()
        except OSError:
            pass


_session = LightTcpSession()


def get_light_tcp_session() -> LightTcpSession:
    return _session


def close_light_tcp() -> None:
    _session.close()
