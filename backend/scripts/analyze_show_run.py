#!/usr/bin/env python3
"""Analyze a completed show run from signal_trace.jsonl for flow disruptions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.director.show_run_analysis import (
    AnalysisThresholds,
    analyze_show_run,
    filter_run_events,
    format_show_run_report,
    latest_run_id,
    list_run_ids,
)


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.is_file():
        return events
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Post-run analysis: pauses, drops, avatar cascades, companion storms"
    )
    parser.add_argument("--trace", type=Path, required=True, help="Path to signal_trace.jsonl")
    parser.add_argument("--run-id", type=str, default=None, help="Filter by run_id (default: latest)")
    parser.add_argument(
        "--list-runs",
        action="store_true",
        help="List run_ids found in the trace and exit",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Write machine-readable report JSON to this path",
    )
    parser.add_argument("--execute-gap-sec", type=float, default=None)
    parser.add_argument("--avatar-gap-sec", type=float, default=None)
    parser.add_argument("--burst-count", type=int, default=None)
    parser.add_argument("--burst-window-ms", type=float, default=None)
    parser.add_argument("--cascade-count", type=int, default=None)
    parser.add_argument("--cascade-window-ms", type=float, default=None)
    parser.add_argument("--companion-after-min", type=int, default=None)
    parser.add_argument("--keyword-storm-count", type=int, default=None)
    parser.add_argument("--keyword-storm-window-ms", type=float, default=None)
    args = parser.parse_args(argv)

    events = load_events(args.trace)
    if not events:
        print(f"No events in {args.trace}", file=sys.stderr)
        return 1

    if args.list_runs:
        for rid in list_run_ids(events):
            count = sum(1 for e in events if e.get("run_id") == rid)
            print(f"{rid}\t{count}")
        return 0

    run_id = args.run_id or latest_run_id(events)
    if not run_id:
        print("No run_id found in trace", file=sys.stderr)
        return 1

    run_events = filter_run_events(events, run_id)
    if not run_events:
        print(f"No events for run_id={run_id}", file=sys.stderr)
        return 1

    thr_kwargs: dict[str, Any] = {}
    if args.execute_gap_sec is not None:
        thr_kwargs["execute_gap_sec"] = args.execute_gap_sec
    if args.avatar_gap_sec is not None:
        thr_kwargs["avatar_gap_sec"] = args.avatar_gap_sec
    if args.burst_count is not None:
        thr_kwargs["burst_count"] = args.burst_count
    if args.burst_window_ms is not None:
        thr_kwargs["burst_window_ms"] = args.burst_window_ms
    if args.cascade_count is not None:
        thr_kwargs["cascade_count"] = args.cascade_count
    if args.cascade_window_ms is not None:
        thr_kwargs["cascade_window_ms"] = args.cascade_window_ms
    if args.companion_after_min is not None:
        thr_kwargs["companion_after_min"] = args.companion_after_min
    if args.keyword_storm_count is not None:
        thr_kwargs["keyword_storm_count"] = args.keyword_storm_count
    if args.keyword_storm_window_ms is not None:
        thr_kwargs["keyword_storm_window_ms"] = args.keyword_storm_window_ms

    report = analyze_show_run(run_events, thresholds=AnalysisThresholds(**thr_kwargs))
    print(format_show_run_report(report))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote {args.json}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
