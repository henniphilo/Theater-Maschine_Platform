"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { AppNav } from "@/components/layout/AppNav";
import { RegieCard } from "@/components/show/RegieCard";
import { loadDramaturgySession } from "@/features/dramaturgy/session";
import {
  hydrateWorkshopRunner,
  isWorkshopRunning,
  startPart1Workshop,
  subscribeWorkshopRunner,
  type WorkshopRunnerState
} from "@/features/dramaturgy/workshopRunner";
import { workshopPhaseLabel } from "@/lib/types/part1";
import {
  bufferStatusLabel,
  isPlaybackBuffered,
  subscribeScriptBuffer,
  type ScriptBufferState
} from "@/features/show/performanceBuffer";
import { fetchTTSStatus } from "@/lib/api/client";
import { fetchScript } from "@/lib/api/script";
import { PROVIDERS } from "@/features/settings/provider-settings";

const OPENAI_MODELS = PROVIDERS.find((p) => p.value === "openai")?.models ?? ["gpt-4o"];
const ANTHROPIC_MODELS = PROVIDERS.find((p) => p.value === "anthropic")?.models ?? ["claude-sonnet-4-6"];

export default function DramaturgiePage() {
  const [runner, setRunner] = useState<WorkshopRunnerState | null>(null);
  const [bufferState, setBufferState] = useState<ScriptBufferState | null>(null);
  const [ttsHint, setTtsHint] = useState("");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const saved = loadDramaturgySession();
    if (saved) {
      hydrateWorkshopRunner({
        title: saved.title,
        sourceText: saved.sourceText,
        chat: saved.chat,
        openaiModel: saved.openaiModel,
        anthropicModel: saved.anthropicModel
      });
      if (saved.scriptId && !isWorkshopRunning()) {
        void fetchScript(saved.scriptId).then((script) => hydrateWorkshopRunner({ script }));
      }
    }
    setHydrated(true);
    fetchTTSStatus()
      .then((s) => {
        setTtsHint(s.hint);
        hydrateWorkshopRunner({ ttsAvailable: s.available });
      })
      .catch(() => undefined);
    const unsubWorkshop = subscribeWorkshopRunner(setRunner);
    const unsubBuffer = subscribeScriptBuffer(setBufferState);
    return () => {
      unsubWorkshop();
      unsubBuffer();
    };
  }, []);

  const loading = runner?.status === "running";
  const script = runner?.script ?? null;
  const error = runner?.error ?? "";

  async function startWorkshop() {
    if (!runner?.sourceText.trim() || loading) return;
    await startPart1Workshop({
      title: runner.title,
      sourceText: runner.sourceText,
      openaiModel: runner.openaiModel,
      anthropicModel: runner.anthropicModel,
      ttsAvailable: runner.ttsAvailable
    });
  }

  function updateRunner(patch: Partial<WorkshopRunnerState>) {
    hydrateWorkshopRunner(patch);
  }

  if (!hydrated || !runner) {
    return (
      <main className="container">
        <p className="textFaint">Lade …</p>
      </main>
    );
  }

  const canOpenScript = script && script.beats.length > 0;
  const bufferReady = script
    ? isPlaybackBuffered(script.id, {
        ttsAvailable: runner.ttsAvailable,
        scriptId: script.id,
        hasRenderedAudio: Boolean(script.has_rendered_audio)
      })
    : false;
  const showBufferStatus =
    script?.status === "ready" &&
    !script.has_rendered_audio &&
    runner.ttsAvailable &&
    bufferState?.scriptId === script.id &&
    bufferState.status !== "idle";

  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Dramaturgie — Teil 1</h1>
        <AppNav />
      </div>
      <p className="textMuted">
        Claude und ChatGPT besprechen Thema, Zitate und Medienwahl. Du kannst während des Workshops zu anderen Seiten
        wechseln — die Analyse und Stimmen-Vorbereitung laufen im Hintergrund weiter.
      </p>
      {runner.workshopPhase ? (
        <p className="textMuted" style={{ fontSize: "0.9rem" }}>
          Phase: <strong>{workshopPhaseLabel(runner.workshopPhase)}</strong>
          {runner.previewStatus ? ` · ${runner.previewStatus}` : ""}
        </p>
      ) : null}

      <section className="card col">
        <label htmlFor="title">Titel</label>
        <input
          id="title"
          value={runner.title}
          onChange={(e) => updateRunner({ title: e.target.value })}
          disabled={loading}
        />

        <label htmlFor="source">Stücktext</label>
        <textarea
          id="source"
          rows={10}
          value={runner.sourceText}
          onChange={(e) => updateRunner({ sourceText: e.target.value })}
          placeholder={"Gesamttext eingeben (ca. 1–2 Seiten, wird als Ganzes analysiert).\n\nVielleicht ist Erinnerung nur eine technische Störung."}
          disabled={loading}
        />

        <div className="row">
          <div className="col" style={{ flex: 1 }}>
            <label htmlFor="openai-model">GPT-Modell</label>
            <select
              id="openai-model"
              value={runner.openaiModel}
              onChange={(e) => updateRunner({ openaiModel: e.target.value })}
              disabled={loading}
            >
              {OPENAI_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div className="col" style={{ flex: 1 }}>
            <label htmlFor="anthropic-model">Claude-Modell</label>
            <select
              id="anthropic-model"
              value={runner.anthropicModel}
              onChange={(e) => updateRunner({ anthropicModel: e.target.value })}
              disabled={loading}
            >
              {ANTHROPIC_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button type="button" onClick={() => void startWorkshop()} disabled={loading || !runner.sourceText.trim()}>
          {loading ? "Teil-1-Workshop läuft …" : "Teil 1 Workshop starten"}
        </button>

        {canOpenScript ? (
          <Link
            className="machineStartBtn"
            href={`/stueck?id=${script!.id}`}
            style={{ display: "inline-block", textAlign: "center", textDecoration: "none" }}
          >
            Stücktext ansehen →
          </Link>
        ) : null}

        {showBufferStatus && bufferState ? (
          <p className={bufferState.status === "error" ? "textError" : "textMuted"} style={{ fontSize: "0.9rem" }}>
            {bufferStatusLabel(bufferState)}
            {bufferReady ? (
              <>
                {" · "}
                <Link href={`/auffuehrung?id=${script!.id}`}>Zur Aufführung →</Link>
              </>
            ) : null}
          </p>
        ) : null}

        {ttsHint ? (
          <p className="textMuted" style={{ fontSize: "0.9rem" }}>
            {ttsHint}
          </p>
        ) : null}
        {error ? (
          <div className="textError" role="alert">
            {error}
          </div>
        ) : null}
      </section>

      {runner.finalSelection ? (
        <section className="card col">
          <h2>Finale Auswahl</h2>
          <p className="textMuted" style={{ fontSize: "0.9rem" }}>
            {runner.finalSelection.final_sounds.length} Sounds · {runner.finalSelection.final_music.length} Musik ·{" "}
            {runner.finalSelection.final_videos.length} Videos · {runner.finalSelection.final_lights.length} Licht
          </p>
        </section>
      ) : null}

      <section className="card col">
        <h2>Claude / ChatGPT</h2>
        {runner.chat.length === 0 && !runner.thinking ? (
          <p className="textFaint">Noch keine Diskussion — Stücktext eingeben und starten.</p>
        ) : (
          <div className="chatList">
            {runner.chat.map((line) => (
              <div key={line.id} className="bubble bubbleAi">
                <strong>{line.speaker}</strong>
                <div className="bubbleContent">{line.content}</div>
                {line.director ? <RegieCard director={line.director} showPhase="planned" /> : null}
              </div>
            ))}
            {runner.thinking ? <p className="textMuted">{runner.thinking}</p> : null}
          </div>
        )}
      </section>
    </main>
  );
}
