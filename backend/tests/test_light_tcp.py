import json
import struct
from unittest.mock import MagicMock, patch

import pytest

from app.director.outputs.light_tcp import (
    LightTcpSession,
    build_light_message,
    build_light_osc_message,
    close_light_tcp,
    encode_osc_binary,
    get_light_tcp_session,
)


def test_build_connect_message_protocol_1_0() -> None:
    message = build_light_message("connect")
    payload = json.loads(message.strip())
    assert payload == {"protocol": "1.0", "command": "connect"}


def test_build_set_scene_message() -> None:
    message = build_light_message("set_scene", scene_id="kuh", fade_time=4.0)
    payload = json.loads(message.strip())
    assert payload["command"] == "set_scene"
    assert payload["scene_id"] == "kuh"


def test_build_light_osc_message_protocol_1_0() -> None:
    message = build_light_osc_message("/eos/chan/6/full", [])
    payload = json.loads(message.strip())
    assert payload == {
        "protocol": "1.0",
        "command": "osc",
        "address": "/eos/chan/6/full",
        "args": [],
    }


def test_encode_osc_binary_uses_length_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.director.outputs.light_tcp.settings.light_osc_tcp_framing", "length_prefix")
    packet = encode_osc_binary("/eos/chan/16/full", [])
    size, body = struct.unpack(">I", packet[:4])[0], packet[4:]
    assert size == len(body)
    assert b"/eos/chan/16/full" in body


@patch("app.director.outputs.light_tcp.time.sleep")
@patch("app.director.outputs.light_tcp.socket.create_connection")
def test_open_session_eos_native_opens_socket_only(
    mock_conn: MagicMock,
    _sleep: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.director.outputs.light_tcp.settings.light_tcp_handshake", "none")
    close_light_tcp()
    sock = MagicMock()
    mock_conn.return_value = sock
    session = LightTcpSession()

    session.open_session(dry_run=False)

    sock.sendall.assert_not_called()
    assert session.connected is True
    close_light_tcp()


@patch("app.director.outputs.light_tcp.time.sleep")
@patch("app.director.outputs.light_tcp.socket.create_connection")
def test_open_session_json_handshake_sends_connect(
    mock_conn: MagicMock,
    _sleep: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.director.outputs.light_tcp.settings.light_tcp_handshake", "json")
    monkeypatch.setattr("app.director.outputs.light_tcp.settings.light_tcp_read_ack", False)
    close_light_tcp()
    sock = MagicMock()
    mock_conn.return_value = sock
    session = LightTcpSession()

    session.open_session(dry_run=False)

    sock.sendall.assert_called_once()
    sent = sock.sendall.call_args[0][0].decode("utf-8")
    assert "connect" in sent
    assert session.connected is True
    close_light_tcp()


@patch("app.director.outputs.light_tcp.time.sleep")
@patch("app.director.outputs.light_tcp.socket.create_connection")
def test_send_osc_writes_binary_packet_on_tcp(
    mock_conn: MagicMock,
    _sleep: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.director.outputs.light_tcp.settings.light_tcp_handshake", "none")
    monkeypatch.setattr("app.director.outputs.light_tcp.settings.light_osc_tcp_format", "binary")
    monkeypatch.setattr("app.director.outputs.light_tcp.settings.light_osc_tcp_framing", "length_prefix")
    monkeypatch.setattr("app.director.outputs.light_tcp.settings.light_osc_send_delay", 0.0)
    close_light_tcp()
    sock = MagicMock()
    mock_conn.return_value = sock
    session = LightTcpSession()
    session.open_session(dry_run=False)

    session.send_osc("/eos/chan/6/full", [])

    osc_call = sock.sendall.call_args_list[-1][0][0]
    size = struct.unpack(">I", osc_call[:4])[0]
    assert size == len(osc_call[4:])
    assert b"/eos/chan/6/full" in osc_call
    close_light_tcp()


@patch("app.director.outputs.light_tcp.socket.create_connection")
def test_close_session_json_handshake_sends_disconnect(
    mock_conn: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.director.outputs.light_tcp.settings.light_tcp_handshake", "json")
    monkeypatch.setattr("app.director.outputs.light_tcp.settings.light_tcp_read_ack", False)
    close_light_tcp()
    sock = MagicMock()
    mock_conn.return_value = sock
    session = get_light_tcp_session()
    session.open_session(dry_run=False)

    session.close_session(dry_run=False)

    disconnect_call = sock.sendall.call_args_list[-1][0][0].decode("utf-8")
    assert "disconnect" in disconnect_call
    assert session.connected is False
