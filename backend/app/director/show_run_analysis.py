"""Post-run show analysis: pauses, drops, avatar cascades, companion bursts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from app.director.signal_trace_analysis import DropReport, classify_command_drops

# Teil-2 avatars: wait CSV duration_ms, then next OSC (no Pixera Done/ACK).
# Stall = waited longer than that clip's duration + grace (hung timer → recovery).
DEFAULT_EXECUTE_GAP_SEC = 60.0
# Fallback only when cue duration is unknown in the catalog.
DEFAULT_AVATAR_STALL_FALLBACK_SEC = 40.0
DEFAULT_AVATAR_STALL_GRACE_SEC = 5.0
# Back-compat alias (fallback when no duration lookup)
DEFAULT_AVATAR_GAP_SEC = DEFAULT_AVATAR_STALL_FALLBACK_SEC
DEFAULT_AVATAR_STALL_SEC = DEFAULT_AVATAR_STALL_FALLBACK_SEC
DEFAULT_BURST_COUNT = 8
DEFAULT_BURST_WINDOW_MS = 500.0
DEFAULT_CASCADE_COUNT = 5
DEFAULT_CASCADE_WINDOW_MS = 1000.0
DEFAULT_COMPANION_AFTER_MIN = 5
DEFAULT_KEYWORD_STORM_COUNT = 6
DEFAULT_KEYWORD_STORM_WINDOW_MS = 1000.0


@dataclass(frozen=True)
class AnalysisThresholds:
    execute_gap_sec: float = DEFAULT_EXECUTE_GAP_SEC
    avatar_gap_sec: float = DEFAULT_AVATAR_GAP_SEC
    avatar_stall_grace_sec: float = DEFAULT_AVATAR_STALL_GRACE_SEC
    # Optional cue_id → duration_sec (tests / overrides). None → load catalog.
    avatar_duration_sec_by_cue: dict[str, float] | None = None
    burst_count: int = DEFAULT_BURST_COUNT
    burst_window_ms: float = DEFAULT_BURST_WINDOW_MS
    cascade_count: int = DEFAULT_CASCADE_COUNT
    cascade_window_ms: float = DEFAULT_CASCADE_WINDOW_MS
    companion_after_min: int = DEFAULT_COMPANION_AFTER_MIN
    keyword_storm_count: int = DEFAULT_KEYWORD_STORM_COUNT
    keyword_storm_window_ms: float = DEFAULT_KEYWORD_STORM_WINDOW_MS


@dataclass(frozen=True)
class Finding:
    severity: str  # critical | warn | info
    kind: str
    detail: str
    ts_wall: str | None = None
    count: int | None = None
    duration_ms: float | None = None
    cues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InterpretedFinding:
    severity: str
    kind: str
    title: str
    interpretation: str
    action_steps: list[str]
    detail: str
    ts_wall: str | None = None
    count: int | None = None
    duration_ms: float | None = None
    cues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ShowRunInterpretation:
    verdict: str  # ok | issues | critical
    headline: str
    summary: str
    priority_actions: list[str]
    findings: list[InterpretedFinding]


@dataclass
class ShowRunReport:
    run_id: str
    frontend_run_id: str | None
    ts_start: str | None
    ts_end: str | None
    duration_sec: float
    executes: int
    commands_built: int
    send_completed: int
    send_failed: int
    drops: list[DropReport]
    category_counts: dict[str, int]
    findings: list[Finding]

    def to_dict(self) -> dict[str, Any]:
        interpreted = interpret_show_run(self)
        return {
            "run_id": self.run_id,
            "frontend_run_id": self.frontend_run_id,
            "ts_start": self.ts_start,
            "ts_end": self.ts_end,
            "duration_sec": self.duration_sec,
            "executes": self.executes,
            "commands_built": self.commands_built,
            "send_completed": self.send_completed,
            "send_failed": self.send_failed,
            "drops": [asdict(d) for d in self.drops],
            "category_counts": self.category_counts,
            "findings": [asdict(f) for f in self.findings],
            "interpretation": asdict(interpreted),
        }


def parse_ts_wall(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def decision_category(reason_short: str | None) -> str:
    reason = reason_short or ""
    if reason == "Avatar-Sprache":
        return "avatar"
    lowered = reason.lower()
    if "[atmosphaere]" in lowered or "[atmosphäre]" in lowered:
        return "atmosphere"
    if "Stichwort" in reason:
        return "stichwort"
    if "Aufführungsende" in reason or "Auffuehrungsende" in reason:
        return "ende"
    return "other"


def list_run_ids(events: list[dict[str, Any]]) -> list[str]:
    """Return run_ids in order of run.started, then any orphan run_ids."""
    seen: list[str] = []
    for event in events:
        if event.get("event") == "run.started" and event.get("run_id"):
            rid = str(event["run_id"])
            if rid not in seen:
                seen.append(rid)
    for event in events:
        rid = event.get("run_id")
        if rid and str(rid) not in seen:
            seen.append(str(rid))
    return seen


def list_started_run_ids(events: list[dict[str, Any]]) -> list[str]:
    """Return run_ids that emitted run.started, in first-seen order."""
    seen: list[str] = []
    for event in events:
        if event.get("event") == "run.started" and event.get("run_id"):
            rid = str(event["run_id"])
            if rid not in seen:
                seen.append(rid)
    return seen


def latest_run_id(events: list[dict[str, Any]], *, min_events: int = 10) -> str | None:
    """Pick the last run.started with enough events; ignore orphan run_ids."""
    started = list_started_run_ids(events)
    counts: dict[str, int] = {}
    for event in events:
        rid = event.get("run_id")
        if rid:
            counts[str(rid)] = counts.get(str(rid), 0) + 1

    if started:
        for rid in reversed(started):
            if counts.get(rid, 0) >= min_events:
                return rid
        return started[-1]

    # No run.started — fall back to last-seen run_id with enough events.
    orphans = list_run_ids(events)
    for rid in reversed(orphans):
        if counts.get(rid, 0) >= min_events:
            return rid
    return orphans[-1] if orphans else None


def filter_run_events(events: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    return [e for e in events if e.get("run_id") == run_id]


def _sorted_by_time(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(e: dict[str, Any]) -> tuple[float, float]:
        wall = parse_ts_wall(e.get("ts_wall") if isinstance(e.get("ts_wall"), str) else None)
        wall_epoch = wall.timestamp() if wall else 0.0
        mono = float(e.get("ts_mono_ms") or 0.0)
        return (wall_epoch, mono)

    return sorted(events, key=key)


def _gap_seconds(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    ta = parse_ts_wall(a.get("ts_wall") if isinstance(a.get("ts_wall"), str) else None)
    tb = parse_ts_wall(b.get("ts_wall") if isinstance(b.get("ts_wall"), str) else None)
    if ta and tb:
        return (tb - ta).total_seconds()
    ma = e_mono(a)
    mb = e_mono(b)
    if ma is not None and mb is not None:
        return (mb - ma) / 1000.0
    return None


def e_mono(event: dict[str, Any]) -> float | None:
    raw = event.get("ts_mono_ms")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _cluster_bursts(
    timed_events: list[dict[str, Any]],
    *,
    min_count: int,
    window_ms: float,
) -> list[tuple[list[dict[str, Any]], float]]:
    """Greedy clustering: grow a cluster while consecutive gaps stay within window_ms."""
    if len(timed_events) < min_count:
        return []
    clusters: list[tuple[list[dict[str, Any]], float]] = []
    i = 0
    while i < len(timed_events):
        cluster = [timed_events[i]]
        j = i + 1
        while j < len(timed_events):
            gap = _gap_seconds(timed_events[j - 1], timed_events[j])
            if gap is None or gap * 1000.0 > window_ms:
                break
            cluster.append(timed_events[j])
            j += 1
        if len(cluster) >= min_count:
            span = _gap_seconds(cluster[0], cluster[-1])
            duration_ms = (span * 1000.0) if span is not None else 0.0
            # Also require total span within a generous multiple of window
            # so sparse chains don't merge; primary gate is consecutive gaps.
            clusters.append((cluster, duration_ms))
            i = j
        else:
            i += 1
    return clusters


def _find_execute_gaps(
    executes: list[dict[str, Any]],
    threshold_sec: float,
) -> list[Finding]:
    findings: list[Finding] = []
    for prev, nxt in zip(executes, executes[1:]):
        gap = _gap_seconds(prev, nxt)
        if gap is None or gap < threshold_sec:
            continue
        findings.append(
            Finding(
                severity="info" if gap < threshold_sec * 1.5 else "warn",
                kind="pause_or_stall",
                detail=(
                    f"{gap:.1f}s without director.execute "
                    f"(während langer Avatar-Clips oft normal; ab ~{threshold_sec:.0f}s melden)"
                ),
                ts_wall=str(prev.get("ts_wall") or "") or None,
                duration_ms=gap * 1000.0,
            )
        )
    return findings


def load_avatar_duration_sec_by_cue() -> dict[str, float]:
    """Map avatar cue ids to CSV duration in seconds from avatar_speech.json."""
    try:
        from app.services.avatar_speech_catalog import get_avatar_speech_catalog_service

        catalog = get_avatar_speech_catalog_service().load()
    except Exception:
        return {}
    out: dict[str, float] = {}
    for cue in catalog.cues:
        ms = getattr(cue, "duration_ms", None)
        if isinstance(ms, (int, float)) and ms > 0:
            out[str(cue.id).strip().lower()] = float(ms) / 1000.0
    return out


def _expected_avatar_wait_sec(
    cue_id: str | None,
    *,
    durations: dict[str, float],
    fallback_sec: float,
    grace_sec: float,
) -> tuple[float, float | None]:
    """Return (stall_after_sec, catalog_duration_sec_or_none)."""
    key = (cue_id or "").strip().lower()
    catalog_sec = durations.get(key) if key else None
    if catalog_sec is not None:
        return catalog_sec + grace_sec, catalog_sec
    return fallback_sec, None


def _find_avatar_gaps(
    avatars: list[dict[str, Any]],
    *,
    fallback_sec: float,
    grace_sec: float,
    durations: dict[str, float],
) -> list[Finding]:
    """Stall only when wait exceeds previous clip CSV duration (+ grace)."""
    findings: list[Finding] = []
    for prev, nxt in zip(avatars, avatars[1:]):
        gap = _gap_seconds(prev, nxt)
        if gap is None:
            continue
        prev_cue = str(prev.get("cue_id") or "")
        next_cue = str(nxt.get("cue_id") or "")
        stall_after, catalog_sec = _expected_avatar_wait_sec(
            prev_cue,
            durations=durations,
            fallback_sec=fallback_sec,
            grace_sec=grace_sec,
        )
        if gap < stall_after:
            continue
        over_by = gap - (catalog_sec if catalog_sec is not None else fallback_sec)
        if catalog_sec is not None:
            detail = (
                f"{gap:.1f}s after {prev_cue or '?'} → {next_cue or '?'} "
                f"(CSV {catalog_sec:.1f}s + {grace_sec:.0f}s Toleranz; "
                f"{over_by:.1f}s zu lang — hing, Recovery hätte greifen sollen)"
            )
        else:
            detail = (
                f"{gap:.1f}s after {prev_cue or '?'} → {next_cue or '?'} "
                f"(keine CSV-Dauer bekannt; Fallback {fallback_sec:.0f}s)"
            )
        findings.append(
            Finding(
                severity="warn" if over_by < grace_sec * 2 else "critical",
                kind="avatar_chain_stall",
                detail=detail,
                ts_wall=str(prev.get("ts_wall") or "") or None,
                duration_ms=gap * 1000.0,
                cues=[prev_cue, next_cue],
            )
        )
    return findings


def _find_execute_storms(
    executes: list[dict[str, Any]],
    *,
    min_count: int,
    window_ms: float,
) -> list[Finding]:
    findings: list[Finding] = []
    for cluster, duration_ms in _cluster_bursts(
        executes, min_count=min_count, window_ms=window_ms
    ):
        findings.append(
            Finding(
                severity="warn",
                kind="execute_storm",
                detail=f"{len(cluster)} executes in {duration_ms:.0f}ms",
                ts_wall=str(cluster[0].get("ts_wall") or "") or None,
                count=len(cluster),
                duration_ms=duration_ms,
            )
        )
    return findings


def _find_avatar_cascades(
    avatars: list[dict[str, Any]],
    *,
    min_count: int,
    window_ms: float,
) -> list[Finding]:
    findings: list[Finding] = []
    for cluster, duration_ms in _cluster_bursts(
        avatars, min_count=min_count, window_ms=window_ms
    ):
        cues = [str(e.get("cue_id") or "?") for e in cluster]
        first, last = cues[0], cues[-1]
        cue_summary = f"{first}…{last}" if len(cues) > 2 else ", ".join(cues)
        findings.append(
            Finding(
                severity="critical",
                kind="avatar_chain_catchup",
                detail=f"{len(cluster)} Avatar-Sprache in {duration_ms:.0f}ms ({cue_summary})",
                ts_wall=str(cluster[0].get("ts_wall") or "") or None,
                count=len(cluster),
                duration_ms=duration_ms,
                cues=cues,
            )
        )
    return findings


def _find_companion_after_avatar(
    decisions: list[dict[str, Any]],
    *,
    min_count: int,
) -> list[Finding]:
    avatars = [d for d in decisions if decision_category(d.get("reason_short")) == "avatar"]
    if not avatars:
        return []
    last_avatar = avatars[-1]
    last_ts = parse_ts_wall(
        last_avatar.get("ts_wall") if isinstance(last_avatar.get("ts_wall"), str) else None
    )
    last_mono = e_mono(last_avatar)

    companions: list[dict[str, Any]] = []
    for decision in decisions:
        cat = decision_category(decision.get("reason_short"))
        if cat not in {"atmosphere", "stichwort"}:
            continue
        if last_ts:
            ts = parse_ts_wall(
                decision.get("ts_wall") if isinstance(decision.get("ts_wall"), str) else None
            )
            if ts is None or ts <= last_ts:
                continue
        elif last_mono is not None:
            mono = e_mono(decision)
            if mono is None or mono <= last_mono:
                continue
        else:
            continue
        companions.append(decision)

    if len(companions) < min_count:
        return []
    atm = sum(1 for c in companions if decision_category(c.get("reason_short")) == "atmosphere")
    kw = sum(1 for c in companions if decision_category(c.get("reason_short")) == "stichwort")
    return [
        Finding(
            severity="warn",
            kind="companion_after_avatar_end",
            detail=(
                f"{len(companions)} companion cues after last avatar "
                f"({atm} atmosphere, {kw} stichwort); last avatar={last_avatar.get('cue_id')}"
            ),
            ts_wall=str(last_avatar.get("ts_wall") or "") or None,
            count=len(companions),
            cues=[str(last_avatar.get("cue_id") or "")],
        )
    ]


def _find_keyword_storms(
    decisions: list[dict[str, Any]],
    *,
    min_count: int,
    window_ms: float,
) -> list[Finding]:
    keywords = [
        d for d in decisions if decision_category(d.get("reason_short")) == "stichwort"
    ]
    findings: list[Finding] = []
    for cluster, duration_ms in _cluster_bursts(
        keywords, min_count=min_count, window_ms=window_ms
    ):
        snippets = {(c.get("text_snippet") or "")[:40] for c in cluster}
        same_text = len(snippets) == 1 and bool(next(iter(snippets)))
        if not same_text and len(cluster) < min_count + 2:
            # Prefer same-snippet storms; still flag very large mixed bursts.
            continue
        snippet = next(iter(snippets)) if snippets else ""
        findings.append(
            Finding(
                severity="warn",
                kind="keyword_storm",
                detail=(
                    f"{len(cluster)} Stichwort cues in {duration_ms:.0f}ms"
                    + (f" (same text: {snippet!r}…)" if same_text and snippet else "")
                ),
                ts_wall=str(cluster[0].get("ts_wall") or "") or None,
                count=len(cluster),
                duration_ms=duration_ms,
                cues=[str(c.get("cue_id") or "") for c in cluster[:12]],
            )
        )
    return findings


def _severity_rank(severity: str) -> int:
    return {"critical": 0, "warn": 1, "info": 2}.get(severity, 9)


def _findings_from_drops(
    events: list[dict[str, Any]],
    drops: list[DropReport],
) -> list[Finding]:
    """Turn drop reports into findings; collapse sent_not_received without receivers."""
    has_receiver = any(e.get("event") == "receiver.seen" for e in events)
    findings: list[Finding] = []
    sent_not_received = 0
    midi_no_receiver = 0

    for drop in drops:
        if drop.drop_class == "sent_not_received" and not has_receiver:
            sent_not_received += 1
            if drop.detail == "midi_no_receiver":
                midi_no_receiver += 1
            continue
        severity = (
            "critical"
            if drop.drop_class in {"attempted_failed", "built_not_enqueued"}
            else "warn"
        )
        findings.append(
            Finding(
                severity=severity,
                kind="signal_drop",
                detail=f"{drop.command_id}: {drop.drop_class}"
                + (f" ({drop.detail})" if drop.detail else ""),
                cues=[drop.logical_signal_id] if drop.logical_signal_id else [],
            )
        )

    if sent_not_received:
        detail = (
            f"{sent_not_received} commands send_completed without receiver.seen "
            "(no receiver instrumentation in this run — not treated as live drops)"
        )
        if midi_no_receiver:
            detail += f"; {midi_no_receiver} midi_no_receiver"
        findings.append(
            Finding(
                severity="info",
                kind="signal_drop",
                detail=detail,
                count=sent_not_received,
            )
        )
    return findings


def analyze_show_run(
    events: list[dict[str, Any]],
    *,
    thresholds: AnalysisThresholds | None = None,
) -> ShowRunReport:
    """Analyze one run's signal-trace events for flow disruptions."""
    thr = thresholds or AnalysisThresholds()
    events = _sorted_by_time(events)

    run_id = next((str(e["run_id"]) for e in events if e.get("run_id")), "?")
    frontend_run_id = next(
        (str(e["frontend_run_id"]) for e in events if e.get("frontend_run_id")),
        None,
    )

    ts_start = next((e.get("ts_wall") for e in events if e.get("ts_wall")), None)
    ts_end = next((e.get("ts_wall") for e in reversed(events) if e.get("ts_wall")), None)
    duration_sec = 0.0
    t0 = parse_ts_wall(ts_start if isinstance(ts_start, str) else None)
    t1 = parse_ts_wall(ts_end if isinstance(ts_end, str) else None)
    if t0 and t1:
        duration_sec = max(0.0, (t1 - t0).total_seconds())

    executes = [e for e in events if e.get("event") == "director.execute_received"]
    decisions = [e for e in events if e.get("event") == "dramaturgy_decision"]
    commands_built = sum(1 for e in events if e.get("event") == "command.built")
    send_completed = sum(1 for e in events if e.get("event") == "command.send_completed")
    send_failed = sum(1 for e in events if e.get("event") == "command.send_failed")

    category_counts: dict[str, int] = {}
    for decision in decisions:
        cat = decision_category(decision.get("reason_short"))
        category_counts[cat] = category_counts.get(cat, 0) + 1

    avatars = [d for d in decisions if decision_category(d.get("reason_short")) == "avatar"]

    drops = classify_command_drops(events)
    findings: list[Finding] = []
    findings.extend(_findings_from_drops(events, drops))

    findings.extend(_find_execute_gaps(executes, thr.execute_gap_sec))
    durations = thr.avatar_duration_sec_by_cue
    if durations is None:
        durations = load_avatar_duration_sec_by_cue()
    findings.extend(
        _find_avatar_gaps(
            avatars,
            fallback_sec=thr.avatar_gap_sec,
            grace_sec=thr.avatar_stall_grace_sec,
            durations=durations,
        )
    )
    findings.extend(
        _find_execute_storms(
            executes, min_count=thr.burst_count, window_ms=thr.burst_window_ms
        )
    )
    findings.extend(
        _find_avatar_cascades(
            avatars, min_count=thr.cascade_count, window_ms=thr.cascade_window_ms
        )
    )
    findings.extend(
        _find_companion_after_avatar(decisions, min_count=thr.companion_after_min)
    )
    findings.extend(
        _find_keyword_storms(
            decisions,
            min_count=thr.keyword_storm_count,
            window_ms=thr.keyword_storm_window_ms,
        )
    )

    findings.sort(key=lambda f: (_severity_rank(f.severity), f.ts_wall or "", f.kind))

    return ShowRunReport(
        run_id=run_id,
        frontend_run_id=frontend_run_id,
        ts_start=str(ts_start) if ts_start else None,
        ts_end=str(ts_end) if ts_end else None,
        duration_sec=round(duration_sec, 1),
        executes=len(executes),
        commands_built=commands_built,
        send_completed=send_completed,
        send_failed=send_failed,
        drops=drops,
        category_counts=category_counts,
        findings=findings,
    )


