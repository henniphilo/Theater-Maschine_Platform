"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { AppNav } from "@/components/layout/AppNav";
import { RegieCard } from "@/components/show/RegieCard";
import { momentSpeechLabel } from "@/features/inszenierung/inszenierungBuffer";
import { composeScript, fetchCorpus, streamKomposition } from "@/lib/api/inszenierung";
import type { CompositionMoment, KompositionStreamEvent, SceneCorpus } from "@/lib/types/inszenierung";
import type { DirectorPayload } from "@/lib/types/director";

function projectorLabel(moment: CompositionMoment): string {
  if (moment.projector_mode === "all") return "alle Beamer";
  const layers = moment.avatar_layers ?? [];
  if (layers.length > 1) {
    return layers.map((l) => l.projector ?? "?").join(", ");
  }
  return layers[0]?.projector ?? "auto";
}

function KompositionContent() {
  const searchParams = useSearchParams();
  const corpusId = searchParams.get("id") ?? sessionStorage.getItem("currentCorpusId") ?? "";
  const [corpus, setCorpus] = useState<SceneCorpus | null>(null);
  const [moments, setMoments] = useState<CompositionMoment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!corpusId) return;
    void fetchCorpus(corpusId).then((c) => {
      setCorpus(c);
      if (c.composition?.moments) setMoments(c.composition.moments);
    });
  }, [corpusId]);

  async function loadTimeline() {
    if (!corpusId || loading) return;
    setError("");
    setLoading(true);
    setMoments([]);
    try {
      const updated = await composeScript(corpusId);
      setCorpus(updated);
      setMoments(updated.composition?.moments ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Timeline fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }

  async function startKompositionStream() {
    if (!corpusId || loading) return;
    setError("");
    setLoading(true);
    setMoments([]);
    try {
      await streamKomposition(corpusId, {}, {
        onEvent: (event: KompositionStreamEvent) => {
          if (event.type === "moment" && event.moment) {
            setMoments((prev) => {
              const next = [...prev.filter((m) => m.id !== event.moment!.id), event.moment!];
              return next.sort((a, b) => a.order - b.order);
            });
          }
          if (event.type === "composition_plan" && event.composition) {
            setMoments(event.composition.moments);
          }
          if (event.type === "corpus_updated" && event.corpus) {
            setCorpus(event.corpus);
          }
          if (event.type === "done") setLoading(false);
        },
        onError: (detail) => setError(detail)
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Komposition fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Komposition</h1>
        <AppNav />
      </div>
      <p className="textMuted">
        Deterministische Timeline aus dem Avatar-Skript — Anarchie steigt über die CSV-Reihenfolge.
      </p>

      {corpus ? (
        <section className="card col">
          <button
            type="button"
            onClick={() => void loadTimeline()}
            disabled={loading}
          >
            {loading ? "Timeline wird geladen …" : "Timeline aus Skript laden"}
          </button>
          <button type="button" onClick={() => void startKompositionStream()} disabled={loading}>
            {loading ? "Lädt …" : "Timeline mit Fortschritt laden"}
          </button>
          {moments.length > 0 ? (
            <Link href={`/inszenierung/auffuehrung?id=${corpus.id}`} className="machineStartBtn" style={{ display: "inline-block" }}>
              Zur Aufführung →
            </Link>
          ) : null}
        </section>
      ) : null}

      <section className="card col">
        <h2>Beats ({moments.length})</h2>
        {moments.length === 0 ? (
          <p className="textFaint">Noch keine Beats.</p>
        ) : (
          moments.map((moment) => (
            <article key={moment.id} className="card col" style={{ marginBottom: "0.75rem" }}>
              <header className="row" style={{ justifyContent: "space-between" }}>
                <strong>#{moment.order + 1}</strong>
                <span className="textMuted">
                  {momentSpeechLabel(moment)} · {projectorLabel(moment)} · Anarchie{" "}
                  {(moment.anarchy_level * 100).toFixed(0)}% · Overlap{" "}
                  {(moment.overlap_with_previous * 100).toFixed(0)}%
                </span>
              </header>
              <p style={{ fontStyle: "italic" }}>{moment.text_excerpt}</p>
              {moment.dramaturgy ? (
                <RegieCard
                  director={
                    {
                      event: {},
                      decision: moment.dramaturgy,
                      executed: false,
                      blocked_reason: null,
                      planned_commands: [],
                      osc_commands: []
                    } as DirectorPayload
                  }
                  showPhase="planned"
                />
              ) : null}
            </article>
          ))
        )}
      </section>

      {error ? <div className="textError">{error}</div> : null}
      <Link href={`/inszenierung/analyse?id=${corpusId}`}>← Analyse</Link>
    </main>
  );
}

export default function KompositionPage() {
  return (
    <Suspense fallback={<main className="container"><p className="textFaint">Lade …</p></main>}>
      <KompositionContent />
    </Suspense>
  );
}
