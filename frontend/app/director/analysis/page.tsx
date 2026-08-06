"use client";

import type { Route } from "next";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { fetchDramaturgyAnalysis } from "@/lib/api/director";
import type { DramaturgyAnalysisResponse } from "@/lib/dramaturgy/labels";
import { dramaturgicalFunctionLabel } from "@/lib/dramaturgy/labels";

function densityValue(state: Record<string, unknown> | undefined, key: string): number {
  const raw = state?.[key];
  return typeof raw === "number" ? Math.max(0, Math.min(1, raw)) : 0;
}

export default function DramaturgyAnalysisPage() {
  const [analysis, setAnalysis] = useState<DramaturgyAnalysisResponse | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      setAnalysis(await fetchDramaturgyAnalysis(200));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analyse konnte nicht geladen werden");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const summary = analysis?.summary;
  const state = analysis?.dramaturgy_state ?? {};

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Dramaturgie-Analyse</h1>
        <Link href={"/director" as Route}>← Operator</Link>
      </div>
      <p className="textMuted">
        Nach der Probe: Dichte, Stille und Begründungen — als Ausgangspunkt für den nächsten Prepare.
      </p>

      {error ? (
        <div role="alert" className="textError">
          {error}
        </div>
      ) : null}

      <section className="card col">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>Überblick</h2>
          <button type="button" onClick={() => refresh()}>
            Aktualisieren
          </button>
        </div>
        {summary ? (
          <div className="reviewSummaryGrid">
            <div className="reviewStat">
              <strong>{summary.total_decisions}</strong>
              <span>Entscheidungen</span>
            </div>
            <div className="reviewStat">
              <strong>{summary.executed_count}</strong>
              <span>Ausgeführt</span>
            </div>
            <div className="reviewStat">
              <strong>{summary.blocked_count}</strong>
              <span>Blockiert</span>
            </div>
            <div className="reviewStat">
              <strong>{Math.round(summary.silence_ratio * 100)}%</strong>
              <span>Stille / Space ({summary.silence_count})</span>
            </div>
          </div>
        ) : (
          <p className="textFaint">Noch keine Zusammenfassung.</p>
        )}

        {summary && Object.keys(summary.function_counts).length > 0 ? (
          <div className="directorDensityMeter" style={{ marginTop: "1rem" }}>
            <h3 style={{ margin: 0, fontSize: "1rem" }}>Funktionen</h3>
            {Object.entries(summary.function_counts).map(([fn, count]) => {
              const max = Math.max(...Object.values(summary.function_counts), 1);
              return (
                <div key={fn} className="directorDensityRow">
                  <span>{dramaturgicalFunctionLabel(fn) || fn}</span>
                  <div className="directorDensityTrack" aria-hidden="true">
                    <div
                      className="directorDensityFill"
                      style={{ width: `${Math.round((count / max) * 100)}%` }}
                    />
                  </div>
                  <span>{count}</span>
                </div>
              );
            })}
          </div>
        ) : null}

        {summary && Object.keys(summary.blocked_reasons).length > 0 ? (
          <div style={{ marginTop: "1rem" }}>
            <h3 style={{ margin: "0 0 0.5rem", fontSize: "1rem" }}>Block-Gründe</h3>
            <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
              {Object.entries(summary.blocked_reasons).map(([reason, count]) => (
                <li key={reason}>
                  <code>{reason}</code> · {count}
                </li>
              ))}
            </ul>
            <p className="textMuted" style={{ fontSize: "0.85rem" }}>
              Hinweis für den nächsten Prepare: Dichte senken oder Silence-Cues bewusst setzen, wenn
              Blockierungen durch Medien-Dichte häufig sind.
            </p>
          </div>
        ) : null}

        {analysis?.dramaturgy_state ? (
          <div className="directorDensityMeter" style={{ marginTop: "1rem" }}>
            <h3 style={{ margin: 0, fontSize: "1rem" }}>Aktueller Zustand</h3>
            {(
              [
                ["Musik", densityValue(state, "music_density")],
                ["Video", densityValue(state, "video_density")],
                ["Gesamt", densityValue(state, "total_media_density")]
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
        ) : null}
      </section>

      <section className="card col">
        <h2>Entscheidungs-Timeline</h2>
        {analysis?.entries?.length ? (
          <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none" }}>
            {analysis.entries.map((entry) => (
              <li key={entry.decision_id} style={{ marginBottom: "1rem" }}>
                <div className="textMuted" style={{ fontSize: "0.85rem" }}>
                  {entry.created_at}
                  {entry.executed ? " · ausgeführt" : " · geplant"}
                  {entry.blocked_reason ? ` · blockiert (${entry.blocked_reason})` : ""}
                  {strIsSilence(entry) ? " · Stille" : ""}
                </div>
                {entry.text_snippet ? <p style={{ margin: "0.25rem 0" }}>{entry.text_snippet}</p> : null}
                {entry.cue_id ? (
                  <p style={{ margin: "0.25rem 0" }}>▶ {entry.cue_id}</p>
                ) : null}
                {entry.reason_short ? (
                  <p className="textMuted" style={{ margin: 0 }}>
                    {dramaturgicalFunctionLabel(entry.dramaturgical_function)} · – {entry.reason_short}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="textFaint">Noch keine protokollierten Entscheidungen.</p>
        )}
      </section>
    </main>
  );
}

function strIsSilence(entry: { decision: string; dramaturgical_function: string }): boolean {
  return entry.decision.toLowerCase() === "none" || entry.dramaturgical_function.toLowerCase() === "space";
}
