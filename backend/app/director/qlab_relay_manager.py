"""Manage pixera_qlab_relay subprocess from Technik UI."""

from __future__ import annotations

import logging
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QlabRelayConfig:
    listen_host: str
    pixera_listen_port: int
    light_listen_port: int
    light_listener_enabled: bool
    qlab_host: str
    qlab_port: int
    feedback_enabled: bool
    avatar_done_host: str
    avatar_done_port: int


_LOCALHOST = "127.0.0.1"


@dataclass
class QlabRelayStatus:
    running: bool
    managed: bool
    pid: int | None = None
    listen_host: str = "127.0.0.1"
    pixera_listen_port: int = 8990
    light_listen_port: int = 7000
    light_listener_enabled: bool = True
    qlab_host: str = "127.0.0.1"
    qlab_port: int = 53000
    feedback_enabled: bool = False
    error: str | None = None
    notice: str | None = None


class QlabRelayError(RuntimeError):
    pass


def _repo_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "tools" / "pixera_qlab_relay.py").is_file():
        return cwd
    if cwd.name == "backend" and (cwd.parent / "tools" / "pixera_qlab_relay.py").is_file():
        return cwd.parent
    backend_root = Path(__file__).resolve().parents[2]
    candidate = backend_root.parent / "tools" / "pixera_qlab_relay.py"
    if candidate.is_file():
        return backend_root.parent
    raise QlabRelayError("pixera_qlab_relay.py nicht gefunden — nur im Repo-Root verfügbar")


def _relay_script_path() -> Path:
    path = _repo_root() / "tools" / "pixera_qlab_relay.py"
    if not path.is_file():
        raise QlabRelayError("pixera_qlab_relay.py nicht gefunden")
    return path


def _can_bind_udp(host: str, port: int) -> bool:
    return _udp_bind_error(host, port) is None


def _udp_bind_error(host: str, port: int) -> str | None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind((host, port))
        return None
    except OSError as exc:
        return str(exc)
    finally:
        probe.close()


def _udp_port_in_use(host: str, port: int) -> bool:
    err = _udp_bind_error(host, port)
    if err is None:
        return False
    lowered = err.lower()
    return "already in use" in lowered or "address already in use" in lowered


def _relay_bind_ok(config: QlabRelayConfig) -> bool:
    if not _can_bind_udp(config.listen_host, config.pixera_listen_port):
        return False
    if config.light_listener_enabled and not _can_bind_udp(
        config.listen_host, config.light_listen_port
    ):
        return False
    return True


def _prepare_relay_listen(
    config: QlabRelayConfig,
) -> tuple[QlabRelayConfig, str | None, str | None]:
    """Ensure relay listen addresses are bindable. Returns (config, notice, error)."""
    if _relay_bind_ok(config):
        return config, None, None

    original_host = config.listen_host
    if original_host != _LOCALHOST:
        from app.director.output_targets import apply_overrides, refresh_pipeline_targets

        apply_overrides(video_host=_LOCALHOST)
        if config.light_listener_enabled:
            apply_overrides(light_host=_LOCALHOST)
        refresh_pipeline_targets()
        config = relay_config()
        if _relay_bind_ok(config):
            notice = (
                f"Bühnen-IP {original_host} ist lokal nicht verfügbar — "
                f"Relay und OSC-Ziele auf {_LOCALHOST} umgestellt."
            )
            return config, notice, None

    if _udp_port_in_use(config.listen_host, config.pixera_listen_port):
        err = (
            f"Port {config.listen_host}:{config.pixera_listen_port} "
            f"oder :{config.light_listen_port} bereits belegt — Relay läuft bereits?"
        )
    elif not _can_bind_udp(config.listen_host, config.pixera_listen_port):
        err = (
            f"Relay kann nicht auf {config.listen_host}:{config.pixera_listen_port} binden "
            f"(Adresse auf diesem Mac nicht verfügbar). "
            f"Für lokalen QLab-Test: PIXERA_OSC_HOST=127.0.0.1 in backend/.env "
            f"oder Video-IP in Technik auf 127.0.0.1 setzen."
        )
    else:
        err = (
            f"Relay kann Licht-Port {config.listen_host}:{config.light_listen_port} "
            f"nicht binden — Port belegt oder Adresse nicht verfügbar."
        )
    return config, None, err


def relay_config() -> QlabRelayConfig:
    from app.director.output_targets import effective_light_target, effective_video_target

    video_host, video_port = effective_video_target()
    _light_host, light_port = effective_light_target()
    light_enabled = settings.light_uses_preview_osc()
    feedback_enabled = settings.avatar_done_gate_enabled
    return QlabRelayConfig(
        listen_host=video_host,
        pixera_listen_port=video_port,
        light_listen_port=light_port,
        light_listener_enabled=light_enabled,
        qlab_host=settings.qlab_host,
        qlab_port=settings.qlab_port,
        feedback_enabled=feedback_enabled,
        avatar_done_host=settings.avatar_done_osc_host,
        avatar_done_port=settings.avatar_done_osc_port,
    )


