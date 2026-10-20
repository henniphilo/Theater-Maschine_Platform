"""Load signal_trace.jsonl and build interpreted show-run analysis for the API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.director.show_run_analysis import (
    ShowRunReport,
    analyze_show_run,
    filter_run_events,
    interpret_show_run,
    latest_run_id,
    list_started_run_ids,
)
from app.schemas.director import (
    ShowRunAnalysisResponse,
    ShowRunFindingView,
    ShowRunInterpretationView,
    ShowRunListItem,
    ShowRunListResponse,
)


def _trace_path() -> Path:
    return Path(settings.signal_trace_path)


def _stream_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return events


def list_show_runs(*, limit: int = 20) -> ShowRunListResponse:
    path = _trace_path()
    events = _stream_events(path)
    started = list_started_run_ids(events)
    counts: dict[str, int] = {}
    starts: dict[str, str] = {}
    for event in events:
        rid = event.get("run_id")
        if not rid:
            continue
        rid_s = str(rid)
        counts[rid_s] = counts.get(rid_s, 0) + 1
        if event.get("event") == "run.started" and event.get("ts_wall") and rid_s not in starts:
            starts[rid_s] = str(event["ts_wall"])

    items: list[ShowRunListItem] = []
    for rid in reversed(started):
        items.append(
            ShowRunListItem(
                run_id=rid,
                ts_start=starts.get(rid),
                event_count=counts.get(rid, 0),
            )
        )
        if len(items) >= limit:
            break
    return ShowRunListResponse(runs=items, trace_path=str(path))


def _report_to_response(report: ShowRunReport) -> ShowRunAnalysisResponse:
    interpreted = interpret_show_run(report)
    return ShowRunAnalysisResponse(
        run_id=report.run_id,
        frontend_run_id=report.frontend_run_id,
        ts_start=report.ts_start,
        ts_end=report.ts_end,
        duration_sec=report.duration_sec,
        executes=report.executes,
        commands_built=report.commands_built,
        send_completed=report.send_completed,
        send_failed=report.send_failed,
        category_counts=report.category_counts,
        drop_report_count=len(report.drops),
        interpretation=ShowRunInterpretationView(
            verdict=interpreted.verdict,
            headline=interpreted.headline,
            summary=interpreted.summary,
            priority_actions=interpreted.priority_actions,
            findings=[
                ShowRunFindingView(
                    severity=f.severity,
                    kind=f.kind,
                    title=f.title,
                    interpretation=f.interpretation,
                    action_steps=f.action_steps,
                    detail=f.detail,
                    ts_wall=f.ts_wall,
                    count=f.count,
                    duration_ms=f.duration_ms,
                    cues=f.cues,
                )
                for f in interpreted.findings
            ],
        ),
    )


def load_show_run_analysis(*, run_id: str | None = None) -> ShowRunAnalysisResponse:
    path = _trace_path()
    events = _stream_events(path)
    if not events:
        return ShowRunAnalysisResponse(
            run_id=run_id or "",
            interpretation=ShowRunInterpretationView(
                verdict="ok",
                headline="Kein Trace gefunden",
                summary=f"Keine Events unter {path}. SIGNAL_TRACE_ENABLED und einen Durchlauf prüfen.",
                priority_actions=[
                    "Runtime-Setting signal_trace_enabled aktivieren und Backend neu starten.",
                    "Einen kurzen Aufführungs-Lauf machen, dann Analyse aktualisieren.",
                ],
                findings=[],
            ),
        )

    rid = run_id or latest_run_id(events)
    if not rid:
        return ShowRunAnalysisResponse(
            run_id="",
            interpretation=ShowRunInterpretationView(
                verdict="ok",
                headline="Kein run_id im Trace",
                summary="Trace enthält Events ohne run.started / run_id.",
                priority_actions=["Neuen Durchlauf starten, damit run.started geschrieben wird."],
                findings=[],
            ),
        )

    run_events = filter_run_events(events, rid)
    if not run_events:
        return ShowRunAnalysisResponse(
            run_id=rid,
            interpretation=ShowRunInterpretationView(
                verdict="issues",
                headline="Run ohne Events",
                summary=f"Für run_id={rid} wurden keine Trace-Events gefunden.",
                priority_actions=["Anderen Run in der Liste wählen oder Trace prüfen."],
                findings=[],
            ),
        )

    return _report_to_response(analyze_show_run(run_events))