_FINDING_GUIDANCE: dict[str, tuple[str, str, list[str]]] = {
    # title, interpretation template ({detail} available), action steps
    "avatar_chain_catchup": (
        "Avatar-Kette ist durchgerast",
        "Mehrere Avatar-Clips wurden fast gleichzeitig gefeuert ({detail}). "
        "Auf dem Beamer bleibt meist nur das letzte Bild sichtbar — die anderen "
        "wurden sofort überschrieben. Typisch nach einem hängenden CSV-Timer "
        "oder parallelen Recovery-Kicks.",
        [
            "Frontend mit dem neuesten Avatar-Recovery-Fix neu laden (Hard-Reload).",
            "Aufführungs-Tab im Vordergrund lassen — Hintergrund-Tabs drosseln Timer.",
            "Kurzen Probe-Lauf ab dem problematischen Abschnitt wiederholen.",
            "Danach erneut Durchlauf-Analyse: kein weiteres avatar_chain_catchup.",
        ],
    ),
    "execute_storm": (
        "Cue-Sturm (viele Executes auf einmal)",
        "Sehr viele Director-Executes in kurzer Zeit ({detail}). "
        "Wirkt wie Überschlagen von Licht/Sound/Video — oft Catch-up nach Pause, "
        "Seek oder Uhrensprung.",
        [
            "Prüfen, ob Pause/Resume oder Tab-Wechsel kurz vorher lag.",
            "Bei Teil 2: Time-Cue-Catch-up und Stichwort-Caps im Playback prüfen.",
            "Abschnitt erneut fahren und Sturm-Zeitpunkt im Trace markieren.",
        ],
    ),
    "keyword_storm": (
        "Stichwort-Cues gebündelt",
        "Viele Stichwort-Cues mit gleichem Textfenster ({detail}). "
        "Regel-Fallback hat für einen Satz/Abschnitt zu viele Keyword-Treffer "
        "auf einmal ausgelöst.",
        [
            "Im Prepare die Stichwort-Zuordnung für den genannten Text prüfen.",
            "KEYWORD_CUES_PER_SENTENCE_CAP / Dramaturgie-Regeln gegen Häufung prüfen.",
            "Optional: betroffene Keywords entschärfen oder auf weniger Cues mappen.",
        ],
    ),
    "companion_after_avatar_end": (
        "Begleitvideos nach dem letzten Avatar",
        "Nach dem letzten Avatar-Clip liefen noch Atmosphäre-/Stichwort-Cues ({detail}). "
        "Kann gewollt sein — oder Rest nach einer Avatar-Lawine / verzögerter Show-Clock.",
        [
            "Timeline: letzter Avatar vs. folgende Atmosphären gegeneinander legen.",
            "Wenn ungewollt: Atmosphere-Offsets im Prepare kürzen oder früher enden lassen.",
            "Zuerst Avatar-Cascade beheben — sonst folgt der Companion-Tail oft darauf.",
        ],
    ),
    "pause_or_stall": (
        "Lange Lücke ohne neue Executes",
        "Sehr lange Zeit ohne director.execute ({detail}). "
        "Bei rein zeitbasierten Avataren (CSV-Dauer, kein Pixera-Done) sind "
        "Lücken während langer Clips oft normal — erst extreme Lücken deuten "
        "auf Show-Stall oder Tab-Freeze hin.",
        [
            "Prüfen, ob der Aufführungs-Tab noch lebte (nicht eingefroren/im Hintergrund).",
            "Ob TTS/Show-Clock noch lief (nicht hängengeblieben).",
            "Avatar-Stalls separat unter avatar_chain_stall prüfen.",
        ],
    ),
    "avatar_chain_stall": (
        "Avatar hing — länger als die Clipdauer",
        "Die Kette hat länger gewartet als die CSV-Dauer des Clips ({detail}). "
        "Normal: Clipdauer abwarten, dann nächstes OSC. Wenn es hängt, soll "
        "Recovery den nächsten Clip anstoßen — und danach wieder normal "
        "Clipdauer für Clipdauer weiterlaufen (nicht die Restkette durchrasen).",
        [
            "Prüfen, ob Recovery im Browser geloggt wurde ([avatar] recover/clearing).",
            "Aufführungs-Tab im Vordergrund lassen, damit Timer nicht drosseln.",
            "CSV-duration_ms des Clips im Katalog gegen die gemessene Lücke legen.",
            "Nach Recovery: Abstände der folgenden Clips prüfen (kein Cascade).",
        ],
    ),
    "signal_drop": (
        "Signal ohne Empfangs-ACK (bei euch erwartet)",
        "({detail}). Pixera sendet bei euch kein /avatar/done und keinen "
        "receiver.seen-ACK — die Steuerung ist rein zeitbasiert (CSV-Dauer). "
        "send_completed ohne Empfang ist deshalb normal und kein Beweis für "
        "verlorene OSC. Handlungsrelevant sind nur send_failed / gar nicht gebaut.",
        [
            "Info-Hinweise ohne Empfänger ignorieren — so ist euer Setup gebaut.",
            "Nur bei send_failed oder fehlendem send_completed OSC_HOST/Ports prüfen.",
            "Visuell am Beamer prüfen, ob der Clip kam (kein ACK im Trace).",
        ],
    ),
}


