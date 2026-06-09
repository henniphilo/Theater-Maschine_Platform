"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  DirectorStatus,
  fetchDirectorStatus,
  patchDirectorSafety,
  postDirectorEmergencyClear,
  postDirectorEmergencyStop,
  postRecordStart,
  postRecordStop,
  streamDirectorEvents
} from "@/lib/api/director";

function FlagButton({
  label,
  active,
  onClick,
  disabled
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-pressed={active}>
      {label}: {active ? "AN" : "AUS"}
    </button>
  );
}

export default function DirectorPage() {
  const [status, setStatus] = useState<DirectorStatus | null>(null);
  const [error, setError] = useState("");
  const [recordingId, setRecordingId] = useState("recording_live_001");
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const next = await fetchDirectorStatus();
      setStatus(next);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Status konnte nicht geladen werden");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const stop = streamDirectorEvents((update) => {
      setStatus((prev) => ({
        safety: update.safety,
        active_cues: update.active_cues,
        last_event: update.event,
        last_decision: update.decision,
        last_executed: update.executed,
        last_blocked_reason: update.blocked_reason,
        ...(prev ?? {})
      }));
    });
    return stop;
  }, [refresh]);

  async function toggleSafety(key: keyof DirectorStatus["safety"]) {
    if (!status) return;
    setLoading(true);
    try {
      const next = await patchDirectorSafety({ [key]: !status.safety[key] });
      setStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }

  async function handleEmergencyStop() {
    setLoading(true);
    try {
      setStatus(await postDirectorEmergencyStop());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Emergency Stop fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }

  async function handleEmergencyClear() {
    setLoading(true);
    try {
      setStatus(await postDirectorEmergencyClear());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Freigabe fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }

  async function handleRecordStart() {
    setLoading(true);
    try {
      await postRecordStart(recordingId.trim() || "recording_live_001");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Aufnahme starten fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }

  async function handleRecordStop() {
    setLoading(true);
    try {
      await postRecordStop();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Aufnahme stoppen fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }

  const lastEvent = status?.last_event;
  const lastDecision = status?.last_decision;

  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Live-Regie Operator</h1>
        <Link href="/">← Zur Debatte</Link>
      </div>
      <p style={{ margin: 0, color: "#6b5e4a" }}>
        Semi-autonome Regie: Safety-Flags, Emergency Stop, Aufnahme-Steuerung.
      </p>

      {error ? (
        <div role="alert" style={{ color: "#8b2020" }}>
          {error}
        </div>
      ) : null}

      <section className="card col">
        <h2>Safety & Steuerung</h2>
        {status ? (
          <>
            <div className="row" style={{ flexWrap: "wrap" }}>
              <FlagButton
                label="Autopilot"
                active={status.safety.autopilot_enabled}
                onClick={() => toggleSafety("autopilot_enabled")}
                disabled={loading || status.safety.emergency_stop_active}
              />
              <FlagButton
                label="Visuals"
                active={status.safety.visuals_enabled}
                onClick={() => toggleSafety("visuals_enabled")}
                disabled={loading || status.safety.emergency_stop_active}
              />
              <FlagButton
                label="Sound"
                active={status.safety.sound_enabled}
                onClick={() => toggleSafety("sound_enabled")}
                disabled={loading || status.safety.emergency_stop_active}
              />
              <FlagButton
                label="Licht"
                active={status.safety.lights_enabled}
                onClick={() => toggleSafety("lights_enabled")}
                disabled={loading || status.safety.emergency_stop_active}
              />
              <FlagButton
                label="Blackout-Sperre"
                active={status.safety.blackout_locked}
                onClick={() => toggleSafety("blackout_locked")}
                disabled={loading}
              />
            </div>
            <div className="row">
              <button type="button" onClick={handleEmergencyStop} disabled={loading}>
                Emergency Stop
              </button>
              <button
                type="button"
                onClick={handleEmergencyClear}
                disabled={loading || !status.safety.emergency_stop_active}
              >
                Emergency aufheben
              </button>
              <button type="button" onClick={() => refresh()} disabled={loading}>
                Status aktualisieren
              </button>
            </div>
            {status.safety.emergency_stop_active ? (
              <p style={{ margin: 0, color: "#8b2020" }}>Emergency Stop aktiv — Ausgabe gesperrt.</p>
            ) : null}
          </>
        ) : (
          <p style={{ margin: 0, color: "#9c8e78" }}>Lade Status …</p>
        )}
      </section>

      <section className="card col">
        <h2>Aufnahme</h2>
        <label htmlFor="recording-id">Recording-ID</label>
        <input
          id="recording-id"
          value={recordingId}
          onChange={(e) => setRecordingId(e.target.value)}
          disabled={loading}
        />
        <div className="row">
          <button type="button" onClick={handleRecordStart} disabled={loading}>
            Record Start
          </button>
          <button type="button" onClick={handleRecordStop} disabled={loading}>
            Record Stop
          </button>
        </div>
      </section>

      <section className="card col">
        <h2>Letzter Dialogue-Event</h2>
        {lastEvent ? (
          <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
            {JSON.stringify(lastEvent, null, 2)}
          </pre>
        ) : (
          <p style={{ margin: 0, color: "#9c8e78" }}>Noch kein Event — Debatte starten oder Test-Event senden.</p>
        )}
      </section>

      <section className="card col">
        <h2>Letzte Regieentscheidung</h2>
        {lastDecision ? (
          <>
            <p style={{ margin: 0 }}>
              Ausgeführt: {status?.last_executed ? "ja" : "nein"}
              {status?.last_blocked_reason ? ` (blockiert: ${status.last_blocked_reason})` : ""}
            </p>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
              {JSON.stringify(lastDecision, null, 2)}
            </pre>
          </>
        ) : (
          <p style={{ margin: 0, color: "#9c8e78" }}>Noch keine Entscheidung.</p>
        )}
      </section>

      <section className="card col">
        <h2>Aktive Cues</h2>
        {status?.active_cues?.length ? (
          <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {status.active_cues.map((cue) => (
              <li key={cue}>{cue}</li>
            ))}
          </ul>
        ) : (
          <p style={{ margin: 0, color: "#9c8e78" }}>Keine aktiven Cues.</p>
        )}
      </section>
    </main>
  );
}
