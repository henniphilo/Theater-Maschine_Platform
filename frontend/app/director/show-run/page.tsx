"use client";

import type { Route } from "next";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { fetchShowRunAnalysis, fetchShowRuns } from "@/lib/api/director";
import type {
  ShowRunAnalysisResponse,
  ShowRunListItem
} from "@/lib/types/showRunAnalysis";

function verdictClass(verdict: string): string {
  if (verdict === "critical") return "textError";
  if (verdict === "issues") return "textWarn";
  return "textMuted";
}

function severityLabel(severity: string): string {
  if (severity === "critical") return "Kritisch";
  if (severity === "warn") return "Warnung";
  return "Hinweis";
}

function formatClock(ts: string | null | undefined): string {
  if (!ts) return "—";
  const t = ts.includes("T") ? ts.slice(11, 19) : ts;
  return t || ts;
}

export default function ShowRunAnalysisPage() {
  const [runs, setRuns] = useState<ShowRunListItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [analysis, setAnalysis] = useState<ShowRunAnalysisResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadRuns = useCallback(async () => {
    const list = await fetchShowRuns(25);
    setRuns(list.runs);
    return list.runs;
  }, []);

  const loadAnalysis = useCallback(async (runId?: string) => {
    setLoading(true);
    try {
      const data = await fetchShowRunAnalysis(runId || null);
      setAnalysis(data);
      if (data.run_id) setSelectedRunId(data.run_id);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analyse konnte nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const list = await loadRuns();
      const prefer = selectedRunId || list[0]?.run_id;
      await loadAnalysis(prefer);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analyse konnte nicht geladen werden");
    }
  }, [loadAnalysis, loadRuns, selectedRunId]);

  useEffect(() => {
    void refresh();
    // Initial load only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const interpretation = analysis?.interpretation;
  const findings = interpretation?.findings ?? [];
  const actionable = findings.filter((f) => f.severity === "critical" || f.severity === "warn");
  const infos = findings.filter((f) => f.severity === "info");

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Durchlauf-Analyse</h1>
        <div className="row" style={{ gap: "1rem" }}>
          <Link href={"/director/analysis" as Route}>Probe-Analyse</Link>
          <Link href={"/director" as Route}>← Operator</Link>
        </div>
      </div>
      <p className="textMuted">
        Nach der Aufführung: Pausen, Avatar-Cascades, Cue-Stürme — mit Interpretation und
        nächsten Schritten.
      </p>

      {error ? (
        <div role="alert" className="textError">
          {error}
        </div>
      ) : null}

      <section className="card col">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
          <label className="col" style={{ flex: 1, gap: "0.35rem" }}>
            <span className="textMuted" style={{ fontSize: "0.85rem" }}>
              Durchlauf
            </span>
            <select
              value={selectedRunId}
              onChange={(e) => {
                const id = e.target.value;
                setSelectedRunId(id);
                void loadAnalysis(id);
              }}
              disabled={loading || runs.length === 0}
            >
              {runs.length === 0 ? <option value="">Kein Run im Trace</option> : null}
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {formatClock(run.ts_start)} · {run.run_id} ({run.event_count} events)
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={() => void refresh()} disabled={loading}>
            {loading ? "Lädt…" : "Aktualisieren"}
          </button>
        </div>
      </section>

      {interpretation ? (
        <section className="card col">
          <h2 style={{ margin: 0 }} className={verdictClass(interpretation.verdict)}>
            {interpretation.headline}
          </h2>
          <p style={{ margin: 0 }}>{interpretation.summary}</p>
          {analysis ? (
            <div className="reviewSummaryGrid">
              <div className="reviewStat">
                <strong>{Math.round(analysis.duration_sec)}s</strong>
                <span>Dauer</span>
              </div>
              <div className="reviewStat">
                <strong>{analysis.executes}</strong>
                <span>Executes</span>
              </div>
              <div className="reviewStat">
                <strong>{analysis.commands_built}</strong>
                <span>Commands</span>
              </div>
              <div className="reviewStat">
                <strong>{actionable.length}</strong>
                <span>Handlungsbedarf</span>
              </div>
            </div>
          ) : null}
          {analysis && Object.keys(analysis.category_counts).length > 0 ? (
            <p className="textMuted" style={{ margin: 0, fontSize: "0.9rem" }}>
              Kategorien:{" "}
              {Object.entries(analysis.category_counts)
                .sort((a, b) => b[1] - a[1])
                .map(([k, v]) => `${k} ${v}`)
                .join(" · ")}
            </p>
          ) : null}
        </section>
      ) : null}

      {interpretation && interpretation.priority_actions.length > 0 ? (
        <section className="card col">
          <h2 style={{ margin: 0 }}>Nächste Schritte</h2>
          <ol style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {interpretation.priority_actions.map((step) => (
              <li key={step} style={{ marginBottom: "0.5rem" }}>
                {step}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <section className="card col">
        <h2 style={{ margin: 0 }}>Befunde</h2>
        {actionable.length === 0 && infos.length === 0 ? (
          <p className="textFaint">Keine Auffälligkeiten für diesen Run.</p>
        ) : null}

        {actionable.map((finding, index) => (
          <article
            key={`${finding.kind}-${finding.ts_wall ?? index}`}
            className="col"
            style={{
              gap: "0.4rem",
              paddingBottom: "1rem",
              borderBottom: "1px solid var(--border, #333)"
            }}
          >
            <div className="row" style={{ justifyContent: "space-between", gap: "0.75rem" }}>
              <strong className={finding.severity === "critical" ? "textError" : "textWarn"}>
                {severityLabel(finding.severity)} · {finding.title}
              </strong>
              <span className="textMuted" style={{ fontSize: "0.85rem" }}>
                {formatClock(finding.ts_wall)}
              </span>
            </div>
            <p style={{ margin: 0 }}>{finding.interpretation}</p>
            <p className="textMuted" style={{ margin: 0, fontSize: "0.85rem" }}>
              <code>{finding.kind}</code> — {finding.detail}
            </p>
            {finding.action_steps.length > 0 ? (
              <div>
                <div className="textMuted" style={{ fontSize: "0.85rem", marginBottom: "0.25rem" }}>
                  Aktion
                </div>
                <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
                  {finding.action_steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </article>
        ))}

        {infos.length > 0 ? (
          <details>
            <summary className="textMuted">
              {infos.length} Hinweise (Info)
            </summary>
            <ul style={{ margin: "0.75rem 0 0", paddingLeft: "1.2rem" }}>
              {infos.map((finding, index) => (
                <li key={`${finding.kind}-info-${index}`} style={{ marginBottom: "0.5rem" }}>
                  <strong>{finding.title}</strong>
                  {finding.ts_wall ? ` @ ${formatClock(finding.ts_wall)}` : ""} — {finding.detail}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </section>
    </main>
  );
}