def _status_from_config(
    config: QlabRelayConfig,
    *,
    running: bool,
    managed: bool,
    pid: int | None,
    error: str | None,
    notice: str | None = None,
) -> QlabRelayStatus:
    return QlabRelayStatus(
        running=running,
        managed=managed,
        pid=pid,
        listen_host=config.listen_host,
        pixera_listen_port=config.pixera_listen_port,
        light_listen_port=config.light_listen_port,
        light_listener_enabled=config.light_listener_enabled,
        qlab_host=config.qlab_host,
        qlab_port=config.qlab_port,
        feedback_enabled=config.feedback_enabled,
        error=error,
        notice=notice,
    )


class QlabRelayManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._last_error: str | None = None
        self._last_notice: str | None = None

    def status(self) -> QlabRelayStatus:
        config = relay_config()
        with self._lock:
            proc = self._process
            last_error = self._last_error
            last_notice = self._last_notice

        managed_running = proc is not None and proc.poll() is None
        if proc is not None and not managed_running:
            last_error = last_error or self._read_process_error(proc)

        external_running = self._relay_ports_in_use(config)
        running = managed_running or external_running
        return _status_from_config(
            config,
            running=running,
            managed=managed_running,
            pid=proc.pid if managed_running and proc else None,
            error=None if managed_running else last_error,
            notice=last_notice if managed_running else None,
        )

    def start(self) -> QlabRelayStatus:
        config = relay_config()
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return _status_from_config(
                    config,
                    running=True,
                    managed=True,
                    pid=self._process.pid,
                    error=None,
                    notice=self._last_notice,
                )

        config, notice, prep_error = _prepare_relay_listen(config)
        if prep_error:
            with self._lock:
                self._last_error = prep_error
                self._last_notice = None
            return _status_from_config(
                config,
                running=self._relay_ports_in_use(config),
                managed=False,
                pid=None,
                error=prep_error,
            )

        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return _status_from_config(
                    config,
                    running=True,
                    managed=True,
                    pid=self._process.pid,
                    error=None,
                    notice=self._last_notice,
                )

            if self._relay_ports_in_use(config):
                self._last_error = (
                    f"Port {config.listen_host}:{config.pixera_listen_port} "
                    f"oder :{config.light_listen_port} bereits belegt — Relay läuft bereits?"
                )
                self._last_notice = None
                return _status_from_config(
                    config,
                    running=True,
                    managed=False,
                    pid=None,
                    error=self._last_error,
                )

            cmd = self._build_command(config)
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
                )
            except OSError as exc:
                self._last_error = f"Relay konnte nicht gestartet werden: {exc}"
                logger.exception("qlab relay start failed")
                return _status_from_config(
                    config,
                    running=False,
                    managed=False,
                    pid=None,
                    error=self._last_error,
                )

            self._last_error = None
            self._last_notice = notice
            proc = self._process

        time.sleep(0.35)
        with self._lock:
            proc = self._process

        if proc is None or proc.poll() is not None:
            err = self._read_process_error(proc) if proc else "Relay-Prozess unbekannt beendet"
            with self._lock:
                self._last_error = err
                self._process = None
            return _status_from_config(
                config,
                running=self._relay_ports_in_use(config),
                managed=False,
                pid=None,
                error=err,
            )

        logger.info("qlab relay started pid=%s cmd=%s", proc.pid, " ".join(cmd))
        return self.status()

    def stop(self) -> QlabRelayStatus:
        with self._lock:
            proc = self._process
            self._process = None

        if proc is not None and proc.poll() is None:
            try:
                proc.send_signal(signal.SIGTERM)
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1)
            except OSError as exc:
                with self._lock:
                    self._last_error = f"Relay stop fehlgeschlagen: {exc}"
                logger.warning("qlab relay stop failed: %s", exc)

        with self._lock:
            if proc is not None and proc.poll() is not None:
                self._last_error = None
                self._last_notice = None

        return self.status()

    def _build_command(self, config: QlabRelayConfig) -> list[str]:
        cmd = [
            sys.executable,
            str(_relay_script_path()),
            "--listen-host",
            config.listen_host,
            "--listen-port",
            str(config.pixera_listen_port),
            "--light-listen-port",
            str(config.light_listen_port),
            "--qlab-host",
            config.qlab_host,
            "--qlab-port",
            str(config.qlab_port),
            "--avatar-done-host",
            config.avatar_done_host,
            "--avatar-done-port",
            str(config.avatar_done_port),
        ]
        if not config.light_listener_enabled:
            cmd.append("--no-light")
        if not config.feedback_enabled:
            cmd.append("--no-qlab-feedback")
        return cmd

    @staticmethod
    def _read_process_error(proc: subprocess.Popen[str]) -> str:
        stderr = ""
        if proc.stderr:
            try:
                stderr = (proc.stderr.read() or "").strip()
            except Exception:
                pass
        if stderr:
            return stderr[:500]
        code = proc.returncode
        return f"Relay-Prozess beendet (exit {code})" if code is not None else "Relay-Prozess beendet"

    @staticmethod
    def _relay_ports_in_use(config: QlabRelayConfig) -> bool:
        if _udp_port_in_use(config.listen_host, config.pixera_listen_port):
            return True
        if config.light_listener_enabled and _udp_port_in_use(
            config.listen_host, config.light_listen_port
        ):
            return True
        return False


_manager: QlabRelayManager | None = None


def get_qlab_relay_manager() -> QlabRelayManager:
    global _manager
    if _manager is None:
        _manager = QlabRelayManager()
    return _manager
