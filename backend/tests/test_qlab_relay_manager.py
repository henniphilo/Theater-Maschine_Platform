"""Tests for QLab OSC relay manager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.director.output_targets import apply_overrides
from app.director.qlab_relay_manager import (
    QlabRelayConfig,
    QlabRelayManager,
    _prepare_relay_listen,
    get_qlab_relay_manager,
)


@pytest.fixture
def relay_manager() -> QlabRelayManager:
    import app.director.qlab_relay_manager as mod

    mod._manager = None
    manager = get_qlab_relay_manager()
    yield manager
    manager.stop()
    mod._manager = None


def _sample_config() -> QlabRelayConfig:
    return QlabRelayConfig(
        listen_host="127.0.0.1",
        pixera_listen_port=18990,
        light_listen_port=17000,
        light_listener_enabled=True,
        qlab_host="127.0.0.1",
        qlab_port=53000,
        feedback_enabled=False,
        avatar_done_host="127.0.0.1",
        avatar_done_port=18991,
    )


def _stage_config() -> QlabRelayConfig:
    return QlabRelayConfig(
        listen_host="172.27.27.1",
        pixera_listen_port=18990,
        light_listen_port=17000,
        light_listener_enabled=True,
        qlab_host="127.0.0.1",
        qlab_port=53000,
        feedback_enabled=False,
        avatar_done_host="127.0.0.1",
        avatar_done_port=18991,
    )


@patch("app.director.qlab_relay_manager.relay_config", return_value=_sample_config())
@patch("app.director.qlab_relay_manager._relay_script_path")
@patch("app.director.qlab_relay_manager._udp_port_in_use", return_value=False)
@patch("app.director.qlab_relay_manager.subprocess.Popen")
def test_relay_start_and_stop(
    mock_popen: MagicMock,
    _mock_port: MagicMock,
    mock_script: MagicMock,
    _mock_config: MagicMock,
    relay_manager: QlabRelayManager,
) -> None:
    mock_script.return_value = MagicMock(is_file=lambda: True, __str__=lambda _s: "/repo/tools/pixera_qlab_relay.py")
    proc = MagicMock()
    proc.poll.return_value = None
    proc.pid = 4242
    proc.stderr = None
    mock_popen.return_value = proc

    started = relay_manager.start()
    assert started.managed is True
    assert started.running is True
    assert started.pid == 4242

    stopped = relay_manager.stop()
    assert stopped.managed is False
    proc.send_signal.assert_called_once()


@patch("app.director.qlab_relay_manager.relay_config", return_value=_sample_config())
@patch("app.director.qlab_relay_manager._udp_port_in_use", return_value=True)
def test_relay_start_reports_port_conflict(
    _mock_port: MagicMock,
    _mock_config: MagicMock,
    relay_manager: QlabRelayManager,
) -> None:
    result = relay_manager.start()
    assert result.running is True
    assert result.managed is False
    assert result.error
    assert "belegt" in result.error


@patch("app.director.qlab_relay_manager.relay_config", return_value=_sample_config())
@patch("app.director.qlab_relay_manager._relay_script_path")
@patch("app.director.qlab_relay_manager._udp_port_in_use", return_value=False)
@patch("app.director.qlab_relay_manager.subprocess.Popen")
def test_relay_start_idempotent_when_already_running(
    mock_popen: MagicMock,
    _mock_port: MagicMock,
    mock_script: MagicMock,
    _mock_config: MagicMock,
    relay_manager: QlabRelayManager,
) -> None:
    mock_script.return_value = MagicMock(is_file=lambda: True, __str__=lambda _s: "/repo/tools/pixera_qlab_relay.py")
    proc = MagicMock()
    proc.poll.return_value = None
    proc.pid = 99
    proc.stderr = None
    mock_popen.return_value = proc

    relay_manager.start()
    again = relay_manager.start()
    assert again.managed is True
    assert mock_popen.call_count == 1


@patch("app.director.qlab_relay_manager._can_bind_udp")
@patch("app.director.qlab_relay_manager.relay_config")
def test_prepare_relay_listen_falls_back_to_localhost(
    mock_relay_config: MagicMock,
    mock_can_bind: MagicMock,
) -> None:
    apply_overrides(reset=True)
    stage = _stage_config()
    local = _sample_config()
    mock_relay_config.return_value = local

    def bind_ok(host: str, port: int) -> bool:
        return host == "127.0.0.1"

    mock_can_bind.side_effect = bind_ok

    config, notice, error = _prepare_relay_listen(stage)
    assert error is None
    assert notice
    assert "172.27.27.1" in notice
    assert config.listen_host == "127.0.0.1"
    apply_overrides(reset=True)


@patch("app.director.qlab_relay_manager.relay_config")
@patch("app.director.qlab_relay_manager._can_bind_udp", return_value=False)
def test_prepare_relay_listen_reports_unbindable_host(
    _mock_can_bind: MagicMock,
    mock_relay_config: MagicMock,
) -> None:
    mock_relay_config.return_value = _stage_config()
    config, notice, error = _prepare_relay_listen(_stage_config())
    assert notice is None
    assert error
    assert "172.27.27.1" in error
    assert "127.0.0.1" in error
