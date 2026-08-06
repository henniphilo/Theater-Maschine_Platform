"use client";

import type { Route } from "next";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  acceptDirectorProposal,
  DirectorStatus,
  fetchDirectorStatus,
  patchDirectorSafety,
  postDirectorEmergencyClear,
  postDirectorEmergencyStop,
  postRecordStart,
  postRecordStop,
  rejectDirectorProposal,
  streamDirectorEvents
} from "@/lib/api/director";
import { displayReasonShort, dramaturgicalFunctionLabel } from "@/lib/dramaturgy/labels";
import { formatOscCommand } from "@/lib/types/director";

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

function densityValue(state: Record<string, unknown> | undefined, key: string): number {
  const raw = state?.[key];
  return typeof raw === "number" ? Math.max(0, Math.min(1, raw)) : 0;
}

export default function DirectorPage() {
  const [status, setStatus] = useState<DirectorStatus | null>(null);
  const [error, setError] = useState("");
  const [recordingId, setRecordingId] = useState("recording_live_001");
  const [loading, setLoading] = useState(false);
  const [showDebug, setShowDebug] = useState(false);

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
        ...(prev ?? {}),
        safety: update.safety,
        active_cues: update.active_cues,
        last_event: update.event,
        last_decision: update.decision,
        last_executed: update.executed,
        last_blocked_reason: update.blocked_reason,
        last_planned_commands: update.planned_commands ?? prev?.last_planned_commands ?? [],
        last_osc_commands: update.last_osc_commands ?? update.osc_commands ?? []
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

  async function handleAcceptProposal(proposalId: string) {
    setLoading(true);
    try {
      await acceptDirectorProposal(proposalId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Vorschlag annehmen fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }

  async function handleRejectProposal(proposalId: string) {
    setLoading(true);
    try {
      await rejectDirectorProposal(proposalId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Vorschlag ablehnen fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }

  const lastEvent = status?.last_event;
  const lastDecision = status?.last_decision;
  const dramaturgyState = (status?.dramaturgy_state ?? {}) as Record<string, unknown>;
  const musicDensity = densityValue(dramaturgyState, "music_density");
  const videoDensity = densityValue(dramaturgyState, "video_density");
  const totalDensity = densityValue(dramaturgyState, "total_media_density");
  const decisionReason = displayReasonShort(
    typeof lastDecision?.reason_short === "string" ? lastDecision.reason_short : null,
    typeof lastDecision?.reason === "string" ? lastDecision.reason : null
  );
  const decisionFunction =
    typeof lastDecision?.dramaturgical_function === "string"
      ? lastDecision.dramaturgical_function
      : null;
  const decisionKind =
    typeof lastDecision?.decision_kind === "string" ? lastDecision.decision_kind : null;

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Live-Regie Operator</h1>
        <Link href="/director/analysis">Probe-Analyse →</Link>
      </div>
      <p className="textMuted">Safety zuerst, dann Regievorschläge — Debug nur bei Bedarf.</p>

      {status?.active_production_id ? (
        <p>
          Aktive Produktion:{" "}
          <Link href={`/productions/${status.active_production_id}` as Route}>
            {status.active_production_name ?? status.active_production_id}
          </Link>
          {status.active_production_slug ? (
            <span className="textMuted"> ({status.active_production_slug})</span>
          ) : null}
        </p>
      ) : (
        <p className="textMuted">
          Keine aktive Produktion — <Link href={"/productions" as Route}>Produktionen</Link>
        </p>
      )}

      {error ? (
        <div role="alert" className="textError">
          {error}
        </div>
      ) : null}

      <section className="card col">
        <h2>Safety & Steuerung</h2>
        {status ? (
          <>
            <div className="row" style={{ flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
              <button
                type="button"
                className="emergencyStopBtn"
                onClick={handleEmergencyStop}
                disabled={loading}
              >
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
              <p className="textError" role="alert">
                Emergency Stop aktiv — Ausgabe gesperrt.
              </p>
            ) : null}
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
          </>
        ) : (
          <p className="textFaint">Lade Status …</p>
        )}
      </section>

      <section className="card col">
        <h2>Letzte Regieentscheidung</h2>
        {lastDecision ? (
          <div className="directorDecisionCard">
            <strong>
              {dramaturgicalFunctionLabel(decisionFunction) || decisionKind || "Entscheidung"}
            </strong>
            {decisionReason ? <p style={{ margin: 0 }}>{decisionReason}</p> : null}
            <p className="textMuted" style={{ margin: 0, fontSize: "0.9rem" }}>
              Ausgeführt: {status?.last_executed ? "ja" : "nein"}
              {status?.last_blocked_reason ? ` · blockiert: ${status.last_blocked_reason}` : ""}
              {decisionKind === "none" ? " · Stille / Space" : ""}
            </p>
          </div>
        ) : (
          <p className="textFaint">Noch keine Entscheidung.</p>
        )}
      </section>

      <section className="card col">
        <h2>Mediendichte</h2>
        {status?.dramaturgy_state ? (
          <div className="directorDensityMeter">
            {(
              [
                ["Musik", musicDensity],
                ["Video", videoDensity],
                ["Gesamt", totalDensity]
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="directorDensityRow">
                <span>{label}</span>
                <div className="directorDensityTrack" aria-hidden="true">
                  <div className="directorDensityFill" style={{ width: `${Math.round(value * 100)}%` }} />
                </div>
                <span>{Math.round(value * 100)}%</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="textFaint">Noch kein Zustand.</p>
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
        <h2>Dramaturgie-Vorschläge</h2>
        {status?.open_proposals?.length ? (
          <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none" }}>
            {status.open_proposals.map((proposal) => {
              const reason = displayReasonShort(
                proposal.reason_short,
                proposal.decision?.reason
              );
              return (
                <li key={proposal.proposal_id} className="col" style={{ gap: "0.35rem", marginBottom: "0.75rem" }}>
                  <strong>{proposal.text_snippet || "Regievorschlag"}</strong>
                  {reason ? (
                    <span className="textMuted">
                      {dramaturgicalFunctionLabel(
                        proposal.dramaturgical_function ?? proposal.decision?.dramaturgical_function
                      )}{" "}
                      · – {reason}
                    </span>
                  ) : null}
                  <div className="row">
                    <button
                      type="button"
                      onClick={() => handleAcceptProposal(proposal.proposal_id)}
                      disabled={loading || status.safety.emergency_stop_active}
                    >
                      Annehmen
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRejectProposal(proposal.proposal_id)}
                      disabled={loading}
                    >
                      Ablehnen
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="textFaint">Keine offenen Vorschläge.</p>
        )}
      </section>

      <section className="card col">
        <h2>Letzte OSC-Befehle</h2>
        {status?.last_osc_commands?.length ? (
          <ul className="regieOscList" style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {status.last_osc_commands.map((cmd, i) => (
              <li key={`${cmd.address}-${i}`}>
                <code>{formatOscCommand(cmd)}</code>
              </li>
            ))}
          </ul>
        ) : status?.last_planned_commands?.length ? (
          <>
            <p className="textFaint">Noch nicht gesendet — geplant:</p>
            <ul className="regieOscList" style={{ margin: 0, paddingLeft: "1.2rem" }}>
              {status.last_planned_commands.map((cmd, i) => (
                <li key={`${cmd.address}-${i}`}>
                  <code>{formatOscCommand(cmd)}</code>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="textFaint">Noch keine OSC-Befehle — Debatte im Show-Modus starten.</p>
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
          <p className="textFaint">Keine aktiven Cues.</p>
        )}
      </section>

      <section className="card col">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>Debug</h2>
          <button type="button" onClick={() => setShowDebug((v) => !v)} aria-expanded={showDebug}>
            {showDebug ? "Ausblenden" : "Rohdaten zeigen"}
          </button>
        </div>
        {showDebug ? (
          <>
            <h3>Dramaturgie-Zustand</h3>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
              {JSON.stringify(status?.dramaturgy_state ?? {}, null, 2)}
            </pre>
            <h3>Letzter Dialogue-Event</h3>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
              {JSON.stringify(lastEvent ?? null, null, 2)}
            </pre>
            <h3>Letzte Entscheidung (roh)</h3>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
              {JSON.stringify(lastDecision ?? null, null, 2)}
            </pre>
          </>
        ) : (
          <p className="textFaint">JSON-Rohdaten sind ausgeblendet.</p>
        )}
      </section>
    </main>
  );
}
