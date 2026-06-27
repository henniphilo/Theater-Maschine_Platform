"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { AppNav } from "@/components/layout/AppNav";
import { createCorpus, fetchCorpus, fetchScript } from "@/lib/api/inszenierung";
import type { SceneCorpus, ScriptBeatPreview, Teil2ScriptResponse } from "@/lib/types/inszenierung";

export default function InszenierungPage() {
  const [corpus, setCorpus] = useState<SceneCorpus | null>(null);
  const [script, setScript] = useState<Teil2ScriptResponse | null>(null);
  const [title, setTitle] = useState("AVATAR Text Delfin bis Wolf");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void fetchScript().then(setScript).catch(() => setError("Skript konnte nicht geladen werden"));
    const id = sessionStorage.getItem("currentCorpusId");
    if (id) {
      void fetchCorpus(id).then(setCorpus).catch(() => sessionStorage.removeItem("currentCorpusId"));
    }
  }, []);

  async function handleCreate() {
    setError("");
    setLoading(true);
    try {
      const created = await createCorpus(title);
      setCorpus(created);
      sessionStorage.setItem("currentCorpusId", created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    } finally {
      setLoading(false);
    }
  }

  const canAnalyse = Boolean(corpus?.script_text);
  const canKomposition = corpus?.gesamtkonzept?.thesis;
  const canShow = corpus?.composition?.moments?.length;

  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Teil 2 — Inszenierung</h1>
        <AppNav />
      </div>
      <p className="textMuted">
        Fester Skriptablauf «AVATAR Text Delfin bis Wolf»: Avatar-CSV steuert Sprechtexte und Beamer, parallel
        eskalieren Sound, Video und Licht.
      </p>

      {!corpus ? (
        <section className="card col">
          <h2>Korpus anlegen</h2>
          <label htmlFor="corpus-title">Titel</label>
          <input id="corpus-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <button type="button" onClick={() => void handleCreate()} disabled={loading}>
            {loading ? "…" : "Korpus erstellen"}
          </button>
        </section>
      ) : (
        <section className="card col">
          <h2>{corpus.title}</h2>
          <p className="textMuted">
            Status: {corpus.status}
            {script ? ` · ${script.beat_count} Beats` : ""}
          </p>
          <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
            {canAnalyse ? (
              <Link className="machineStartBtn" href={`/inszenierung/analyse?id=${corpus.id}`}>
                Analyse →
              </Link>
            ) : null}
            {canKomposition ? (
              <Link className="machineStartBtn" href={`/inszenierung/komposition?id=${corpus.id}`}>
                Komposition →
              </Link>
            ) : null}
            {canShow ? (
              <Link className="machineStartBtn" href={`/inszenierung/auffuehrung?id=${corpus.id}`}>
                Aufführung →
              </Link>
            ) : null}
          </div>
        </section>
      )}

      {script ? (
        <>
          <section className="card col">
            <h2>Skriptablauf</h2>
            <p className="textMuted">
              Quelle: Textzuordnung Del-Wolf · Timeline aus Avatar Textzuordnung.csv · OSC 2026-06-27
            </p>
            {script.validation_warnings.length > 0 ? (
              <p className="textError" role="alert">
                {script.validation_warnings.length} Abweichung(en) zwischen CSV und Skripttext
              </p>
            ) : null}
          </section>

          <section className="card col">
            <h2>Beat-Vorschau ({script.beats_preview.length})</h2>
            <BeatList beats={script.beats_preview} />
          </section>
        </>
      ) : null}

      {error ? (
        <div className="textError" role="alert">
          {error}
        </div>
      ) : null}
    </main>
  );
}

function BeatList({ beats }: { beats: ScriptBeatPreview[] }) {
  if (beats.length === 0) return <p className="textFaint">Keine Beats.</p>;
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {beats.map((beat) => (
        <li key={beat.order} className="card" style={{ marginBottom: "0.5rem", padding: "0.75rem" }}>
          <strong>
            #{beat.order + 1}
            {beat.is_chorus ? " · Chorus" : ""}
          </strong>
          <span className="textMuted" style={{ marginLeft: "0.5rem" }}>
            {beat.avatars.join(", ")} ({beat.avatar_ids.join(", ")})
          </span>
          <p style={{ margin: "0.35rem 0 0", fontStyle: "italic" }}>
            {beat.text.length > 160 ? `${beat.text.slice(0, 160)}…` : beat.text}
          </p>
        </li>
      ))}
    </ul>
  );
}
