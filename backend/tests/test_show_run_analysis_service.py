"""API-facing show-run analysis service (trace load + interpretation)."""

from __future__ import annotations

import json
from pathlib import Path

from app.services import show_run_analysis_service as svc


def _write_trace(path: Path, events: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
        encoding="utf-8",
    )


def test_load_show_run_analysis_interprets_cascade(tmp_path: Path, monkeypatch) -> None:
    trace = tmp_path / "signal_trace.jsonl"
    events = [
        {
            "event": "run.started",
            "run_id": "run-ui",
            "ts_wall": "2026-10-17T19:46:00.000Z",
            "ts_mono_ms": 1,
        }
    ]
    for i in range(8):
        ms = 100 + i * 20
        events.append(
            {
                "event": "director.execute_received",
                "run_id": "run-ui",
                "ts_wall": f"2026-10-17T19:46:00.{ms:03d}Z",
                "ts_mono_ms": ms,
            }
        )
        events.append(
            {
                "event": "dramaturgy_decision",
                "run_id": "run-ui",
                "ts_wall": f"2026-10-17T19:46:00.{ms + 1:03d}Z",
                "ts_mono_ms": ms + 1,
                "cue_id": f"wo{i}",
                "reason_short": "Avatar-Sprache",
                "decision_status": "executed",
            }
        )
    _write_trace(trace, events)
    monkeypatch.setattr(svc.settings, "signal_trace_path", str(trace))

    listed = svc.list_show_runs(limit=5)
    assert listed.runs[0].run_id == "run-ui"

    report = svc.load_show_run_analysis(run_id="run-ui")
    assert report.run_id == "run-ui"
    assert report.interpretation.verdict == "critical"
    assert report.interpretation.priority_actions
    assert any(f.kind == "avatar_chain_catchup" for f in report.interpretation.findings)
    assert any(f.action_steps for f in report.interpretation.findings)


def test_load_empty_trace(tmp_path: Path, monkeypatch) -> None:
    missing = tmp_path / "missing.jsonl"
    monkeypatch.setattr(svc.settings, "signal_trace_path", str(missing))
    report = svc.load_show_run_analysis()
    assert report.interpretation.verdict == "ok"
    assert "Kein Trace" in report.interpretation.headline or report.interpretation.priority_actions
