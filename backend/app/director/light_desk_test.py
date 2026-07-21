"""Two-step light desk test: TCP connect first, then EOS signals on demand."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.core.config import settings
from app.director.cues.cue_models import LightCue
from app.director.outputs.light_tcp import get_light_tcp_session
from app.director.pipeline import DirectorPipeline


class LightDeskNotConnectedError(RuntimeError):
    pass


@dataclass
class LightDeskStatus:
    tcp_connected: bool = False
    output: str = "tcp"
    ready: bool = False
    scene_id: str | None = None
    hold_active: bool = False
    intensity: float | None = None


class LightDeskTestManager:
    def __init__(self, pipeline: DirectorPipeline) -> None:
        self._pipeline = pipeline
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._hold_thread: threading.Thread | None = None
        self._scene_id: str | None = None
        self._intensity: float | None = None

    def status(self) -> LightDeskStatus:
        output = settings.light_output
        tcp_connected = get_light_tcp_session().connected
        ready = output == "mirror" or tcp_connected
        with self._lock:
            return LightDeskStatus(
                tcp_connected=tcp_connected,
                output=output,
                ready=ready,
                scene_id=self._scene_id,
                hold_active=self._hold_thread is not None and self._hold_thread.is_alive(),
                intensity=self._intensity,
            )

    def connect(self, *, dry_run: bool | None = None) -> LightDeskStatus:
        is_dry_run = settings.osc_dry_run if dry_run is None else dry_run
        self._pipeline.lighting.connect_desk(dry_run=is_dry_run)
        return self.status()

    def disconnect(self, *, dry_run: bool | None = None) -> LightDeskStatus:
        is_dry_run = settings.osc_dry_run if dry_run is None else dry_run
        self.stop_hold(dry_run=is_dry_run)
        self._pipeline.lighting.disconnect_desk(dry_run=is_dry_run)
        with self._lock:
            self._scene_id = None
            self._intensity = None
        return self.status()

    def send_scene(
        self,
        scene_id: str,
        *,
        intensity: float | None = None,
        dry_run: bool | None = None,
    ) -> LightDeskStatus:
        is_dry_run = settings.osc_dry_run if dry_run is None else dry_run
        self._require_tcp_connected()
        self.stop_hold(dry_run=is_dry_run)
        delay = settings.light_osc_send_delay
        if delay > 0 and not is_dry_run:
            import time

            time.sleep(delay)
        cue = LightCue(scene_id=scene_id, intensity=intensity)
        self._pipeline.lighting.send_scene(cue, dry_run=is_dry_run)
        with self._lock:
            self._scene_id = scene_id
            self._intensity = intensity
        return self.status()

    def start_hold(
        self,
        scene_id: str,
        *,
        intensity: float | None = None,
        dry_run: bool | None = None,
    ) -> LightDeskStatus:
        is_dry_run = settings.osc_dry_run if dry_run is None else dry_run
        self._require_tcp_connected()
        self.stop_hold(dry_run=is_dry_run)
        with self._lock:
            self._scene_id = scene_id
            self._intensity = intensity
            self._stop_event.clear()
            self._hold_thread = threading.Thread(
                target=self._hold_loop,
                args=(scene_id, intensity, is_dry_run),
                name="light-desk-hold",
                daemon=True,
            )
            self._hold_thread.start()
        self._pipeline.lighting.send_scene(LightCue(scene_id=scene_id, intensity=intensity), dry_run=is_dry_run)
        return self.status()

    def stop_signal(self, *, dry_run: bool | None = None) -> LightDeskStatus:
        is_dry_run = settings.osc_dry_run if dry_run is None else dry_run
        self.stop_hold(dry_run=is_dry_run)
        self._pipeline.lighting.blackout_signal(dry_run=is_dry_run)
        with self._lock:
            self._scene_id = None
            self._intensity = None
        return self.status()

    def stop_hold(self, *, dry_run: bool | None = None) -> None:
        self._stop_event.set()
        with self._lock:
            thread = self._hold_thread
            self._hold_thread = None
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.2)

    def _hold_loop(self, scene_id: str, intensity: float | None, dry_run: bool) -> None:
        interval = settings.technik_hold_interval_seconds
        cue = LightCue(scene_id=scene_id, intensity=intensity)
        while not self._stop_event.wait(interval):
            if settings.light_output == "tcp" and not get_light_tcp_session().connected:
                return
            self._pipeline.lighting.send_scene(cue, dry_run=dry_run)

    def _require_tcp_connected(self) -> None:
        if settings.light_output != "tcp":
            return
        if not get_light_tcp_session().connected:
            raise LightDeskNotConnectedError("Light desk TCP session not connected")


_manager: LightDeskTestManager | None = None


def get_light_desk_test_manager(pipeline: DirectorPipeline | None = None) -> LightDeskTestManager:
    global _manager
    if _manager is None:
        from app.director.pipeline import get_director_pipeline

        _manager = LightDeskTestManager(pipeline or get_director_pipeline())
    return _manager
