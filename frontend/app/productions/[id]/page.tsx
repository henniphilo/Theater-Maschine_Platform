"use client";

import type { Route } from "next";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { setMirroredActiveProductionId } from "@/lib/activeProduction";
import {
  archiveProduction,
  fetchActiveProduction,
  fetchProduction,
  setActiveProduction
} from "@/lib/api/productions";
import type { Production } from "@/lib/types/production";

export default function ProductionDetailPage() {
  const params = useParams();
  const id = typeof params.id === "string" ? params.id : "";
  const [production, setProduction] = useState<Production | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!id) return;
    setError(null);
    try {
      const [row, active] = await Promise.all([fetchProduction(id), fetchActiveProduction()]);
      setProduction(row);
      setActiveId(active.production_id);
      setMirroredActiveProductionId(active.production_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
      setProduction(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onActivate() {
    if (!production || production.status === "archived") return;
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

  async function onArchive() {
    if (!production || production.status === "archived") return;
    if (!window.confirm(`Produktion „${production.name}“ archivieren?`)) return;
    setError(null);
    try {
      const archived = await archiveProduction(production.id);
      setProduction(archived);
      const active = await fetchActiveProduction();
      setActiveId(active.production_id);
      setMirroredActiveProductionId(active.production_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Archivieren fehlgeschlagen");
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

  const isActive = production.id === activeId;

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>{production.name}</h1>
      </div>
      <p>
        <Link href="/productions">← Produktionen</Link>
      </p>
      {error ? <p className="textError">{error}</p> : null}

      <dl className="col" style={{ gap: "var(--space-2)" }}>
        <div>
          <dt className="textMuted">Slug</dt>
          <dd>{production.slug}</dd>
        </div>
        <div>
          <dt className="textMuted">Status</dt>
          <dd>
            {production.status}
            {isActive ? " (aktiv)" : ""}
          </dd>
        </div>
        <div>
          <dt className="textMuted">Beschreibung</dt>
          <dd>{production.description || "—"}</dd>
        </div>
        <div>
          <dt className="textMuted">ID</dt>
          <dd>
            <code>{production.id}</code>
          </dd>
        </div>
      </dl>

      <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
        <Link href={`/productions/${production.id}/library` as Route}>Bibliothek</Link>
        <button
          type="button"
          disabled={production.status === "archived" || isActive}
          onClick={() => void onActivate()}
        >
          {isActive ? "Bereits aktiv" : "Als aktiv setzen"}
        </button>
        <button type="button" disabled={production.status === "archived"} onClick={() => void onArchive()}>
          Archivieren
        </button>
      </div>
    </main>
  );
}
