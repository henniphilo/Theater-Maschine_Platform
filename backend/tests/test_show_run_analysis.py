"""Tests for post-run show flow analysis heuristics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.director.show_run_analysis import (
    AnalysisThresholds,
    analyze_show_run,
    decision_category,
    filter_run_events,
    format_show_run_report,
    interpret_show_run,
    latest_run_id,
    list_run_ids,
)


def _ts(base: datetime, offset_ms: float) -> str:
    return (base + timedelta(milliseconds=offset_ms)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


BASE = datetime(2026, 10, 17, 19, 46, 0, tzinfo=timezone.utc)


def _decision(
    *,
    offset_ms: float,
    cue_id: str,
    reason: str,
    run_id: str = "run-test",
    text: str = "snippet",
) -> dict:
    return {
        "event": "dramaturgy_decision",
        "ts_wall": _ts(BASE, offset_ms),
        "ts_mono_ms": 1_000_000 + offset_ms,
        "run_id": run_id,
        "cue_id": cue_id,
        "reason_short": reason,
        "text_snippet": text,
        "decision_status": "executed",
    }


def _execute(*, offset_ms: float, run_id: str = "run-test") -> dict:
    return {
        "event": "director.execute_received",
        "ts_wall": _ts(BASE, offset_ms),
        "ts_mono_ms": 1_000_000 + offset_ms,
        "run_id": run_id,
        "logical_signal_id": f"sig-{offset_ms}",
    }


def _built(*, offset_ms: float, command_id: str, run_id: str = "run-test") -> dict:
    return {
        "event": "command.built",
        "ts_wall": _ts(BASE, offset_ms),
        "ts_mono_ms": 1_000_000 + offset_ms,
        "run_id": run_id,
        "command_id": command_id,
        "bridge": "pixera",
    }


def test_decision_category() -> None:
    assert decision_category("Avatar-Sprache") == "avatar"
    assert decision_category("[atmosphaere] Teil-2 Atmosphäre (parallel)") == "atmosphere"
    assert decision_category("[entfremden] Teil-2 Stichwort-Cues (Regel-Fallback ohne LLM)") == (
        "stichwort"
    )
    assert decision_category("Aufführungsende — Sounds Cut") == "ende"


def test_latest_run_id_prefers_last_started_with_events() -> None:
    events = [
        {"event": "run.started", "run_id": "run-old", "ts_wall": _ts(BASE, 0)},
        {"event": "director.execute_received", "run_id": "run-old", "ts_wall": _ts(BASE, 10)},
        {"event": "run.started", "run_id": "run-new", "ts_wall": _ts(BASE, 100)},
        *[{"event": "x", "run_id": "run-new", "ts_wall": _ts(BASE, 100 + i)} for i in range(12)],
        # Orphan after last started must not win.
        *[{"event": "x", "run_id": "run-orphan", "ts_wall": _ts(BASE, 500 + i)} for i in range(20)],
    ]
    assert latest_run_id(events, min_events=10) == "run-new"
    assert "run-old" in list_run_ids(events)
    assert "run-orphan" in list_run_ids(events)


def test_avatar_chain_catchup_critical() -> None:
    """22 Avatar-Sprache in ~355ms — pattern from run-20261017-193917-1cda."""
    events: list[dict] = [{"event": "run.started", "run_id": "run-test", "ts_wall": _ts(BASE, 0)}]
    cue_names = [f"wo{i}" for i in range(3, 8)] + [f"sch{i}" for i in range(1, 9)]
    for i, name in enumerate(cue_names):
        offset = 636 + i * 16  # ~15ms apart → cascade window
        events.append(_execute(offset_ms=offset))
        events.append(
            _decision(offset_ms=offset + 1, cue_id=name, reason="Avatar-Sprache")
        )
        events.append(_built(offset_ms=offset + 2, command_id=f"cmd-{i}"))

    report = analyze_show_run(events)
    cascades = [f for f in report.findings if f.kind == "avatar_chain_catchup"]
    assert cascades, format_show_run_report(report)
    assert cascades[0].severity == "critical"
    assert cascades[0].count == len(cue_names)
    assert cascades[0].duration_ms is not None
    assert cascades[0].duration_ms < 1000

    interpreted = interpret_show_run(report)
    assert interpreted.verdict == "critical"
    assert "Avatar" in interpreted.headline or "durchgerast" in interpreted.headline.lower()
    assert interpreted.priority_actions
    cascade_views = [f for f in interpreted.findings if f.kind == "avatar_chain_catchup"]
    assert cascade_views
    assert cascade_views[0].action_steps
    assert "überschrieben" in cascade_views[0].interpretation.lower() or "Beamer" in cascade_views[0].interpretation


def test_execute_storm_and_keyword_storm() -> None:
    events: list[dict] = [{"event": "run.started", "run_id": "run-test", "ts_wall": _ts(BASE, 0)}]
    snippet = "21 Der Bärenklau: – wir werden alle von Pflanzen e"
    for i in range(12):
        offset = 1000 + i * 20
        events.append(_execute(offset_ms=offset))
        events.append(
            _decision(
                offset_ms=offset + 1,
                cue_id=f"kw-{i}",
                reason="[desorientieren] Teil-2 Stichwort-Cues (Regel-Fallback ohne LLM)",
                text=snippet,
            )
        )

    report = analyze_show_run(events)
    assert any(f.kind == "execute_storm" for f in report.findings), format_show_run_report(report)
    assert any(f.kind == "keyword_storm" for f in report.findings), format_show_run_report(report)


def test_companion_after_avatar_end() -> None:
    events = [
        {"event": "run.started", "run_id": "run-test", "ts_wall": _ts(BASE, 0)},
        _decision(offset_ms=100, cue_id="last_avatar", reason="Avatar-Sprache"),
    ]
    for i in range(8):
        events.append(
            _decision(
                offset_ms=5000 + i * 100,
                cue_id=f"atm-{i}",
                reason="[atmosphaere] Teil-2 Atmosphäre (parallel)",
            )
        )

    report = analyze_show_run(events)
    companions = [f for f in report.findings if f.kind == "companion_after_avatar_end"]
    assert companions
    assert companions[0].count == 8
    assert report.category_counts.get("avatar") == 1
    assert report.category_counts.get("atmosphere") == 8


def test_pause_or_stall_gap() -> None:
    events = [
        {"event": "run.started", "run_id": "run-test", "ts_wall": _ts(BASE, 0)},
        _execute(offset_ms=0),
        _execute(offset_ms=65_000),
    ]
    report = analyze_show_run(
        events, thresholds=AnalysisThresholds(execute_gap_sec=60.0)
    )
    gaps = [f for f in report.findings if f.kind == "pause_or_stall"]
    assert gaps
    assert gaps[0].duration_ms is not None
    assert gaps[0].duration_ms >= 60_000


def test_normal_avatar_csv_duration_is_not_a_stall() -> None:
    """Wait ≈ CSV duration (+ small slack) is healthy — not a hang."""
    events = [
        {"event": "run.started", "run_id": "run-test", "ts_wall": _ts(BASE, 0)},
        _decision(offset_ms=0, cue_id="sch7", reason="Avatar-Sprache"),
        _decision(offset_ms=45_400, cue_id="sch8", reason="Avatar-Sprache"),
    ]
    report = analyze_show_run(
        events,
        thresholds=AnalysisThresholds(
            avatar_duration_sec_by_cue={"sch7": 45.2, "sch8": 10.0},
            avatar_stall_grace_sec=5.0,
        ),
    )
    assert not any(f.kind == "pause_or_stall" for f in report.findings)
    assert not any(f.kind == "avatar_chain_stall" for f in report.findings)


def test_avatar_chain_stall_when_past_clip_duration() -> None:
    """8s clip that sits 25s = hung; recovery should have kicked."""
    events = [
        {"event": "run.started", "run_id": "run-test", "ts_wall": _ts(BASE, 0)},
        _decision(offset_ms=0, cue_id="wo2_branko", reason="Avatar-Sprache"),
        _decision(offset_ms=25_000, cue_id="wo3_seb_musik", reason="Avatar-Sprache"),
    ]
    report = analyze_show_run(
        events,
        thresholds=AnalysisThresholds(
            avatar_duration_sec_by_cue={"wo2_branko": 7.9, "wo3_seb_musik": 9.8},
            avatar_stall_grace_sec=5.0,
        ),
    )
    stalls = [f for f in report.findings if f.kind == "avatar_chain_stall"]
    assert stalls
    assert stalls[0].severity in {"warn", "critical"}
    assert "CSV" in stalls[0].detail or "zu lang" in stalls[0].detail


def test_avatar_cofire_layers_not_flagged_as_stall() -> None:
    """Multi-layer segment (~26ms) must not be compared against CSV duration."""
    events = [
        {"event": "run.started", "run_id": "run-test", "ts_wall": _ts(BASE, 0)},
        _decision(offset_ms=0, cue_id="bak3_hasen", reason="Avatar-Sprache"),
        _decision(offset_ms=26, cue_id="bak3_mavie", reason="Avatar-Sprache"),
        _decision(offset_ms=20_506, cue_id="bak4_inge", reason="Avatar-Sprache"),
    ]
    report = analyze_show_run(
        events,
        thresholds=AnalysisThresholds(
            avatar_duration_sec_by_cue={
                "bak3_hasen": 20.48,
                "bak3_mavie": 20.48,
                "bak4_inge": 8.44,
            },
            avatar_stall_grace_sec=5.0,
        ),
    )
    assert not any(f.kind == "avatar_chain_stall" for f in report.findings)


def test_signal_drop_finding() -> None:
    events = [
        {"event": "run.started", "run_id": "run-test", "ts_wall": _ts(BASE, 0)},
        _built(offset_ms=10, command_id="cmd-drop-01"),
        {
            "event": "queue.enqueued",
            "command_id": "cmd-drop-01",
            "ts_wall": _ts(BASE, 11),
            "ts_mono_ms": 1_000_011,
            "run_id": "run-test",
        },
    ]
    report = analyze_show_run(events)
    assert any(f.kind == "signal_drop" for f in report.findings)
    assert report.drops


def test_sent_not_received_collapsed_without_receiver() -> None:
    events: list[dict] = [
        {"event": "run.started", "run_id": "run-test", "ts_wall": _ts(BASE, 0)},
    ]
    for i, cid in enumerate(("cmd-a", "cmd-b")):
        base = 10 + i * 20
        events.extend(
            [
                _built(offset_ms=base, command_id=cid),
                {
                    "event": "command.send_attempted",
                    "command_id": cid,
                    "ts_wall": _ts(BASE, base + 1),
                    "ts_mono_ms": 1_000_000 + base + 1,
                    "run_id": "run-test",
                    "bridge": "pixera",
                },
                {
                    "event": "command.send_completed",
                    "command_id": cid,
                    "ts_wall": _ts(BASE, base + 2),
                    "ts_mono_ms": 1_000_000 + base + 2,
                    "run_id": "run-test",
                    "bridge": "pixera",
                },
            ]
        )
    report = analyze_show_run(events)
    drop_findings = [f for f in report.findings if f.kind == "signal_drop"]
    assert len(drop_findings) == 1
    assert drop_findings[0].severity == "info"
    assert drop_findings[0].count == 2
    assert "no receiver instrumentation" in drop_findings[0].detail


def test_filter_and_report_dict() -> None:
    events = [
        {"event": "run.started", "run_id": "run-a", "ts_wall": _ts(BASE, 0)},
        _execute(offset_ms=10, run_id="run-a"),
        {"event": "run.started", "run_id": "run-b", "ts_wall": _ts(BASE, 100)},
        _execute(offset_ms=110, run_id="run-b"),
    ]
    filtered = filter_run_events(events, "run-b")
    assert all(e.get("run_id") == "run-b" for e in filtered)
    report = analyze_show_run(filtered)
    assert report.run_id == "run-b"
    data = report.to_dict()
    assert "findings" in data
    assert "drops" in data
    text = format_show_run_report(report)
    assert "run-b" in text