def interpret_finding(finding: Finding) -> InterpretedFinding:
    title, interpretation_tmpl, actions = _FINDING_GUIDANCE.get(
        finding.kind,
        (
            finding.kind.replace("_", " "),
            "Auffälligkeit im Durchlauf: {detail}",
            ["Detail im Trace nachvollziehen und bei Wiederholung melden."],
        ),
    )
    return InterpretedFinding(
        severity=finding.severity,
        kind=finding.kind,
        title=title,
        interpretation=interpretation_tmpl.format(detail=finding.detail),
        action_steps=list(actions),
        detail=finding.detail,
        ts_wall=finding.ts_wall,
        count=finding.count,
        duration_ms=finding.duration_ms,
        cues=list(finding.cues),
    )


# Prefer show-flow disruptions over raw signal_drop noise when choosing the headline.
_HEADLINE_KIND_PRIORITY = (
    "avatar_chain_catchup",
    "avatar_chain_stall",
    "execute_storm",
    "keyword_storm",
    "companion_after_avatar_end",
    "pause_or_stall",
    "signal_drop",
)


def _pick_lead_finding(findings: list[InterpretedFinding]) -> InterpretedFinding | None:
    if not findings:
        return None
    by_kind = {f.kind: f for f in findings}
    for kind in _HEADLINE_KIND_PRIORITY:
        if kind in by_kind:
            return by_kind[kind]
    return findings[0]


