"use client";

import type { Route } from "next";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { createCue, deleteCue, dryRunCue, listCues } from "@/lib/api/cues";
import { fetchProduction } from "@/lib/api/productions";
import type { Cue, CueType } from "@/lib/types/cue";
import { CUE_ACTIONS, CUE_TYPES, defaultParametersFor } from "@/lib/types/cue";
import type { Production } from "@/lib/types/production";

export default function ProductionCuesPage() {
  const params = useParams();
  const productionId = typeof params.id === "string" ? params.id : "";

  const [production, setProduction] = useState<Production | null>(null);
  const [cues, setCues] = useState<Cue[]>([]);
  const [typeFilter, setTypeFilter] = useState<CueType | "">("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dryRunResult, setDryRunResult] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [cueType, setCueType] = useState<CueType>("wait");
  const [action, setAction] = useState("wait");
  const [parametersJson, setParametersJson] = useState(
    JSON.stringify(defaultParametersFor("wait"), null, 2)
  );
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(async () => {
    if (!productionId) return;
    setError(null);
    try {
      const [prod, rows] = await Promise.all([
        fetchProduction(productionId),
        listCues({
          productionId,
          cueType: typeFilter || undefined
        })
      ]);
      setProduction(prod);
      setCues(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
      setProduction(null);
      setCues([]);
    } finally {
      setLoading(false);
    }
  }, [productionId, typeFilter]);

  useEffect(() => {
    setLoading(true);
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const actions = CUE_ACTIONS[cueType];
    setAction(actions[0] ?? "wait");
    setParametersJson(JSON.stringify(defaultParametersFor(cueType), null, 2));
  }, [cueType]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!productionId || creating || !name.trim()) return;
    setCreating(true);
    setError(null);
    setDryRunResult(null);
    try {
      const parameters = JSON.parse(parametersJson) as Record<string, unknown>;
      await createCue({
        production_id: productionId,
        name: name.trim(),
        cue_type: cueType,
        action,
        parameters
      });
      setName("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anlegen fehlgeschlagen");
    } finally {
      setCreating(false);
    }
  }

  async function onDryRun(cue: Cue) {
    setBusyId(cue.id);
    setError(null);
    setDryRunResult(null);
    try {
      const result = await dryRunCue(cue.id, productionId);
      setDryRunResult(
        `${result.status}: ${result.message}\n${JSON.stringify(result.planned, null, 2)}`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dry-Run fehlgeschlagen");
    } finally {
      setBusyId(null);
    }
  }

  async function onDelete(cue: Cue) {
    if (!window.confirm(`Cue „${cue.name}“ löschen?`)) return;
    setError(null);
    try {
      await deleteCue(cue.id, productionId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen");
    }
  }

  if (loading) {
    return (
      <main className="container col">
        <p className="textMuted">Laden…</p>
      </main>
    );
  }

  if (!production) {
    return (
      <main className="container col">
        <p className="textError">{error ?? "Produktion nicht gefunden"}</p>
        <Link href="/productions">Zurück zur Liste</Link>
      </main>
    );
  }

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Cues</h1>
      </div>
      <p>
        <Link href={`/productions/${production.id}`}>← {production.name}</Link>
      </p>
      <p className="textMuted">
        Ausführbare Aktionen dieser Produktion. Dry-Run plant nur — keine Hardwareausgabe.
      </p>

      {error ? <p className="textError">{error}</p> : null}

      <section className="col" style={{ gap: "var(--space-3)", maxWidth: 560 }}>
        <h2>Neuen Cue anlegen</h2>
        <form className="col" style={{ gap: "var(--space-3)" }} onSubmit={(e) => void onCreate(e)}>
          <label className="col" style={{ gap: 4 }}>
            <span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Typ</span>
            <select value={cueType} onChange={(e) => setCueType(e.target.value as CueType)}>
              {CUE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Aktion</span>
            <select value={action} onChange={(e) => setAction(e.target.value)}>
              {CUE_ACTIONS[cueType].map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Parameter (JSON)</span>
            <textarea
              value={parametersJson}
              onChange={(e) => setParametersJson(e.target.value)}
              rows={8}
              style={{ fontFamily: "ui-monospace, monospace" }}
            />
          </label>
          <button type="submit" disabled={creating || !name.trim()}>
            {creating ? "Anlegen…" : "Cue anlegen"}
          </button>
        </form>
      </section>

      <label className="col" style={{ gap: 4, maxWidth: 280 }}>
        <span>Typfilter</span>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter((e.target.value || "") as CueType | "")}
        >
          <option value="">Alle Typen</option>
          {CUE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <section className="col" style={{ gap: "var(--space-3)" }}>
        <h2>Cue-Liste</h2>
        {cues.length === 0 ? (
          <p className="textMuted">Noch keine Cues.</p>
        ) : (
          <ul className="col" style={{ gap: "var(--space-2)", listStyle: "none", padding: 0 }}>
            {cues.map((cue) => (
              <li
                key={cue.id}
                style={{
                  border: "1px solid var(--color-border)",
                  padding: "var(--space-3)",
                  borderRadius: "var(--radius-md)",
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "var(--space-3)",
                  alignItems: "center",
                  justifyContent: "space-between"
                }}
              >
                <div className="col" style={{ gap: 2 }}>
                  <strong>{cue.name}</strong>
                  <span className="textMuted">
                    {cue.cue_type} · {cue.action}
                    {cue.enabled ? "" : " · deaktiviert"} · Prio {cue.priority}
                  </span>
                </div>
                <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                  <Link href={`/productions/${production.id}/cues/${cue.id}` as Route}>
                    Bearbeiten
                  </Link>
                  <button
                    type="button"
                    disabled={busyId === cue.id}
                    onClick={() => void onDryRun(cue)}
                  >
                    Dry-Run
                  </button>
                  <button type="button" onClick={() => void onDelete(cue)}>
                    Löschen
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {dryRunResult ? (
        <section className="col" style={{ gap: "var(--space-2)" }}>
          <h2>Dry-Run Ergebnis</h2>
          <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{dryRunResult}</pre>
        </section>
      ) : null}
    </main>
  );
}
