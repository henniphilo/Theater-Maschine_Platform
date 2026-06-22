"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { AppNav } from "@/components/layout/AppNav";
import {
  addScene,
  addScenesBatch,
  createCorpus,
  deleteScene,
  fetchCorpus
} from "@/lib/api/inszenierung";
import type { AnimalScene, SceneCorpus } from "@/lib/types/inszenierung";

export default function InszenierungPage() {
  const [corpus, setCorpus] = useState<SceneCorpus | null>(null);
  const [title, setTitle] = useState("Unter Tieren — Geld");
  const [animal, setAnimal] = useState("");
  const [sceneTitle, setSceneTitle] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [batchJson, setBatchJson] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
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

  async function handleAddScene() {
    if (!corpus || !animal.trim() || !sourceText.trim()) return;
    setError("");
    try {
      const updated = await addScene(corpus.id, {
        animal: animal.trim(),
        title: sceneTitle.trim(),
        source_text: sourceText.trim()
      });
      setCorpus(updated);
      setAnimal("");
      setSceneTitle("");
      setSourceText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    }
  }

  async function handleBatch() {
    if (!corpus || !batchJson.trim()) return;
    setError("");
    try {
      const scenes = JSON.parse(batchJson) as {
        animal: string;
        title?: string;
        source_text: string;
      }[];
      const updated = await addScenesBatch(corpus.id, scenes);
      setCorpus(updated);
      setBatchJson("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Batch-JSON ungültig");
    }
  }

  async function handleDelete(scene: AnimalScene) {
    if (!corpus) return;
    const updated = await deleteScene(corpus.id, scene.id);
    setCorpus(updated);
  }

  const canAnalyse = corpus && corpus.scenes.length > 0;
  const canKomposition = corpus?.gesamtkonzept?.thesis;
  const canShow = corpus?.composition?.moments?.length;

  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Teil 2 — Inszenierung</h1>
        <AppNav />
      </div>
      <p className="textMuted">
        Jelinek «Unter Tieren»: mehrere Tier-Szenen über Geld importieren, KI-Analyse, Komposition, anarchische
        Aufführung.
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
        <>
          <section className="card col">
            <h2>{corpus.title}</h2>
            <p className="textMuted">
              Status: {corpus.status} · {corpus.scenes.length} Szenen
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

          <section className="card col">
            <h2>Szene hinzufügen</h2>
            <label htmlFor="animal">Tier</label>
            <input id="animal" value={animal} onChange={(e) => setAnimal(e.target.value)} placeholder="z. B. Bär" />
            <label htmlFor="scene-title">Szentitel</label>
            <input
              id="scene-title"
              value={sceneTitle}
              onChange={(e) => setSceneTitle(e.target.value)}
              placeholder="z. B. Szene 20: Der Bärenklau"
            />
            <label htmlFor="scene-text">Text</label>
            <textarea
              id="scene-text"
              rows={8}
              value={sourceText}
              onChange={(e) => setSourceText(e.target.value)}
              placeholder="Auszug aus Unter Tieren — Tier spricht über Geld …"
            />
            <button type="button" onClick={() => void handleAddScene()} disabled={!animal.trim() || !sourceText.trim()}>
              Szene speichern
            </button>
          </section>

          <section className="card col">
            <h2>Batch-Import (JSON)</h2>
            <textarea
              rows={6}
              value={batchJson}
              onChange={(e) => setBatchJson(e.target.value)}
              placeholder={'[{"animal":"Bär","title":"Szene 1","source_text":"…"}]'}
            />
            <button type="button" onClick={() => void handleBatch()} disabled={!batchJson.trim()}>
              Batch importieren
            </button>
          </section>

          <section className="card col">
            <h2>Szenen</h2>
            {corpus.scenes.length === 0 ? (
              <p className="textFaint">Noch keine Szenen.</p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {corpus.scenes.map((scene) => (
                  <li key={scene.id} className="card" style={{ marginBottom: "0.5rem", padding: "0.75rem" }}>
                    <strong>{scene.animal}</strong>
                    {scene.title ? ` — ${scene.title}` : ""}
                    <span className="textMuted" style={{ marginLeft: "0.5rem" }}>
                      ({scene.source_text.length} Zeichen)
                    </span>
                    <button
                      type="button"
                      style={{ marginLeft: "0.75rem" }}
                      onClick={() => void handleDelete(scene)}
                    >
                      Entfernen
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}

      {error ? (
        <div className="textError" role="alert">
          {error}
        </div>
      ) : null}
    </main>
  );
}