def interpret_show_run(report: ShowRunReport) -> ShowRunInterpretation:
    interpreted = [interpret_finding(f) for f in report.findings]
    critical = [f for f in interpreted if f.severity == "critical"]
    warns = [f for f in interpreted if f.severity == "warn"]
    lead_pool = critical or warns
    lead = _pick_lead_finding(lead_pool)

    if critical:
        verdict = "critical"
        headline = lead.title if lead else "Kritische Ablaufstörung"
        summary = (
            f"{len(critical)} kritische und {len(warns)} weitere Auffälligkeiten. "
            f"Zuerst: {(lead.title if lead else headline).lower()}."
        )
    elif warns:
        verdict = "issues"
        headline = lead.title if lead else "Auffälligkeiten im Durchlauf"
        summary = (
            f"{len(warns)} Warnungen im Durchlauf "
            f"({report.duration_sec:.0f}s, {report.executes} Executes)."
        )
    else:
        verdict = "ok"
        headline = "Durchlauf wirkt stabil"
        summary = (
            f"Keine kritischen Ablaufstörungen. "
            f"{report.executes} Executes, {report.commands_built} Commands "
            f"in {report.duration_sec:.0f}s."
        )

    # Action order: lead finding first, then other non-info by severity.
    ordered_for_actions: list[InterpretedFinding] = []
    if lead:
        ordered_for_actions.append(lead)
    for finding in interpreted:
        if finding.severity == "info":
            continue
        if lead and finding.kind == lead.kind and finding.detail == lead.detail:
            continue
        ordered_for_actions.append(finding)

    priority_actions: list[str] = []
    seen: set[str] = set()
    for finding in ordered_for_actions:
        for step in finding.action_steps:
            if step in seen:
                continue
            seen.add(step)
            priority_actions.append(step)
            if len(priority_actions) >= 6:
                break
        if len(priority_actions) >= 6:
            break

    if verdict == "ok" and not priority_actions:
        priority_actions = [
            "Optional: kurzen Smoke mit echtem Pixera/Licht vor Ort machen.",
            "Trace archivieren (make prepare-tryout), bevor der nächste Lauf startet.",
        ]

    return ShowRunInterpretation(
        verdict=verdict,
        headline=headline,
        summary=summary,
        priority_actions=priority_actions,
        findings=interpreted,
    )


