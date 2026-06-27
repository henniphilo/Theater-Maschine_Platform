"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { AppNav } from "@/components/layout/AppNav";
import { fetchTTSStatus, setPlaybackPaused } from "@/lib/api/client";
import { fetchCorpus } from "@/lib/api/inszenierung";
import {
  INITIAL_ANARCHY_STATE,
  runAnarchyPlayback,
  stopAnarchyPlayback,
  type AnarchyPlaybackState
} from "@/features/inszenierung/anarchyPlayback";
import { planRequiresTts } from "@/features/inszenierung/avatarCuePlayback";
import type { InszenierungBufferState } from "@/features/inszenierung/inszenierungBuffer";
import {
  bufferStatusLabel,
  isInszenierungBuffered,
  momentSpeechLabel,
  startInszenierungBuffer,
  subscribeInszenierungBuffer
} from "@/features/inszenierung/inszenierungBuffer";
import type { SceneCorpus } from "@/lib/types/inszenierung";

function AuffuehrungContent() {
  const searchParams = useSearchParams();
  const corpusId = searchParams.get("id") ?? sessionStorage.getItem("currentCorpusId") ?? "";
  const [corpus, setCorpus] = useState<SceneCorpus | null>(null);
  const [playback, setPlayback] = useState<AnarchyPlaybackState>(INITIAL_ANARCHY_STATE);
  const [ttsAvailable, setTtsAvailable] = useState(false);
  const [bufferState, setBufferState] = useState<InszenierungBufferState | null>(null);
  const abortRef = useRef(false);
  const genRef = useRef(0);

  useEffect(() => {
    return subscribeInszenierungBuffer(setBufferState);
  }, []);

  useEffect(() => {
    if (!corpusId) return;
    void fetchCorpus(corpusId).then(setCorpus);
    fetchTTSStatus()
      .then((s) => setTtsAvailable(s.available))
      .catch(() => undefined);
  }, [corpusId]);

  const hasPlan = (corpus?.composition?.moments?.length ?? 0) > 0;
  const needsTts = corpus?.composition ? planRequiresTts(corpus.composition) : false;
  const bufferReady = corpus ? isInszenierungBuffered(corpus.id, ttsAvailable) : false;
  const canPlay = hasPlan && (!needsTts || bufferReady || !ttsAvailable);

  useEffect(() => {
    if (!corpus || !hasPlan || bufferReady || !needsTts) return;
    if (ttsAvailable) startInszenierungBuffer(corpus, ttsAvailable);
  }, [corpus, hasPlan, bufferReady, ttsAvailable, needsTts]);

  const play = useCallback(async () => {
    if (!corpus?.composition || !canPlay) return;
    const gen = ++genRef.current;
    abortRef.current = false;
    setPlaybackPaused(false);
    setPlayback({ ...INITIAL_ANARCHY_STATE, running: true, paused: false });

    await runAnarchyPlayback(
      corpus,
      corpus.composition,
      ttsAvailable,
      (patch) => {
        if (gen === genRef.current) setPlayback((prev) => ({ ...prev, ...patch }));
      },
      () => abortRef.current
    );
  }, [corpus, canPlay, ttsAvailable]);

  function pause() {
    setPlaybackPaused(true);
    setPlayback((prev) => ({ ...prev, paused: true }));
  }

  function resume() {
    setPlaybackPaused(false);
    setPlayback((prev) => ({ ...prev, paused: false }));
  }

  function stop() {
    abortRef.current = true;
    genRef.current += 1;
    stopAnarchyPlayback();
    setPlayback({ ...INITIAL_ANARCHY_STATE, paused: true });
  }

  const sortedMoments = [...(corpus?.composition?.moments ?? [])].sort((a, b) => a.order - b.order);
  const currentMoment =
    playback.momentIndex >= 0 ? sortedMoments[playback.momentIndex] : undefined;

  return (
    <main className={`container col${corpus ? " pageWithPerformanceTransport" : ""}`}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Teil 2 — Aufführung</h1>
        <AppNav />
      </div>

      {corpus ? (
        <section className="card col">
          <h2>{corpus.title}</h2>
          {!hasPlan ? (
            <p className="textFaint">Zuerst Timeline in der Komposition laden.</p>
          ) : needsTts && !bufferReady && ttsAvailable ? (
            <p className="textMuted">{bufferState ? bufferStatusLabel(bufferState) : "Stimmen werden vorbereitet …"}</p>
          ) : (
            <p className="textMuted">
              {corpus.composition?.moments.length} Beats · Avatar-Video
              {needsTts ? ` · max. ${corpus.composition?.max_concurrent_voices} KI-Stimmen` : ""}
            </p>
          )}
          {currentMoment ? (
            <p className="textMuted">
              Aktiv: {momentSpeechLabel(currentMoment)}
              {currentMoment.avatar_layers?.length
                ? ` · Beamer: ${currentMoment.projector_mode === "all" ? "alle" : currentMoment.avatar_layers.map((l) => l.projector).join(", ")}`
                : ""}
            </p>
          ) : null}
        </section>
      ) : null}

      <footer className="performanceTransport" aria-label="Anarchie-Steuerung">
        <div className="performanceTransportInner">
          <div className="performanceTransportMeta">
            <strong>
              Beat {playback.momentIndex >= 0 ? playback.momentIndex + 1 : "—"} /{" "}
              {corpus?.composition?.moments.length ?? 0}
            </strong>
            <span className="textMuted performanceTransportDetail">
              {playback.completed
                ? "Beendet"
                : playback.running
                  ? playback.paused
                    ? "Pausiert"
                    : `${currentMoment ? momentSpeechLabel(currentMoment) : "Läuft"} · Anarchie ${(playback.anarchyLevel * 100).toFixed(0)}%`
                  : needsTts && !bufferReady && ttsAvailable
                    ? bufferState
                      ? bufferStatusLabel(bufferState)
                      : "Lädt …"
                    : "Bereit"}
              {playback.activeVoices > 0 ? ` · ${playback.activeVoices} Stimmen` : ""}
            </span>
          </div>
          <div className="performanceTransportControls">
            {!playback.running || playback.paused ? (
              <button type="button" className="machineStartBtn" disabled={!canPlay} onClick={() => void play()}>
                {playback.paused ? "▶ Fortsetzen" : "▶ Play"}
              </button>
            ) : (
              <button type="button" onClick={pause}>
                ⏸ Pause
              </button>
            )}
            {playback.paused ? (
              <button type="button" onClick={resume}>
                Fortsetzen
              </button>
            ) : null}
            <button type="button" className="machineStopBtn" onClick={stop} disabled={!playback.running && !playback.paused}>
              ⏹ Stop
            </button>
          </div>
        </div>
      </footer>

      <Link href={`/inszenierung/komposition?id=${corpusId}`}>← Komposition</Link>
    </main>
  );
}

export default function InszenierungAuffuehrungPage() {
  return (
    <Suspense fallback={<main className="container"><p className="textFaint">Lade …</p></main>}>
      <AuffuehrungContent />
    </Suspense>
  );
}
