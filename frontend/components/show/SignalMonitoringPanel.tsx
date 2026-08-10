"use client";

import { useEffect, useRef, useState } from "react";

import {
  fetchDirectorStatus,
  fetchOscLogRecent,
  type DirectorStatus
} from "@/lib/api/director";

const MAX_LINES = 200;
const POLL_MS = 600;

type TerminalLine = {
  id: string;
  text: string;
  kind: "osc" | "midi" | "queue" | "other";
};

function classifyLine(text: string): TerminalLine["kind"] {
  if (text.includes("[OSC ")) return "osc";
  if (text.includes("[MIDI ")) return "midi";
  if (text.includes("[OSC QUEUE]")) return "queue";
  return "other";
}

export function SignalMonitoringPanel() {
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [status, setStatus] = useState<DirectorStatus | null>(null);
  const [error, setError] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const prevTail = useRef<string[]>([]);
  const seq = useRef(0);
  const stickToBottom = useRef(true);

  useEffect(() => {
    void fetchDirectorStatus()
      .then(setStatus)
      .catch(() => undefined);

    const poll = async () => {
      try {
        const data = await fetchOscLogRecent(180);
        setError("");
        const incoming = data.lines;
        const prev = prevTail.current;
        let appendFrom = 0;
        if (prev.length > 0) {
          const last = prev[prev.length - 1];
          const idx = incoming.lastIndexOf(last);
          if (idx >= 0) {
            appendFrom = idx + 1;
          } else {
            // Log rotated or truncated — show the latest window.
            appendFrom = 0;
            setLines([]);
            seq.current = 0;
          }
        }
        prevTail.current = incoming;
        const freshSlice = incoming.slice(appendFrom);
        if (!freshSlice.length) return;
        setLines((prevLines) => {
          const mapped = freshSlice.map((text) => {
            seq.current += 1;
            return { id: `osc-${seq.current}`, text, kind: classifyLine(text) };
          });
          const next = appendFrom === 0 && prev.length === 0
            ? mapped
            : appendFrom === 0
              ? mapped
              : [...prevLines, ...mapped];
          return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "OSC-Log nicht lesbar");
      }
    };

    void poll();
    const id = window.setInterval(() => void poll(), POLL_MS);
    const statusId = window.setInterval(() => {
      void fetchDirectorStatus()
        .then(setStatus)
        .catch(() => undefined);
    }, 2000);

    return () => {
      window.clearInterval(id);
      window.clearInterval(statusId);
    };
  }, []);

  useEffect(() => {
    const el = listRef.current;
    if (!el || !stickToBottom.current) return;
    el.scrollTop = el.scrollHeight;
  }, [lines]);

  function clearTerminal() {
    // Drop the UI buffer only. Keep prevTail so the next poll appends only
    // lines written after clear — not the whole osc.log window again.
    setLines([]);
    setError("");
    stickToBottom.current = true;
  }

  const tryout = status?.safety.performance_tryout;
  const emergency = status?.safety.emergency_stop_active;

  return (
    <section className="card col signalMonitor" aria-label="Signal-Monitoring">
      <header className="signalMonitorHeader">
        <div>
          <h2>Signal-Monitoring</h2>
          <p className="textMuted">Terminal-Ausgabe · OSC / MIDI (logs/osc.log)</p>
        </div>
        <div className="signalMonitorHeaderActions">
          <button
            type="button"
            disabled={lines.length === 0 && !error}
            onClick={clearTerminal}
            aria-label="Terminal-Ausgabe leeren"
          >
            Clear
          </button>
          <span
            className={
              emergency ? "liveSignalChip" : "liveSignalChip liveSignalChipOn"
            }
          >
            {emergency ? "Emergency" : tryout ? "Probe" : "Live"}
          </span>
        </div>
      </header>

      <div className="signalMonitorMeta" aria-label="Aktive Cues">
        {status?.active_cues?.length ? (
          status.active_cues.slice(0, 4).map((cue) => (
            <span key={cue} className="liveSignalChip liveSignalChipOn">
              {cue}
            </span>
          ))
        ) : (
          <span className="liveSignalChip">Keine aktiven Cues</span>
        )}
      </div>

      <div
        className="signalMonitorLog signalMonitorTerminal"
        ref={listRef}
        role="log"
        aria-live="polite"
        onScroll={(e) => {
          const el = e.currentTarget;
          stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        }}
      >
        {error ? <p className="textError signalMonitorEmpty">{error}</p> : null}
        {!error && lines.length === 0 ? (
          <p className="textFaint signalMonitorEmpty">
            Warte auf OSC/MIDI-Zeilen … Sobald Signale gesendet werden, erscheinen sie hier wie im Terminal.
          </p>
        ) : null}
        {lines.length > 0 ? (
          <pre className="signalMonitorPre">
            {lines.map((line) => (
              <span key={line.id} className={`signalMonitorTermLine signalMonitorTermLine-${line.kind}`}>
                {line.text}
                {"\n"}
              </span>
            ))}
          </pre>
        ) : null}
      </div>
    </section>
  );
}
