"""Technik-Test: fire all Pixera video clips (all projectors) and record failures."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.core.config import settings
from app.director.media.video_inventory import (
    parse_osc_befehlliste_files,
    resolve_osc_befehlliste_paths_for_scope,
)
from app.director.outputs.signal_trace import emit_signal_trace_event
from app.director.pipeline import DirectorPipeline
from app.services.video_cue_catalog import _data_dir
from app.services.video_scope import VideoScope

_logger = logging.getLogger(__name__)

SweepItemStatus = Literal["ok", "failed", "dry_run", "blocked"]

# Stable projector order for “one cue = all beamers”.
_PROJECTOR_PREFIX_ORDER = ("KI_RZ21", "KI_Adam", "KI_Eva", "KI_LED")


@dataclass
class VideoSweepItemResult:
    index: int
    cue_name: str
    prefix: str
    clip_name: str
    status: SweepItemStatus
    error: str | None = None
    sent_at: float | None = None


@dataclass
class VideoSweepState:
    active: bool = False
    finished: bool = False
    cancelled: bool = False
    scope: VideoScope = "part2"
    gap_ms: int = 100
    total: int = 0
    completed: int = 0
    dry_run: bool = False
    target: str = ""
    report_path: str | None = None
    error: str | None = None
    results: list[VideoSweepItemResult] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None


def list_pixera_sweep_cues(scope: VideoScope = "part2") -> list[tuple[str, list[str]]]:
    """Unique clips with projector prefixes: (clip_name, [KI_RZ21, KI_Adam, ...])."""
    paths = resolve_osc_befehlliste_paths_for_scope(_data_dir(), scope)
    pairs = parse_osc_befehlliste_files(paths)
    by_clip: dict[str, list[str]] = {}
    order: list[str] = []
    for prefix, clip_name in pairs:
        if clip_name not in by_clip:
            by_clip[clip_name] = []
            order.append(clip_name)
        if prefix not in by_clip[clip_name]:
            by_clip[clip_name].append(prefix)

    def _prefix_key(prefix: str) -> tuple[int, str]:
        try:
            return (_PROJECTOR_PREFIX_ORDER.index(prefix), prefix)
        except ValueError:
            return (len(_PROJECTOR_PREFIX_ORDER), prefix)

    return [
        (clip_name, sorted(by_clip[clip_name], key=_prefix_key))
        for clip_name in order
    ]


def _report_path() -> Path:
    log_path = Path(settings.osc_log_path)
    return log_path.parent / "pixera_video_sweep_report.json"


def _target_label(pipeline: DirectorPipeline) -> str:
    pixera = pipeline.pixera
    if not pixera:
        return "—"
    return ", ".join(f"{host}:{port}" for host, port in pixera.targets)


class VideoPixeraSweepManager:
    def __init__(self, pipeline: DirectorPipeline) -> None:
        self._pipeline = pipeline
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state = VideoSweepState()

    def status(self) -> VideoSweepState:
        with self._lock:
            return VideoSweepState(
                active=self._state.active,
                finished=self._state.finished,
                cancelled=self._state.cancelled,
                scope=self._state.scope,
                gap_ms=self._state.gap_ms,
                total=self._state.total,
                completed=self._state.completed,
                dry_run=self._state.dry_run,
                target=self._state.target,
                report_path=self._state.report_path,
                error=self._state.error,
                results=list(self._state.results),
                started_at=self._state.started_at,
                finished_at=self._state.finished_at,
            )

    def start(self, *, scope: VideoScope = "part2", gap_ms: int = 100) -> VideoSweepState:
        clips = list_pixera_sweep_cues(scope)
        if not clips:
            raise ValueError(f"Keine Pixera-Video-Cues für Scope {scope!r} gefunden")

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Video-Cue-Sweep läuft bereits")
            self._stop_event.clear()
            dry_run = bool(settings.osc_dry_run)
            self._state = VideoSweepState(
                active=True,
                finished=False,
                cancelled=False,
                scope=scope,
                gap_ms=gap_ms,
                total=len(clips),
                completed=0,
                dry_run=dry_run,
                target=_target_label(self._pipeline),
                report_path=None,
                error=None,
                results=[],
                started_at=datetime.now(timezone.utc).isoformat(),
                finished_at=None,
            )
            thread = threading.Thread(
                target=self._run,
                args=(list(clips), gap_ms, dry_run),
                name="video-pixera-sweep",
                daemon=True,
            )
            self._thread = thread

        emit_signal_trace_event(
            "technik.video_sweep_started",
            status="started",
            bridge="pixera",
            detail=f"scope={scope} clips={len(clips)} gap_ms={gap_ms}",
        )
        thread.start()
        return self.status()

    def stop(self) -> VideoSweepState:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        with self._lock:
            if self._state.active:
                self._state.cancelled = True
                self._state.active = False
                self._state.finished = True
                self._state.finished_at = datetime.now(timezone.utc).isoformat()
        return self.status()

    def _run(
        self,
        clips: list[tuple[str, list[str]]],
        gap_ms: int,
        dry_run: bool,
    ) -> None:
        try:
            if self._pipeline.safety.emergency_stop_active:
                with self._lock:
                    self._state.error = "emergency_stop_active"
                    self._state.active = False
                    self._state.finished = True
                    self._state.finished_at = datetime.now(timezone.utc).isoformat()
                return

            for index, (clip_name, prefixes) in enumerate(clips):
                if self._stop_event.is_set():
                    with self._lock:
                        self._state.cancelled = True
                    break

                result = self._send_clip(index, clip_name, prefixes, dry_run=dry_run)
                with self._lock:
                    self._state.results.append(result)
                    self._state.completed = len(self._state.results)

                if index < len(clips) - 1 and not self._stop_event.is_set():
                    time.sleep(max(gap_ms, 0) / 1000.0)
        except Exception as exc:
            _logger.exception("video pixera sweep failed")
            with self._lock:
                self._state.error = str(exc)
        finally:
            report_path = self._write_report()
            with self._lock:
                self._state.report_path = str(report_path) if report_path else None
                self._state.active = False
                self._state.finished = True
                self._state.finished_at = datetime.now(timezone.utc).isoformat()
            emit_signal_trace_event(
                "technik.video_sweep_finished",
                status="cancelled" if self._state.cancelled else "completed",
                bridge="pixera",
                detail=(
                    f"completed={self._state.completed}/{self._state.total} "
                    f"failed={sum(1 for r in self._state.results if r.status == 'failed')}"
                ),
            )

    def _send_clip(
        self,
        index: int,
        clip_name: str,
        prefixes: list[str],
        *,
        dry_run: bool,
    ) -> VideoSweepItemResult:
        cue_names = [f"{prefix}.{clip_name}" for prefix in prefixes]
        cue_label = ", ".join(cue_names)
        prefix_label = ",".join(prefixes)

        if self._pipeline.safety.emergency_stop_active:
            return VideoSweepItemResult(
                index=index,
                cue_name=cue_label,
                prefix=prefix_label,
                clip_name=clip_name,
                status="blocked",
                error="emergency_stop_active",
                sent_at=time.time(),
            )

        sent_at = time.time()
        failures: list[str] = []
        for cue_name in cue_names:
            try:
                self._pipeline.pixera.apply_cue(cue_name)
            except Exception as exc:
                failures.append(f"{cue_name}: {exc}")
                emit_signal_trace_event(
                    "technik.video_sweep_item",
                    status="failed",
                    bridge="pixera",
                    cue_id=cue_name,
                    error_message=str(exc),
                )
            else:
                emit_signal_trace_event(
                    "technik.video_sweep_item",
                    status="dry_run" if dry_run else "ok",
                    bridge="pixera",
                    cue_id=cue_name,
                )

        if failures:
            return VideoSweepItemResult(
                index=index,
                cue_name=cue_label,
                prefix=prefix_label,
                clip_name=clip_name,
                status="failed",
                error="; ".join(failures),
                sent_at=sent_at,
            )

        status: SweepItemStatus = "dry_run" if dry_run else "ok"
        return VideoSweepItemResult(
            index=index,
            cue_name=cue_label,
            prefix=prefix_label,
            clip_name=clip_name,
            status=status,
            sent_at=sent_at,
        )

    def _write_report(self) -> Path | None:
        state = self.status()
        path = _report_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            failed = [r for r in state.results if r.status in {"failed", "blocked"}]
            payload = {
                "started_at": state.started_at,
                "finished_at": state.finished_at,
                "scope": state.scope,
                "gap_ms": state.gap_ms,
                "dry_run": state.dry_run,
                "target": state.target,
                "cancelled": state.cancelled,
                "total": state.total,
                "completed": state.completed,
                "failed_count": len(failed),
                "error": state.error,
                "failed": [
                    {
                        "index": r.index,
                        "cue_name": r.cue_name,
                        "prefix": r.prefix,
                        "clip_name": r.clip_name,
                        "status": r.status,
                        "error": r.error,
                        "sent_at": r.sent_at,
                    }
                    for r in failed
                ],
                "results": [
                    {
                        "index": r.index,
                        "cue_name": r.cue_name,
                        "prefix": r.prefix,
                        "clip_name": r.clip_name,
                        "status": r.status,
                        "error": r.error,
                        "sent_at": r.sent_at,
                    }
                    for r in state.results
                ],
            }
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return path
        except Exception:
            _logger.exception("failed to write pixera video sweep report")
            return None


_manager: VideoPixeraSweepManager | None = None


def get_video_pixera_sweep_manager(
    pipeline: DirectorPipeline | None = None,
) -> VideoPixeraSweepManager:
    global _manager
    if _manager is None:
        from app.director.pipeline import get_director_pipeline

        _manager = VideoPixeraSweepManager(pipeline or get_director_pipeline())
    return _manager


def reset_video_pixera_sweep_manager_for_tests() -> None:
    global _manager
    if _manager is not None:
        _manager.stop()
    _manager = None
