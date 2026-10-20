#!/usr/bin/env python3
"""MCP debug server for Theatermaschine — read-only trace/catalog/inszenierung tools."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("THEATERMASCHINE_ROOT", Path(__file__).resolve().parents[2]))
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("theatermaschine-debug")


def _trace_path() -> Path:
    for candidate in (ROOT / "logs" / "signal_trace.jsonl", ROOT / "backend" / "logs" / "signal_trace.jsonl"):
        if candidate.is_file():
            return candidate
    return ROOT / "logs" / "signal_trace.jsonl"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@mcp.tool()
def analyze_signal_trace(run_id: str | None = None) -> str:
    """Analyze signal_trace.jsonl for dropped commands. Optional run_id filter."""
    from scripts.analyze_signal_trace import format_report, load_events, summarize_run, _filter_run

    trace = _trace_path()
    events = load_events(trace)
    events = _filter_run(events, run_id)
    if not events:
        return f"No trace events found at {trace}"
    return format_report(summarize_run(events))


@mcp.tool()
def analyze_show_run(run_id: str | None = None) -> str:
    """Post-run flow analysis: pauses, drops, avatar cascades, companion storms.

    Defaults to the latest run in logs/signal_trace.jsonl when run_id is omitted.
    """
    from app.director.show_run_analysis import (
        analyze_show_run as _analyze,
        filter_run_events,
        format_show_run_report,
        latest_run_id,
    )

    trace = _trace_path()
    events = _load_jsonl(trace)
    if not events:
        return f"No trace events found at {trace}"
    rid = run_id or latest_run_id(events)
    if not rid:
        return "No run_id found in trace"
    run_events = filter_run_events(events, rid)
    if not run_events:
        return f"No events for run_id={rid}"
    return format_show_run_report(_analyze(run_events))


@mcp.tool()
def read_inszenierung(inszenierung_id: str) -> str:
    """Summarize a Teil 2 inszenierung JSON by UUID."""
    path = ROOT / "data" / "inszenierungen" / f"{inszenierung_id}.json"
    data = _load_json(path)
    if data is None:
        return f"Not found: {path}"

    corpus = data if isinstance(data, dict) else {}
    plan = corpus.get("teil2_plan") or {}
    summary = {
        "id": inszenierung_id,
        "title": corpus.get("title"),
        "status": corpus.get("status"),
        "prepare_phase": corpus.get("prepare_phase"),
        "prepare_error": corpus.get("prepare_error"),
        "script_text_length": len(corpus.get("script_text") or ""),
        "sentences": len(plan.get("sentences") or []),
        "avatar_segments": len(plan.get("avatar_segments") or []),
        "dramaturgy_cues": len((plan.get("dramaturgy") or {}).get("cue_points") or []),
        "atmosphere_cues": len(plan.get("atmosphere_cue_points") or []),
        "alignment_warnings": plan.get("alignment_warnings") or [],
        "performance_speaker": plan.get("performance_speaker"),
    }
    return json.dumps(summary, indent=2, ensure_ascii=False)


@mcp.tool()
def list_recent_traces(limit: int = 20, bridge: str | None = None, cue_id: str | None = None) -> str:
    """List recent signal trace events, optionally filtered by bridge or cue_id."""
    events = _load_jsonl(_trace_path())
    if bridge:
        events = [e for e in events if e.get("bridge") == bridge]
    if cue_id:
        events = [e for e in events if e.get("cue_id") == cue_id]
    recent = events[-limit:]
    return json.dumps(recent, indent=2, ensure_ascii=False)


@mcp.tool()
def cue_catalog_lookup(query: str, catalog: str = "video") -> str:
    """Search video_cues.json or sound_cues.json for a cue id or label substring."""
    if catalog not in {"video", "sound"}:
        return "catalog must be 'video' or 'sound'"

    filename = "video_cues.json" if catalog == "video" else "sound_cues.json"
    data = _load_json(ROOT / "data" / filename)
    if data is None:
        return f"Catalog not found: data/{filename}"

    q = query.lower()
    matches: list[Any] = []
    items = data if isinstance(data, list) else data.get("cues") or data.get("items") or []

    if isinstance(items, dict):
        items = [{"id": k, **(v if isinstance(v, dict) else {"value": v})} for k, v in items.items()]

    for item in items:
        if not isinstance(item, dict):
            continue
        blob = json.dumps(item, ensure_ascii=False).lower()
        if q in blob:
            matches.append(item)
        if len(matches) >= 25:
            break

    return json.dumps({"query": query, "catalog": catalog, "matches": matches[:25]}, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
