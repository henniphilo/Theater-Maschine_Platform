"use client";

import type { Route } from "next";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { fetchDramaturgyAnalysis } from "@/lib/api/director";
import type { DramaturgyAnalysisResponse } from "@/lib/dramaturgy/labels";
import { dramaturgicalFunctionLabel } from "@/lib/dramaturgy/labels";

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

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Dramaturgie-Analyse</h1>
        <Link href={"/director" as Route}>← Operator</Link>
      </div>
      <p className="textMuted">Entscheidungen aus Probe oder Aufführung — Text, Cue, Begründung.</p>

      {error ? (
        <div role="alert" className="textError">
          {error}
        </div>
      ) : null}

      <section className="card col">
        <div className="row">
          <button type="button" onClick={() => refresh()}>
            Aktualisieren
          </button>
        </div>
        {analysis?.dramaturgy_state ? (
          <details>
            <summary>Aktueller Dramaturgie-Zustand</summary>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
              {JSON.stringify(analysis.dramaturgy_state, null, 2)}
            </pre>
          </details>
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
                </div>
                {entry.text_snippet ? <p style={{ margin: "0.25rem 0" }}>{entry.text_snippet}</p> : null}
                {entry.cue_id ? (
                  <p style={{ margin: "0.25rem 0" }}>
                    ▶ {entry.cue_id}
                  </p>
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
