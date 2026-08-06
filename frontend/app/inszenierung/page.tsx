"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { Teil2ScriptCueOverview } from "@/components/show/Teil2ScriptCueOverview";
import { RuntimeSettingsPanel } from "@/components/settings/RuntimeSettingsPanel";
import {
  createCorpus,
  fetchCorpus,
  fetchScript,
  patchCorpus,
  prepareCorpus,
  pollCorpusUntilReady
} from "@/lib/api/inszenierung";
import type { PerformanceSpeaker } from "@/lib/types/director";
import type { SceneCorpus, ScriptBeatPreview, Teil2ScriptResponse } from "@/lib/types/inszenierung";
import { sessionGet, sessionSet, sessionRemove } from "@/lib/browser/session";

export default function InszenierungPage() {
  const [corpus, setCorpus] = useState<SceneCorpus | null>(null);
  const [script, setScript] = useState<Teil2ScriptResponse | null>(null);
  const [title, setTitle] = useState("AVATAR Text Delfin bis Wolf");
  const [scriptText, setScriptText] = useState("");
  const [performanceSpeaker, setPerformanceSpeaker] = useState<PerformanceSpeaker>("narrator");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadTemplate() {
      let lastError: unknown;
      for (let attempt = 0; attempt < 8; attempt++) {
        try {
          const data = await fetchScript();
          if (!cancelled) {
            setScript(data);
            setError("");
          }
          return;
        } catch (err) {
          lastError = err;
          await new Promise((r) => setTimeout(r, 750 * (attempt + 1)));
        }
      }
      if (!cancelled && lastError) {
        setError("Vorlage konnte nicht geladen werden");
      }
    }
    void loadTemplate();
    const id = sessionGet("currentCorpusId");
    if (id) {
      void fetchCorpus(id)
        .then((data) => {
          setCorpus(data);
          setScriptText(data.script_text ?? "");
          if (data.teil2_plan?.performance_speaker) {
            setPerformanceSpeaker(data.teil2_plan.performance_speaker);
          }
          if (data.status === "preparing") {
            setPreparing(true);
            void pollCorpusUntilReady(id, { onUpdate: setCorpus })
              .then(setCorpus)
              .catch((err) => setError(err instanceof Error ? err.message : "Vorbereiten fehlgeschlagen"))
              .finally(() => setPreparing(false));
          }
        })
        .catch(() => sessionRemove("currentCorpusId"));
    }
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCreate() {
    setError("");
    setLoading(true);
    try {
      const created = await createCorpus(title);
      setCorpus(created);
      sessionSet("currentCorpusId", created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveText() {
    if (!corpus) return;
    setSaving(true);
    setError("");
    try {
      const updated = await patchCorpus(corpus.id, { script_text: scriptText });
      setCorpus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  async function handleLoadTemplate() {
    if (!script?.text) return;
    setScriptText(script.text);
    if (corpus) {
      setSaving(true);
      try {
        const updated = await patchCorpus(corpus.id, { script_text: script.text });
        setCorpus(updated);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Vorlage konnte nicht geladen werden");
      } finally {
        setSaving(false);
      }
    }
  }

  async function handleFileUpload(file: File) {
    const text = await file.text();
    setScriptText(text);
    if (corpus) {
      await patchCorpus(corpus.id, { script_text: text })
        .then(setCorpus)
        .catch((err) => setError(err instanceof Error ? err.message : "Upload fehlgeschlagen"));
    }
  }

  async function handlePrepare() {
    if (!corpus) return;
    setPreparing(true);
    setError("");
    try {
      if (scriptText.trim() && scriptText !== (corpus.script_text ?? "")) {
        const saved = await patchCorpus(corpus.id, { script_text: scriptText });
        setCorpus(saved);
      }
      const updated = await prepareCorpus(corpus.id, {
        performance_speaker: performanceSpeaker,
        onUpdate: setCorpus
      });
      setCorpus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Vorbereiten fehlgeschlagen");
    } finally {
      setPreparing(false);
    }
  }

  const hasText = Boolean(corpus?.script_text?.trim() || scriptText.trim());
  const canPrepare = hasText && !preparing && corpus?.status !== "preparing";
  const canShow = Boolean(corpus?.teil2_plan?.sentences?.length);
  const preparePhaseLabel = corpus?.prepare_phase
    ? ` (${corpus.prepare_phase})`
    : "";

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Teil 2 — Inszenierung</h1>
      </div>
      <p className="textMuted">
        Aufführungstext hochladen, einmal vorbereiten (Analyse + OSC-Regie + Avatar-Anker), dann mit gewählter Stimme
        abspielen.
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
            <p className="textMuted">Status: {corpus.status}{preparePhaseLabel}</p>
            {corpus.prepare_error ? (
              <p className="textError" role="alert">
                {corpus.prepare_error}
              </p>
            ) : null}
            <label htmlFor="performance-text">Aufführungstext</label>
            <textarea
              id="performance-text"
              rows={12}
              value={scriptText}
              onChange={(e) => setScriptText(e.target.value)}
              placeholder="Gesamten Aufführungstext hier einfügen oder hochladen …"
            />
            <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
              <button type="button" onClick={() => void handleSaveText()} disabled={saving || !scriptText.trim()}>
                {saving ? "Speichern …" : "Text speichern"}
              </button>
              <label className="machineStartBtn" style={{ cursor: "pointer" }}>
                .txt hochladen
                <input
                  type="file"
                  accept=".txt,text/plain"
                  hidden
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void handleFileUpload(file);
                  }}
                />
              </label>
              {script ? (
                <button type="button" onClick={() => void handleLoadTemplate()}>
                  Kanon-Vorlage
                </button>
              ) : null}
            </div>
            <label htmlFor="performance-speaker">Aufführungsstimme</label>
            <select
              id="performance-speaker"
              value={performanceSpeaker}
              onChange={(e) => setPerformanceSpeaker(e.target.value as PerformanceSpeaker)}
            >
              <option value="narrator">Erzähler</option>
              <option value="AI_A">Stimme A</option>
              <option value="AI_B">Stimme B</option>
            </select>
            <RuntimeSettingsPanel compact />
            <button type="button" className="machineStartBtn" disabled={!canPrepare} onClick={() => void handlePrepare()}>
              {preparing || corpus.status === "preparing"
                ? `Vorbereiten …${preparePhaseLabel}`
                : "Vorbereiten"}
            </button>
            {corpus.teil2_plan?.alignment_warnings?.length ? (
              <div className="textError" role="alert">
                {corpus.teil2_plan.alignment_warnings.map((warning) => (
                  <p key={warning} style={{ margin: "0.25rem 0" }}>
                    {warning}
                  </p>
                ))}
              </div>
            ) : null}
            {canShow ? (
              <Link className="machineStartBtn" href={`/inszenierung/auffuehrung?id=${corpus.id}`}>
                Aufführung →
              </Link>
            ) : null}
          </section>

          {corpus.teil2_plan?.cue_overview ? (
            <section className="card col">
              <h2>Stücktext mit Cues</h2>
              <p className="textMuted">
                {corpus.teil2_plan.sentences.length} Sätze · {corpus.teil2_plan.avatar_segments.length}{" "}
                Avatar-Segmente · {corpus.teil2_plan.atmosphere_cue_points?.length ?? 0} Atmosphären-Cues
              </p>
              <Teil2ScriptCueOverview overview={corpus.teil2_plan.cue_overview} />
            </section>
          ) : corpus.teil2_plan ? (
            <section className="card col">
              <h2>Plan</h2>
              <p className="textMuted">
                {corpus.teil2_plan.sentences.length} Sätze · {corpus.teil2_plan.avatar_segments.length} Avatar-Segmente
              </p>
            </section>
          ) : null}
        </>
      )}

      {script ? (
        <section className="card col">
          <h2>CSV-Vorschau ({script.beats_preview.length} Beats)</h2>
          <BeatList beats={script.beats_preview} />
        </section>
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
