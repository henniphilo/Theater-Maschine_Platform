"""Sustained Technik-Test output with periodic hold keepalives until explicit stop."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.core.config import settings
from app.director.cues.cue_models import SoundAction, SoundCue
from app.director.pipeline import DirectorPipeline


@dataclass
class TechnikHoldState:
    clip_id: str = "kuh"
    sound_cue_id: str = "dummy_drone"
    light_scene_id: str = "vorbuehnenzug"
    send_visual: bool = False
    send_sound: bool = False
    send_light: bool = False
    opacity: float = 0.8
    volume: float = 0.5


class TechnikHoldManager:
    def __init__(self, pipeline: DirectorPipeline) -> None:
        self._pipeline = pipeline
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active: TechnikHoldState | None = None

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active is not None and any(
                (
                    self._active.send_visual,
                    self._active.send_sound,
                    self._active.send_light,
                )
            )

    def status(self) -> TechnikHoldState | None:
        with self._lock:
            if self._active is None:
                return None
            return TechnikHoldState(**self._active.__dict__)

    def start(self, state: TechnikHoldState) -> None:
        with self._lock:
            self._stop_locked(send_stop=True)
            if not state.send_visual and not state.send_sound and not state.send_light:
                return
            self._active = state
            self._stop_event.clear()
            self._send_start(state)
            self._thread = threading.Thread(target=self._hold_loop, name="technik-hold", daemon=True)
            self._thread.start()

    def stop(
        self,
        *,
        send_visual: bool = True,
        send_sound: bool = True,
        send_light: bool = True,
    ) -> None:
        with self._lock:
            if self._active is None:
                return
            state = self._active
            if send_visual and state.send_visual:
                self._stop_visual()
                state.send_visual = False
            if send_sound and state.send_sound:
                self._stop_sound(state)
                state.send_sound = False
            if send_light and state.send_light:
                self._stop_light()
                state.send_light = False
            if not state.send_visual and not state.send_sound and not state.send_light:
                self._stop_locked(send_stop=False)

    def _hold_loop(self) -> None:
        interval = settings.technik_hold_interval_seconds
        while not self._stop_event.wait(interval):
            with self._lock:
                state = self._active
                if state is None:
                    return
                self._send_hold(state)

    def _stop_locked(self, *, send_stop: bool) -> None:
        self._stop_event.set()
        if send_stop and self._active is not None:
            state = self._active
            if state.send_visual:
                self._stop_visual()
            if state.send_sound:
                self._stop_sound(state)
            if state.send_light:
                self._stop_light()
        self._active = None
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.2)

    def _dry_run(self) -> bool:
        return settings.osc_dry_run

    def _send_start(self, state: TechnikHoldState) -> None:
        dry_run = self._dry_run()
        if state.send_visual:
            self._pipeline.touchdesigner.play_clip(state.clip_id, state.opacity, fade_time=0.0)
        if state.send_sound:
            self._pipeline.sound.execute(
                SoundCue(action=SoundAction.TRIGGER_CUE, cue_id=state.sound_cue_id, volume=state.volume),
                dry_run=dry_run,
            )

    def _send_hold(self, state: TechnikHoldState) -> None:
        dry_run = self._dry_run()
        if state.send_visual:
            self._pipeline.touchdesigner.set_opacity(state.opacity)
        if state.send_sound:
            self._pipeline.sound.hold(
                SoundCue(action=SoundAction.TRIGGER_CUE, cue_id=state.sound_cue_id, volume=state.volume),
                dry_run=dry_run,
            )

    def _stop_visual(self) -> None:
        self._pipeline.touchdesigner.stop_clip()
        self._pipeline.touchdesigner.blackout()

    def _stop_sound(self, state: TechnikHoldState) -> None:
        self._pipeline.sound.execute(
            SoundCue(action=SoundAction.STOP_CUE, cue_id=state.sound_cue_id),
            dry_run=self._dry_run(),
        )

    def _stop_light(self) -> None:
        from app.director.light_desk_test import get_light_desk_test_manager

        get_light_desk_test_manager(self._pipeline).stop_signal(dry_run=self._dry_run())


_manager: TechnikHoldManager | None = None


def get_technik_hold_manager(pipeline: DirectorPipeline | None = None) -> TechnikHoldManager:
    global _manager
    if _manager is None:
        from app.director.pipeline import get_director_pipeline

        _manager = TechnikHoldManager(pipeline or get_director_pipeline())
    return _manager
