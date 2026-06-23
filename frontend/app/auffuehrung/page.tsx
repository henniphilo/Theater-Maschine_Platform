"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { AppNav } from "@/components/layout/AppNav";
import { PerformanceTransport, beatIndexFromProgress } from "@/components/show/PerformanceTransport";
import { ScriptBeatBlock } from "@/components/script/ScriptBeatBlock";
import { fetchTTSStatus, setPlaybackPaused, stopPlayback } from "@/lib/api/client";
import { downloadBlob, exportPerformance, importPerformance } from "@/lib/api/performance";
import { fetchScript } from "@/lib/api/script";
import {
  bufferStatusLabel,
  isPlaybackBuffered,
  startScriptBuffer,
  subscribeScriptBuffer,
  type ScriptBufferState
} from "@/features/show/performanceBuffer";
import { part1Beats } from "@/lib/show/baerenklauBeat";
import {
  INITIAL_PLAYBACK_STATE,
  runPart1ScriptPlayback,
  stopScriptPlayback,
  type PlaybackAudioOptions,
  type PlaybackState
} from "@/features/show/scriptPlayback";
import { resolvePerformancePart } from "@/lib/types/part1";
import { fetchCorpus } from "@/lib/api/inszenierung";
import { patchScript } from "@/lib/api/script";
import {
  INITIAL_ANARCHY_STATE,
  runAnarchyPlayback,
  stopAnarchyPlayback,
  type AnarchyPlaybackState
} from "@/features/inszenierung/anarchyPlayback";
import {
  bufferStatusLabel as inszenierungBufferLabel,
  isInszenierungBuffered,
  startInszenierungBuffer,
  subscribeInszenierungBuffer,
  type InszenierungBufferState
} from "@/features/inszenierung/inszenierungBuffer";
import type { SceneCorpus } from "@/lib/types/inszenierung";
import { progressFromBeat } from "@/lib/show/performanceTimeline";
import { fetchMediaCatalog } from "@/lib/api/media";
import { buildMediaLookup, type MediaLookup } from "@/lib/types/media";
import type { ProductionScript } from "@/lib/types/script";

function AuffuehrungContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const scriptId = searchParams.get("id") ?? sessionStorage.getItem("currentScriptId") ?? "";
  const corpusIdParam =
    searchParams.get("corpus") ?? searchParams.get("corpus_id") ?? sessionStorage.getItem("currentCorpusId") ?? "";
  const importInputRef = useRef<HTMLInputElement>(null);
  const [script, setScript] = useState<ProductionScript | null>(null);
  const [playback, setPlayback] = useState<PlaybackState>(INITIAL_PLAYBACK_STATE);
  const [media, setMedia] = useState<MediaLookup | undefined>();
  const [ttsAvailable, setTtsAvailable] = useState(false);
  const [ttsHint, setTtsHint] = useState("");
  const [ttsProvider, setTtsProvider] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [bufferState, setBufferState] = useState<ScriptBufferState | null>(null);
  const [corpus, setCorpus] = useState<SceneCorpus | null>(null);
  const [anarchyPlayback, setAnarchyPlayback] = useState<AnarchyPlaybackState>(INITIAL_ANARCHY_STATE);
  const [inszenierungBuffer, setInszenierungBuffer] = useState<InszenierungBufferState | null>(null);
  const abortRef = useRef(false);
  const playbackGenRef = useRef(0);

  const beatCount = script?.beats.length ?? 0;
  const performancePart = script
    ? resolvePerformancePart(script.performance_part, Boolean(script.part1_selection))
    : "part1_baerenklau";
  const part1OnlyBeats = script ? part1Beats(script.beats) : [];
  const activeBeatCount = performancePart === "part1_baerenklau" ? part1OnlyBeats.length : beatCount;

  const load = useCallback(async () => {
    if (!scriptId) {
      setLoading(false);
      return;
    }
    try {
      const data = await fetchScript(scriptId);
      setScript(data);
      sessionStorage.setItem("currentScriptId", data.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stück nicht gefunden");
    } finally {
      setLoading(false);
    }
  }, [scriptId]);

  useEffect(() => {
    void load();
    fetchTTSStatus()
      .then((s) => {
        setTtsAvailable(s.available);
        setTtsHint(s.hint ?? "");
        setTtsProvider(s.provider ?? "");
      })
      .catch(() => undefined);
    fetchMediaCatalog()
      .then((catalog) => setMedia(buildMediaLookup(catalog)))
      .catch(() => undefined);
    return subscribeScriptBuffer(setBufferState);
  }, [load]);

  useEffect(() => {
    const linkedId = script?.teil2_corpus_id ?? corpusIdParam;
    if (!linkedId) {
      setCorpus(null);
      return;
    }
    void fetchCorpus(linkedId).then(setCorpus).catch(() => setCorpus(null));
  }, [script?.teil2_corpus_id, corpusIdParam]);

  useEffect(() => subscribeInszenierungBuffer(setInszenierungBuffer), []);

  useEffect(() => {
    if (!corpus?.composition?.moments?.length || !ttsAvailable) return;
    if (isInszenierungBuffered(corpus.id, ttsAvailable)) return;
    startInszenierungBuffer(corpus, ttsAvailable);
  }, [corpus, ttsAvailable]);

  const ready = script?.status === "ready";
  const playbackAudio: PlaybackAudioOptions = useMemo(
    () => ({
      ttsAvailable,
      scriptId: script?.id,
      hasRenderedAudio: Boolean(script?.has_rendered_audio)
    }),
    [ttsAvailable, script?.id, script?.has_rendered_audio]
  );
  const bufferReady = script ? isPlaybackBuffered(script.id, playbackAudio) : false;
  const scriptReady = ready || Boolean(script?.has_rendered_audio);
  const canPlayTeil1 = scriptReady && bufferReady && !anarchyPlayback.running;
  const canPlayTeil2 =
    Boolean(corpus?.composition?.moments?.length) &&
    teil2Ready &&
    !playback.running;
  const teil2Ready =
    Boolean(corpus?.composition?.moments?.length) &&
    (isInszenierungBuffered(corpus!.id, ttsAvailable) || !ttsAvailable);
  const showBufferStatus =
    scriptReady &&
    !script?.has_rendered_audio &&
    ttsAvailable &&
    bufferState?.scriptId === script?.id &&
    bufferState.status !== "idle" &&
    !bufferReady;
  const playBlockedReason =
    scriptReady && !bufferReady && ttsAvailable && !script?.has_rendered_audio
      ? bufferState?.scriptId === script?.id && bufferState.status === "buffering"
        ? bufferStatusLabel(bufferState)
        : "Stimmen werden vorbereitet …"
      : undefined;

  useEffect(() => {
    if (!script || !scriptReady) return;
    if (bufferReady) return;
    startScriptBuffer(script, playbackAudio);
  }, [script, scriptReady, bufferReady, playbackAudio]);

  const playFrom = useCallback(
    async (startIndex: number) => {
      if (!script || !canPlayTeil1) return;
      if (performancePart === "part2_delphin_to_mole") return;
      const gen = ++playbackGenRef.current;
      setError("");
      abortRef.current = false;
      setPlaybackPaused(false);
      void patchScript(script.id, { performance_part: "part1_baerenklau" }).catch(() => undefined);
      const beats = part1OnlyBeats;
      setPlayback((prev) => ({
        ...prev,
        beatIndex: startIndex,
        paused: false,
        completed: false,
        running: true,
        timelineProgress: progressFromBeat(startIndex, beats.length, 0)
      }));

      if (gen !== playbackGenRef.current || abortRef.current) return;

      await runPart1ScriptPlayback(
        script.beats,
        playbackAudio,
        startIndex,
        (update) => {
          if (gen === playbackGenRef.current) {
            setPlayback((prev) => ({ ...prev, ...update }));
          }
        },
        () => abortRef.current,
        `${script.title} — Teil 1`
      );

      if (gen === playbackGenRef.current && !abortRef.current && script.teil2_corpus_id) {
        setPlayback((prev) => ({ ...prev, completed: true, running: false }));
      }
    },
    [script, canPlayTeil1, playbackAudio, performancePart, part1OnlyBeats]
  );

  const playTeil2 = useCallback(async () => {
    if (!corpus?.composition || !canPlayTeil2) return;
    const gen = ++playbackGenRef.current;
    abortRef.current = false;
    setPlaybackPaused(false);
    setAnarchyPlayback({ ...INITIAL_ANARCHY_STATE, running: true, paused: false });
    if (script?.id) {
      await patchScript(script.id, { performance_part: "part2_delphin_to_mole" }).catch(() => undefined);
    }
    await runAnarchyPlayback(
      corpus,
      corpus.composition,
      ttsAvailable,
      (patch) => {
        if (gen === playbackGenRef.current) setAnarchyPlayback((prev) => ({ ...prev, ...patch }));
      },
      () => abortRef.current
    );
    if (gen === playbackGenRef.current) {
      setAnarchyPlayback((prev) => ({ ...prev, running: false, completed: true }));
    }
  }, [corpus, canPlayTeil2, ttsAvailable, script]);

  function handlePlayTeil1() {
    if (!script || !canPlayTeil1) return;
    if (playback.running && playback.paused) {
      setPlaybackPaused(false);
      setPlayback((prev) => ({ ...prev, paused: false }));
      return;
    }
    if (playback.running) return;
    const from =
      playback.paused && playback.beatIndex >= 0
        ? playback.beatIndex
        : playback.beatIndex >= 0
          ? playback.beatIndex
          : 0;
    void playFrom(from);
  }

  function handlePause() {
    if (!playback.running || playback.paused) return;
    setPlaybackPaused(true);
    setPlayback((prev) => ({ ...prev, paused: true }));
  }

  function handleStop() {
    abortRef.current = true;
    playbackGenRef.current += 1;
    stopScriptPlayback();
    stopAnarchyPlayback();
    setPlayback((prev) => ({
      ...prev,
      running: false,
      paused: true,
      activeOscBridge: null,
      activeOscCommand: null
    }));
    setAnarchyPlayback((prev) => ({ ...prev, running: false, paused: true }));
  }

  function handleSeek(progress: number) {
    if (!script || beatCount === 0) return;
    const index = beatIndexFromProgress(progress, beatCount);
    setPlayback((prev) => ({
      ...prev,
      beatIndex: index,
      timelineProgress: progressFromBeat(index, beatCount, 0),
      paused: prev.running ? prev.paused : true,
      completed: false
    }));

    if (playback.running) {
      abortRef.current = true;
      playbackGenRef.current += 1;
      stopScriptPlayback();
      setPlaybackPaused(false);
      void playFrom(index);
    }
  }

  function handleJumpToBeat(index: number) {
    handleSeek(progressFromBeat(index, beatCount, 0));
  }

  async function handleExport() {
    if (!script || !ready) return;
    setExporting(true);
    setError("");
    try {
      const { blob, filename } = await exportPerformance(script.id);
      downloadBlob(blob, filename);
      const updated = await fetchScript(script.id);
      setScript(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export fehlgeschlagen");
    } finally {
      setExporting(false);
    }
  }

  async function handleImportFile(file: File | null) {
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      const imported = (await importPerformance(file)) as ProductionScript;
      sessionStorage.setItem("currentScriptId", imported.id);
      router.push(`/auffuehrung?id=${imported.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import fehlgeschlagen");
    } finally {
      setImporting(false);
      if (importInputRef.current) importInputRef.current.value = "";
    }
  }

  return (
    <main className={`container col${script ? " pageWithPerformanceTransport" : ""}`}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Aufführung</h1>
        <AppNav />
      </div>
      <p className="textMuted">
        Teil 1 und Teil 2 laufen unabhängig: ▶ Teil 1 = Dramaturgen-Diskussion, dann Stücktext mit Cues. Teil 2 =
        anarchische Inszenierung (eigener Start).
      </p>

      <section className="card col">
        <h2>Aufführung laden / speichern</h2>
        <div className="row">
          <button type="button" onClick={() => importInputRef.current?.click()} disabled={importing}>
            {importing ? "Import läuft …" : "Aufführung importieren (.zip)"}
          </button>
          <input
            ref={importInputRef}
            type="file"
            accept=".zip,application/zip"
            hidden
            onChange={(e) => void handleImportFile(e.target.files?.[0] ?? null)}
          />
          {script && ready ? (
            <button type="button" onClick={() => void handleExport()} disabled={exporting || playback.running}>
              {exporting ? "Export rendert Stimmen …" : "Aufführung exportieren"}
            </button>
          ) : null}
        </div>
        {script?.has_rendered_audio ? (
          <p className="textMuted" style={{ fontSize: "0.85rem" }}>
            Vorgespeicherte Stimmen aktiv — Wiedergabe ohne Live-TTS.
          </p>
        ) : ttsAvailable ? (
          <p className="textMuted" style={{ fontSize: "0.85rem" }}>
            Live-TTS: {ttsProvider === "say" ? "Siri / macOS say" : ttsProvider}
            {ttsHint ? ` · ${ttsHint}` : ""}
          </p>
        ) : (
          <p className="textError" style={{ fontSize: "0.85rem" }}>
            Keine Stimmen verfügbar — Backend nativ starten (<code>./run-native.sh</code>) oder Aufführung mit
            exportierten Stimmen importieren.
          </p>
        )}
      </section>

      {loading ? <p className="textFaint">Lade Stück …</p> : null}
      {error ? (
        <div className="textError" role="alert">
          {error}
        </div>
      ) : null}
      {!scriptId && !loading ? (
        <p className="textFaint">
          Kein Stück geladen — oben importieren oder <Link href="/dramaturgie">Dramaturgie</Link> starten.
        </p>
      ) : null}

      {script ? (
        <>
          <section className="card col">
            <h2>{script.title}</h2>
            <p className="textMuted" style={{ fontSize: "0.9rem" }}>
              Aktueller Teil:{" "}
              <strong>{performancePart === "part1_baerenklau" ? "Teil 1 — Bärenklau" : "Teil 2 — Anarchie"}</strong>
            </p>
            {!scriptReady ? (
              <p className="textFaint">
                Stück noch nicht bereit — Dramaturgie abschließen oder gespeicherte Aufführung importieren.
              </p>
            ) : showBufferStatus && bufferState ? (
              <p className="textMuted">{bufferStatusLabel(bufferState)}</p>
            ) : bufferReady && !script?.has_rendered_audio ? (
              <p className="textMuted" style={{ fontSize: "0.9rem" }}>
                Stimmen bereit — Play startet ohne Wartezeit.
              </p>
            ) : null}
            <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap" }}>
              <button
                type="button"
                className="machineStartBtn"
                onClick={handlePlayTeil1}
                disabled={!canPlayTeil1 || playback.running}
              >
                {playback.running ? "Teil 1 läuft …" : "Teil 1 starten"}
              </button>
              {corpus?.composition?.moments?.length ? (
                <button
                  type="button"
                  onClick={() => void playTeil2()}
                  disabled={!canPlayTeil2 || anarchyPlayback.running}
                >
                  {anarchyPlayback.running ? "Teil 2 läuft …" : "Teil 2 starten"}
                </button>
              ) : (
                <p className="textMuted" style={{ fontSize: "0.85rem", margin: 0 }}>
                  Teil 2: Korpus in <Link href="/inszenierung">Inszenierung</Link> vorbereiten und verknüpfen, oder{" "}
                  <code>?corpus=…</code> in der URL.
                </p>
              )}
            </div>
            {playback.completed && performancePart === "part1_baerenklau" ? (
              <p className="textMuted">Teil 1 beendet.</p>
            ) : null}
            {anarchyPlayback.completed ? <p className="textMuted">Teil 2 beendet.</p> : null}
            {inszenierungBuffer && !teil2Ready && script.teil2_corpus_id ? (
              <p className="textMuted">{inszenierungBufferLabel(inszenierungBuffer)}</p>
            ) : null}
            {anarchyPlayback.running ? (
              <p className="textMuted" style={{ fontSize: "0.9rem" }}>
                Anarchie {Math.round(anarchyPlayback.anarchyLevel * 100)}% · Stimmen{" "}
                {anarchyPlayback.activeVoices}
              </p>
            ) : null}
            {playback.completed && !script.teil2_corpus_id && !corpusIdParam ? (
              <p className="textMuted">Teil 1 beendet — erneut starten über die Buttons oben.</p>
            ) : null}
          </section>

          <section className="card col scriptDocument">
            <h2>Stücktext</h2>
            <p className="textMuted" style={{ fontSize: "0.9rem" }}>
              Klick auf einen Abschnitt springt dorthin (Zeitspur).
            </p>
            {script.beats.map((beat, index) => (
              <ScriptBeatBlock
                key={beat.id}
                beat={beat}
                media={media}
                highlight={index === playback.beatIndex && (playback.running || playback.paused)}
                segmentPhase={index === playback.beatIndex ? playback.segmentPhase : undefined}
                discussionTurnIndex={
                  index === playback.beatIndex ? playback.discussionTurnIndex : undefined
                }
                sentenceIndex={index === playback.beatIndex ? playback.sentenceIndex : undefined}
                clickable={canPlayTeil1}
                onSelect={() => handleJumpToBeat(index)}
              />
            ))}
          </section>

          <PerformanceTransport
            beats={performancePart === "part1_baerenklau" ? part1OnlyBeats : script.beats}
            beatIndex={playback.beatIndex}
            beatCount={activeBeatCount}
            timelineProgress={
              playback.timelineProgress >= 0
                ? playback.timelineProgress
                : progressFromBeat(Math.max(playback.beatIndex, 0), beatCount, 0)
            }
            running={playback.running}
            paused={playback.paused}
            completed={playback.completed}
            canPlay={canPlayTeil1}
            playBlockedReason={playBlockedReason}
            segmentPhase={playback.segmentPhase}
            discussionTurnIndex={playback.discussionTurnIndex}
            sentenceIndex={playback.sentenceIndex}
            showPhase={playback.showPhase}
            activeOscBridge={playback.activeOscBridge}
            onPlay={handlePlayTeil1}
            onPause={handlePause}
            onStop={handleStop}
            onSeek={handleSeek}
          />
        </>
      ) : null}
    </main>
  );
}

export default function AuffuehrungPage() {
  return (
    <Suspense fallback={<main className="container"><p className="textFaint">Lade …</p></main>}>
      <AuffuehrungContent />
    </Suspense>
  );
}
