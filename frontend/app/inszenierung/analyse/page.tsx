"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { AppNav } from "@/components/layout/AppNav";
import { fetchCorpus, streamAnalyse } from "@/lib/api/inszenierung";
import type { AnalyseStreamEvent, SceneCorpus } from "@/lib/types/inszenierung";

function AnalyseContent() {
  const searchParams = useSearchParams();
  const corpusId = searchParams.get("id") ?? sessionStorage.getItem("currentCorpusId") ?? "";
  const [corpus, setCorpus] = useState<SceneCorpus | null>(null);
  const [chat, setChat] = useState<{ speaker: string; content: string }[]>([]);
  const [concept, setConcept] = useState<SceneCorpus["gesamtkonzept"]>(null);
  const [thinking, setThinking] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!corpusId) return;
    void fetchCorpus(corpusId).then(setCorpus).catch(() => setError("Korpus nicht gefunden"));
  }, [corpusId]);

  async function startAnalyse() {
    if (!corpusId || loading) return;
    setError("");
    setLoading(true);
    setChat([]);
    setConcept(null);
    setThinking(null);
    try {
      await streamAnalyse(corpusId, {}, {
        onEvent: (event: AnalyseStreamEvent) => {
          if (event.type === "thinking" && event.speaker) {
            setThinking(event.speaker === "openai" ? "ChatGPT denkt …" : "Claude denkt …");
          }
          if (event.type === "discussion_turn" && event.content && event.speaker) {
            setThinking(null);
            setChat((prev) => [
              ...prev,
              {
                speaker: event.speaker === "openai" ? "ChatGPT" : "Claude",
                content: event.content
              }
            ]);
          }
          if (event.type === "gesamtkonzept" && event.gesamtkonzept) {
            setConcept(event.gesamtkonzept);
          }
          if (event.type === "corpus_updated" && event.corpus) {
            setCorpus(event.corpus);
            sessionStorage.setItem("currentCorpusId", event.corpus.id);
          }
          if (event.type === "done") {
            setThinking(null);
            setLoading(false);
          }
        },
        onError: (detail) => setError(detail)
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analyse fehlgeschlagen");
    } finally {
      setLoading(false);
      setThinking(null);
    }
  }

  const displayConcept = concept ?? corpus?.gesamtkonzept;

  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Analyse — Gesamtkonzept</h1>
        <AppNav />
      </div>
      <p className="textMuted">
        Dramaturgen diskutieren alle Tier-Szenen zum Thema Geld und formen ein Gesamtkonzept.
      </p>

      {corpus ? (
        <section className="card col">
          <h2>{corpus.title}</h2>
          <p className="textMuted">{corpus.scenes.length} Szenen</p>
          <button type="button" onClick={() => void startAnalyse()} disabled={loading || corpus.scenes.length === 0}>
            {loading ? "Analyse läuft …" : "Analyse starten"}
          </button>
          {displayConcept?.thesis ? (
            <Link href={`/inszenierung/komposition?id=${corpus.id}`} className="machineStartBtn" style={{ display: "inline-block" }}>
              Zur Komposition →
            </Link>
          ) : null}
        </section>
      ) : null}

      <section className="card col">
        <h2>Diskussion</h2>
        {chat.map((line, i) => (
          <div key={i} className="bubble bubbleAi">
            <strong>{line.speaker}</strong>
            <div className="bubbleContent">{line.content}</div>
          </div>
        ))}
        {thinking ? <p className="textMuted">{thinking}</p> : null}
      </section>

      {displayConcept ? (
        <section className="card col">
          <h2>Gesamtkonzept</h2>
          <p>{displayConcept.thesis}</p>
          {displayConcept.money_themes.length > 0 ? (
            <>
              <h3>Geld-Themen</h3>
              <ul>
                {displayConcept.money_themes.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </>
          ) : null}
          {displayConcept.animal_positions.length > 0 ? (
            <>
              <h3>Tier-Positionen</h3>
              <ul>
                {displayConcept.animal_positions.map((p) => (
                  <li key={p.animal}>
                    <strong>{p.animal}</strong>: {p.money_angle || p.stance}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      ) : null}

      {error ? <div className="textError">{error}</div> : null}
      <Link href={`/inszenierung${corpusId ? `?id=${corpusId}` : ""}`}>← Korpus</Link>
    </main>
  );
}

export default function AnalysePage() {
  return (
    <Suspense fallback={<main className="container"><p className="textFaint">Lade …</p></main>}>
      <AnalyseContent />
    </Suspense>
  );
}
