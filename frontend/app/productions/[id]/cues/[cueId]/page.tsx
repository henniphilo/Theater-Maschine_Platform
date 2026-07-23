"use client";

import type { Route } from "next";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { deleteCue, dryRunCue, fetchCue, updateCue } from "@/lib/api/cues";
import { fetchProduction } from "@/lib/api/productions";
import type { Cue, CueType } from "@/lib/types/cue";
import { CUE_ACTIONS, CUE_TYPES } from "@/lib/types/cue";
import type { Production } from "@/lib/types/production";

export default function CueDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productionId = typeof params.id === "string" ? params.id : "";
  const cueId = typeof params.cueId === "string" ? params.cueId : "";

  const [production, setProduction] = useState<Production | null>(null);
  const [cue, setCue] = useState<Cue | null>(null);
  const [name, setName] = useState("");
  const [cueType, setCueType] = useState<CueType>("wait");
  const [action, setAction] = useState("wait");
  const [enabled, setEnabled] = useState(true);
  const [priority, setPriority] = useState(0);
  const [parametersJson, setParametersJson] = useState("{}");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dryRunResult, setDryRunResult] = useState<string | null>(null);
  const [dryRunning, setDryRunning] = useState(false);

  const refresh = useCallback(async () => {
    if (!productionId || !cueId) return;
    setError(null);
    try {
      const [prod, row] = await Promise.all([
        fetchProduction(productionId),
        fetchCue(cueId, productionId)
      ]);
      setProduction(prod);
      setCue(row);
      setName(row.name);
      setCueType(row.cue_type);
      setAction(row.action);
      setEnabled(row.enabled);
      setPriority(row.priority);
      setParametersJson(JSON.stringify(row.parameters ?? {}, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
      setCue(null);
      setProduction(null);
    } finally {
      setLoading(false);
    }
  }, [productionId, cueId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!cue || saving) return;
    setSaving(true);
    setError(null);
    try {
      const parameters = JSON.parse(parametersJson) as Record<string, unknown>;
      const updated = await updateCue(cue.id, {
        name: name.trim(),
        cue_type: cueType,
        action,
        enabled,
        priority,
        parameters
      });
      setCue(updated);
      setName(updated.name);
      setCueType(updated.cue_type);
      setAction(updated.action);
      setEnabled(updated.enabled);
      setPriority(updated.priority);
      setParametersJson(JSON.stringify(updated.parameters ?? {}, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  async function onDryRun() {
    if (!cue) return;
    setDryRunning(true);
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
      setDryRunning(false);
    }
  }

  async function onDelete() {
    if (!cue) return;
    if (!window.confirm(`Cue „${cue.name}“ löschen?`)) return;
    try {
      await deleteCue(cue.id, productionId);
      router.push(`/productions/${productionId}/cues` as Route);
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

  if (!cue || !production) {
    return (
      <main className="container col">
        <p className="textError">{error ?? "Cue nicht gefunden"}</p>
        <Link href={`/productions/${productionId}/cues` as Route}>Zurück zu Cues</Link>
      </main>
    );
  }

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>{cue.name}</h1>
      </div>
      <p>
        <Link href={`/productions/${production.id}/cues` as Route}>
          ← Cues · {production.name}
        </Link>
      </p>

      {error ? <p className="textError">{error}</p> : null}

      <section className="col" style={{ gap: "var(--space-3)", maxWidth: 560 }}>
        <h2>Bearbeiten</h2>
        <form className="col" style={{ gap: "var(--space-3)" }} onSubmit={(e) => void onSave(e)}>
          <label className="col" style={{ gap: 4 }}>
            <span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Typ</span>
            <select
              value={cueType}
              onChange={(e) => {
                const next = e.target.value as CueType;
                setCueType(next);
                setAction(CUE_ACTIONS[next][0] ?? "wait");
              }}
            >
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
            <span>Priorität</span>
            <input
              type="number"
              value={priority}
              onChange={(e) => setPriority(Number(e.target.value))}
            />
          </label>
          <label style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            <span>Aktiviert</span>
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Parameter (JSON)</span>
            <textarea
              value={parametersJson}
              onChange={(e) => setParametersJson(e.target.value)}
              rows={10}
              style={{ fontFamily: "ui-monospace, monospace" }}
            />
          </label>
          <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
            <button type="submit" disabled={saving || !name.trim()}>
              {saving ? "Speichern…" : "Speichern"}
            </button>
            <button type="button" disabled={dryRunning} onClick={() => void onDryRun()}>
              {dryRunning ? "Dry-Run…" : "Dry-Run testen"}
            </button>
            <button type="button" onClick={() => void onDelete()}>
              Löschen
            </button>
          </div>
        </form>
      </section>

      {dryRunResult ? (
        <section className="col" style={{ gap: "var(--space-2)" }}>
          <h2>Dry-Run Ergebnis</h2>
          <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{dryRunResult}</pre>
        </section>
      ) : null}

      <dl className="col" style={{ gap: "var(--space-2)" }}>
        <div>
          <dt className="textMuted">ID</dt>
          <dd>
            <code>{cue.id}</code>
          </dd>
        </div>
        <div>
          <dt className="textMuted">Asset</dt>
          <dd>{cue.asset_id ?? "—"}</dd>
        </div>
        <div>
          <dt className="textMuted">Device</dt>
          <dd>{cue.device_id ?? "— (Device-Meilenstein folgt)"}</dd>
        </div>
      </dl>
    </main>
  );
}
