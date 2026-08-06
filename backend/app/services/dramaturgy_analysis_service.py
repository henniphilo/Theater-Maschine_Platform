"""Load dramaturgy decision events from signal trace and optional DB."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.schemas.director import (
    DramaturgyAnalysisEntry,
    DramaturgyAnalysisResponse,
    DramaturgyAnalysisSummary,
)


def _load_trace_entries(limit: int) -> list[DramaturgyAnalysisEntry]:
    path = Path(settings.signal_trace_path)
    if not path.exists():
        return []
    entries: list[DramaturgyAnalysisEntry] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        if len(entries) >= limit:
            break
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") != "dramaturgy_decision":
            continue
        entries.append(
            DramaturgyAnalysisEntry(
                decision_id=str(payload.get("decision_id", "")),
                created_at=str(payload.get("created_at") or payload.get("ts_wall", "")),
                text_snippet=str(payload.get("text_snippet", "")),
                reason_short=str(payload.get("reason_short", "")),
                dramaturgical_function=str(payload.get("dramaturgical_function", "")),
                decision=str(payload.get("decision", "")),
                decision_status=str(payload.get("status", payload.get("decision_status", ""))),
                cue_id=payload.get("cue_id"),
                executed=bool(payload.get("executed")),
                blocked_reason=payload.get("blocked_reason"),
            )
        )
    entries.reverse()
    return entries


def build_analysis_summary(entries: list[DramaturgyAnalysisEntry]) -> DramaturgyAnalysisSummary:
    total = len(entries)
    executed = sum(1 for item in entries if item.executed)
    blocked = sum(1 for item in entries if item.blocked_reason)
    silence = sum(
        1
        for item in entries
        if str(item.decision).lower() == "none"
        or str(item.dramaturgical_function).lower() == "space"
    )
    function_counts: dict[str, int] = {}
    for item in entries:
        label = item.dramaturgical_function or "unbekannt"
        function_counts[label] = function_counts.get(label, 0) + 1
    blocked_reasons = Counter(item.blocked_reason for item in entries if item.blocked_reason)
    return DramaturgyAnalysisSummary(
        total_decisions=total,
        executed_count=executed,
        blocked_count=blocked,
        silence_count=silence,
        silence_ratio=round(silence / total, 3) if total else 0.0,
        function_counts=dict(sorted(function_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        blocked_reasons=dict(sorted(blocked_reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
    )


def load_dramaturgy_analysis(
    *,
    limit: int = 100,
    dramaturgy_state: dict[str, object] | None = None,
) -> DramaturgyAnalysisResponse:
    db_entries = _load_db_entries(limit)
    trace_entries = _load_trace_entries(limit)
    merged = db_entries + [e for e in trace_entries if e.decision_id not in {d.decision_id for d in db_entries}]
    merged.sort(key=lambda item: item.created_at)
    if len(merged) > limit:
        merged = merged[-limit:]
    return DramaturgyAnalysisResponse(
        entries=merged,
        dramaturgy_state=dramaturgy_state or {},
        summary=build_analysis_summary(merged),
    )


def _load_db_entries(limit: int) -> list[DramaturgyAnalysisEntry]:
    try:
        from app.db.session import SessionLocal
        from app.models.dramaturgy_decision_event import DramaturgyDecisionEventRow
    except ImportError:
        return []

    session = SessionLocal()
    try:
        rows = (
            session.query(DramaturgyDecisionEventRow)
            .order_by(DramaturgyDecisionEventRow.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            DramaturgyAnalysisEntry(
                decision_id=row.id,
                created_at=row.created_at.isoformat(),
                text_snippet=row.text_snippet or "",
                reason_short=row.reason_short or "",
                dramaturgical_function=row.dramaturgical_function or "",
                decision=row.decision_kind or "",
                decision_status=row.decision_status or "",
                cue_id=row.cue_id,
                executed=row.executed,
                blocked_reason=row.blocked_reason,
            )
            for row in reversed(rows)
        ]
    except Exception:
        return []
    finally:
        session.close()