def format_show_run_report(report: ShowRunReport) -> str:
    cats = ", ".join(f"{k}={v}" for k, v in sorted(report.category_counts.items()))
    actionable_drops = sum(
        1
        for f in report.findings
        if f.kind == "signal_drop" and f.severity in {"warn", "critical"}
    )
    interpreted = interpret_show_run(report)
    lines = [
        f"Run {report.run_id}"
        + (f"  fe={report.frontend_run_id}" if report.frontend_run_id else ""),
        f"  {report.ts_start or '?'} → {report.ts_end or '?'}  ({report.duration_sec}s)",
        f"  executes={report.executes}  commands={report.commands_built}  "
        f"send_ok={report.send_completed}  send_fail={report.send_failed}  "
        f"drop_findings={actionable_drops}  drop_reports={len(report.drops)}",
    ]
    if cats:
        lines.append(f"  categories: {cats}")
    lines.extend(
        [
            "",
            f"VERDICT: {interpreted.verdict.upper()} — {interpreted.headline}",
            f"  {interpreted.summary}",
            "",
            "PRIORITY ACTIONS:",
        ]
    )
    for step in interpreted.priority_actions:
        lines.append(f"  - {step}")
    lines.append("")
    lines.append("FINDINGS:")
    if not interpreted.findings:
        lines.append("  (none)")
    else:
        for finding in interpreted.findings:
            ts = (finding.ts_wall or "")[11:19] if finding.ts_wall else ""
            prefix = f"  {finding.severity.upper():8} {finding.kind:28}"
            mid = f" @{ts}" if ts else ""
            lines.append(f"{prefix}{mid}  {finding.title}: {finding.detail}")
            lines.append(f"           → {finding.interpretation}")
            for step in finding.action_steps[:2]:
                lines.append(f"           • {step}")
    return "\n".join(lines)
