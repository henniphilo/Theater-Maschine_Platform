"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { setMirroredActiveProductionId } from "@/lib/activeProduction";
import {
  createProduction,
  fetchActiveProduction,
  listProductions,
  setActiveProduction
} from "@/lib/api/productions";
import type { Production } from "@/lib/types/production";

export default function ProductionsPage() {
  const [productions, setProductions] = useState<Production[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [rows, active] = await Promise.all([listProductions(true), fetchActiveProduction()]);
      setProductions(rows);
      setActiveId(active.production_id);
      setMirroredActiveProductionId(active.production_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      await createProduction({
        name: name.trim(),
        description: description.trim() || undefined
      });
      setName("");
      setDescription("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anlegen fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  async function onActivate(production: Production) {
    if (production.status === "archived") return;
    setError(null);
    try {
      const active = await setActiveProduction(production.id);
      setActiveId(active.production_id);
      setMirroredActiveProductionId(active.production_id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Aktivieren fehlgeschlagen");
    }
  }

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Produktionen</h1>
      </div>
      <p className="textMuted">
        Plattform-Registry (MS1). Aktive Produktion wird serverseitig in{" "}
        <code>data/active_production.json</code> gehalten — siehe{" "}
        <code>docs/active-production.md</code>.
      </p>

      {activeId ? (
        <p>
          Aktiv: <strong>{productions.find((p) => p.id === activeId)?.name ?? activeId}</strong>
        </p>
      ) : (
        <p className="textMuted">Keine aktive Produktion gewählt.</p>
      )}

      {error ? <p className="textError">{error}</p> : null}

      <section className="col" style={{ gap: "var(--space-3)", maxWidth: 520 }}>
        <h2>Neue Produktion</h2>
        <form className="col" style={{ gap: "var(--space-3)" }} onSubmit={onCreate}>
          <label className="col" style={{ gap: 4 }}>
            <span>Name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="z. B. Unter Tieren"
              required
            />
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Beschreibung (optional)</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </label>
          <button type="submit" disabled={saving || !name.trim()}>
            {saving ? "Speichern…" : "Anlegen"}
          </button>
        </form>
      </section>

      <section className="col" style={{ gap: "var(--space-3)" }}>
        <h2>Liste</h2>
        {loading ? <p className="textMuted">Laden…</p> : null}
        {!loading && productions.length === 0 ? (
          <p className="textMuted">Noch keine Produktionen.</p>
        ) : null}
        <ul className="col" style={{ gap: "var(--space-2)", listStyle: "none", padding: 0 }}>
          {productions.map((production) => {
            const isActive = production.id === activeId;
            return (
              <li
                key={production.id}
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
                  <strong>{production.name}</strong>
                  <span className="textMuted">
                    {production.slug} · {production.status}
                    {isActive ? " · aktiv" : ""}
                  </span>
                </div>
                <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
                  <Link href={`/productions/${production.id}`}>Öffnen</Link>
                  <button
                    type="button"
                    disabled={production.status === "archived" || isActive}
                    onClick={() => void onActivate(production)}
                  >
                    {isActive ? "Aktiv" : "Als aktiv"}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </main>
  );
}
