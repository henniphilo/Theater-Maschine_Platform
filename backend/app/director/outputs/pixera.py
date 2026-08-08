from pythonosc import udp_client

from app.core.config import settings
from app.director.output_targets import effective_video_target, effective_video_targets
from app.director.outputs.osc_log import log_osc_command
from app.director.outputs.udp_client import create_udp_client


class PixeraBridge:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        hosts: list[tuple[str, int]] | None = None,
        dry_run: bool | None = None,
    ) -> None:
        if hosts is not None:
            self._targets = [(h, p) for h, p in hosts if h]
        elif host is not None:
            resolved_port = port if port is not None else effective_video_target()[1]
            self._targets = [(host, resolved_port)]
        else:
            self._targets = list(effective_video_targets())
        if not self._targets:
            self._targets = [effective_video_target()]
        # Primary target kept for adapters / status that expect a single host.
        self.host = self._targets[0][0]
        self.port = self._targets[0][1]
        self.dry_run = settings.osc_dry_run if dry_run is None else dry_run
        self._clients: list[tuple[str, int, udp_client.SimpleUDPClient | None]] = []
        self._rebuild_clients()

    def _rebuild_clients(self) -> None:
        self._clients = []
        for host, port in self._targets:
            client = None if self.dry_run else create_udp_client(host, port)
            self._clients.append((host, port, client))

    @property
    def targets(self) -> list[tuple[str, int]]:
        return list(self._targets)

    def _send(self, address: str, *args: object) -> None:
        for host, port, client in self._clients:
            dry_run = self.dry_run or client is None
            log_osc_command(
                host,
                port,
                address,
                list(args),
                dry_run=dry_run,
                bridge="pixera",
            )
            if dry_run:
                continue
            client.send_message(address, list(args))

    def reconfigure(
        self,
        host: str | None = None,
        port: int | None = None,
        hosts: list[tuple[str, int]] | None = None,
    ) -> None:
        if hosts is not None:
            self._targets = [(h, p) for h, p in hosts if h] or list(effective_video_targets())
        elif host is not None:
            resolved_port = port if port is not None else self.port
            self._targets = [(host, resolved_port)]
        elif port is not None:
            self._targets = [(h, port) for h, _ in self._targets]
        self.host = self._targets[0][0]
        self.port = self._targets[0][1]
        self._rebuild_clients()

    def apply_cue(self, pixera_cue_name: str) -> None:
        self._send("/pixera/args/cue/apply", pixera_cue_name)
        self._note_avatar_done_expectation(pixera_cue_name)

    def _note_avatar_done_expectation(self, pixera_cue_name: str) -> None:
        """Venue Pixera path (Option A): cue end must send /avatar/done back.

        Backend already listens for /avatar/done. This emits a trace hint so operators
        can verify that Pixera timelines are wired to the same cue name.
        """
        if not settings.avatar_done_gate_enabled:
            return
        if settings.avatar_done_source not in {"pixera", "manual"}:
            return
        try:
            from app.director.outputs.signal_trace import emit_signal_trace_event

            emit_signal_trace_event(
                "avatar.done_expected",
                status="armed",
                bridge="pixera",
                cue_id=pixera_cue_name,
                detail=(
                    f"Expect /avatar/done {pixera_cue_name!r} on "
                    f"{settings.avatar_done_osc_host}:{settings.avatar_done_osc_port}"
                ),
            )
        except Exception:
            return
