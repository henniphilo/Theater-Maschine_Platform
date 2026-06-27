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
  composeScript,
  createCorpus,
  exportTeil2,
  fetchCorpus,
  importTeil2
} from "@/lib/api/inszenierung";
import { patchScript } from "@/lib/api/script";
import {
  INITIAL_ANARCHY_STATE,
  runAnarchyPlayback,
  stopAnarchyPlayback,
  type AnarchyPlaybackState
} from "@/features/inszenierung/anarchyPlayback";
import {
  planNeedsAvatarVisualRefresh,
  planRequiresTts
} from "@/features/inszenierung/avatarCuePlayback";
import {
  bufferStatusLabel as inszenierungBufferLabel,
  isInszenierungBuffered,
  momentSpeechLabel,
  startInszenierungBuffer,
  subscribeInszenierungBuffer,
  type InszenierungBufferState
} from "@/features/inszenierung/inszenierungBuffer";
import type { CompositionMoment, SceneCorpus } from "@/lib/types/inszenierung";
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
  type PlaybackMode,
  type PlaybackState
} from "@/features/show/scriptPlayback";
import { resolvePerformancePart } from "@/lib/types/part1";
import { progressFromBeat } from "@/lib/show/performanceTimeline";
import { fetchMediaCatalog } from "@/lib/api/media";
import type { MediaCatalog } from "@/lib/types/media";
import { allowlistFromCatalog, buildMediaAliasIndex, type MediaAllowlist, type MediaAliasIndex } from "@/features/show/mediaMentions";
import { buildMediaLookup, type MediaLookup } from "@/lib/types/media";
import type { ProductionScript } from "@/lib/types/script";

function AuffuehrungContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const scriptId = searchParams.get("id") ?? sessionStorage.getItem("currentScriptId") ?? "";
  const corpusIdParam =
    searchParams.get("corpus") ?? searchParams.get("corpus_id") ?? sessionStorage.getItem("currentCorpusId") ?? "";
  const importTeil2InputRef = useRef<HTMLInputElement>(null);
  const importInputRef = useRef<HTMLInputElement>(null);
  const [script, setScript] = useState<ProductionScript | null>(null);
  const [playback, setPlayback] = useState<PlaybackState>(INITIAL_PLAYBACK_STATE);
  const [media, setMedia] = useState<MediaLookup | undefined>();
  const [mediaCatalog, setMediaCatalog] = useState<MediaCatalog | null>(null);
  const [mediaAllowlist, setMediaAllowlist] = useState<MediaAllowlist | null>(null);
  const [mediaAliasIndex, setMediaAliasIndex] = useState<MediaAliasIndex | null>(null);
  const [ttsAvailable, setTtsAvailable] = useState(false);
  const [ttsHint, setTtsHint] = useState("");
  const [ttsProvider, setTtsProvider] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [exportingTeil2, setExportingTeil2] = useState(false);
  const [importingTeil2, setImportingTeil2] = useState(false);
  const [preparingTeil2, setPreparingTeil2] = useState(false);
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
  const part1OnlyBeats = useMemo(
    () => (script ? part1Beats(script.beats) : []),
    [script]
  );
  const activeBeatCount = performancePart === "part1_baerenklau" ? part1OnlyBeats.length : beatCount;
  const teil2Moments = useMemo(
    () => [...(corpus?.composition?.moments ?? [])].sort((a, b) => a.order - b.order),
    [corpus?.composition?.moments]
  );
  const teil2NeedsTts = corpus?.composition ? planRequiresTts(corpus.composition) : false;
  const teil2BeatCount = teil2Moments.length;
  const teil2Only = Boolean(corpusIdParam && !scriptId);
  const activeTeil2Moment =
    anarchyPlayback.momentIndex >= 0 ? teil2Moments[anarchyPlayback.momentIndex] : undefined;

  const load = useCallback(async () => {
    if (!scriptId && !corpusIdParam) {
      setLoading(false);
      return;
    }
    if (!scriptId) {
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
    const videoScope = performancePart === "part2_delphin_to_mole" ? "part2" : "part1";
    fetchMediaCatalog(videoScope)
      .then((catalog) => {
        setMediaCatalog(catalog);
        setMedia(buildMediaLookup(catalog));
        setMediaAllowlist(allowlistFromCatalog(catalog));
        setMediaAliasIndex(buildMediaAliasIndex(catalog));
      })
      .catch(() => undefined);
    return subscribeScriptBuffer(setBufferState);
  }, [load, performancePart]);

  useEffect(() => {
    let cancelled = false;
    const linkedId = script?.teil2_corpus_id ?? corpusIdParam;
    if (!linkedId) {
      setCorpus(null);
      if (!scriptId) setLoading(false);
      return;
    }
    if (!scriptId) setLoading(true);
    void (async () => {
      try {
        let data = await fetchCorpus(linkedId);
        if (cancelled) return;
        if (data.script_text && !(data.composition?.moments?.length ?? 0)) {
          try {
            data = await composeScript(data.id);
          } catch (err) {
            if (!cancelled) {
              setError(err instanceof Error ? err.message : "Teil-2-Timeline konnte nicht geladen werden");
            }
          }
        }
        if (cancelled) return;
        setCorpus(data);
        sessionStorage.setItem("currentCorpusId", data.id);
        if (script?.id && script.teil2_corpus_id !== data.id) {
          await patchScript(script.id, { teil2_corpus_id: data.id }).catch(() => undefined);
        }
      } catch {
        if (!cancelled) setCorpus(null);
      } finally {
        if (!cancelled && !scriptId) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [script?.teil2_corpus_id, script?.id, corpusIdParam, scriptId]);

  useEffect(() => {
    if (!corpus?.composition?.moments?.length || !ttsAvailable || !teil2NeedsTts) return;
    if (isInszenierungBuffered(corpus.id, ttsAvailable)) return;
    startInszenierungBuffer(corpus, ttsAvailable);
  }, [corpus, ttsAvailable, teil2NeedsTts]);

  useEffect(() => subscribeInszenierungBuffer(setInszenierungBuffer), []);

  const ready = script?.status === "ready";
  const playbackAudio: PlaybackAudioOptions = useMemo(
    () => ({
      ttsAvailable,
      scriptId: script?.id,
      hasRenderedAudio: Boolean(script?.has_rendered_audio),
      mediaAllowlist,
      mediaAliasIndex,
      mediaCatalog
    }),
    [ttsAvailable, script?.id, script?.has_rendered_audio, mediaAllowlist, mediaAliasIndex, mediaCatalog]
  );
  const bufferReady = script ? isPlaybackBuffered(script.id, playbackAudio) : false;
  const scriptReady = ready || Boolean(script?.has_rendered_audio);
  const teil2Ready =
    Boolean(corpus?.composition?.moments?.length) &&
    (!teil2NeedsTts || isInszenierungBuffered(corpus!.id, ttsAvailable) || !ttsAvailable);
  const teil2BlockedReason =
    corpus?.composition?.moments?.length && teil2NeedsTts && ttsAvailable && !teil2Ready
      ? inszenierungBuffer && inszenierungBuffer.corpusId === corpus.id
        ? inszenierungBufferLabel(inszenierungBuffer)
        : "Stimmen werden vorbereitet …"
      : !corpus?.composition?.moments?.length && corpus
        ? "Timeline fehlt — Komposition laden oder vorbereiten."
        : undefined;
  const canPlayTeil1 = scriptReady && bufferReady && !anarchyPlayback.running;
  const canPlayTeil2 =
    Boolean(corpus?.composition?.moments?.length) &&
    teil2Ready &&
    !playback.running;
  const showBufferStatus =
    scriptReady &&
    !script?.has_rendered_audio &&
    ttsAvailable &&
    bufferState?.scriptId === script?.id &&
    bufferState?.status !== "idle" &&
    !bufferReady;
  const playBlockedReason =
    scriptReady && !bufferReady && ttsAvailable && !script?.has_rendered_audio
      ? bufferState?.scriptId === script?.id && bufferState?.status === "buffering" && bufferState
        ? bufferStatusLabel(bufferState)
        : "Stimmen werden vorbereitet …"
      : undefined;

  useEffect(() => {
    if (!script || !scriptReady) return;
    if (bufferReady) return;
    startScriptBuffer(script, playbackAudio);
  }, [script, scriptReady, bufferReady, playbackAudio]);

  const playFrom = useCallback(
    async (startIndex: number, mode: PlaybackMode = "full") => {
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
        playbackMode: mode,
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
        `${script.title} — Teil 1`,
        script.part1_selection ?? null,
        mode
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
    let activeCorpus = corpus;
    try {
      activeCorpus = await composeScript(corpus.id);
      if (gen === playbackGenRef.current) setCorpus(activeCorpus);
    } catch (err) {
      if (planNeedsAvatarVisualRefresh(corpus.composition)) {
        setError(err instanceof Error ? err.message : "Teil-2-Timeline konnte nicht geladen werden");
        setAnarchyPlayback((prev) => ({ ...prev, running: false }));
        return;
      }
    }
    if (!activeCorpus.composition) return;
    await runAnarchyPlayback(
      activeCorpus,
      activeCorpus.composition,
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

  function handlePlayTeil1(mode: PlaybackMode = "full") {
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
    void playFrom(from, mode);
  }

  function handlePlayTeil2() {
    if (anarchyPlayback.running && anarchyPlayback.paused) {
      setPlaybackPaused(false);
      setAnarchyPlayback((prev) => ({ ...prev, paused: false }));
      return;
    }
    if (anarchyPlayback.running) return;
    void playTeil2();
  }

  function handlePause() {
    if (anarchyPlayback.running && !anarchyPlayback.paused) {
      setPlaybackPaused(true);
      setAnarchyPlayback((prev) => ({ ...prev, paused: true }));
      return;
    }
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
      void playFrom(index, playback.playbackMode ?? "full");
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

  async function handleExportTeil2() {
    if (!corpus?.composition?.moments?.length) return;
    setExportingTeil2(true);
    setError("");
    try {
      const { blob, filename } = await exportTeil2(corpus.id);
      downloadBlob(blob, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Teil-2-Export fehlgeschlagen");
    } finally {
      setExportingTeil2(false);
    }
  }

  async function handleImportTeil2File(file: File | null) {
    if (!file) return;
    setImportingTeil2(true);
    setError("");
    try {
      const imported = await importTeil2(file);
      setCorpus(imported);
      sessionStorage.setItem("currentCorpusId", imported.id);
      const href = scriptId
        ? `/auffuehrung?id=${scriptId}&corpus=${imported.id}`
        : `/auffuehrung?corpus=${imported.id}`;
      router.push(href);
      if (script?.id) {
        await patchScript(script.id, { teil2_corpus_id: imported.id }).catch(() => undefined);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Teil-2-Import fehlgeschlagen");
    } finally {
      setImportingTeil2(false);
      if (importTeil2InputRef.current) importTeil2InputRef.current.value = "";
    }
  }

  async function handlePrepareTeil2() {
    setPreparingTeil2(true);
    setError("");
    try {
      let next = corpus;
      if (!next) {
        next = await createCorpus("Teil 2 — Delphin bis Wolf");
      }
      if (!(next.composition?.moments?.length ?? 0)) {
        next = await composeScript(next.id);
      }
      setCorpus(next);
      sessionStorage.setItem("currentCorpusId", next.id);
      const href = scriptId
        ? `/auffuehrung?id=${scriptId}&corpus=${next.id}`
        : `/auffuehrung?corpus=${next.id}`;
      router.push(href);
      if (script?.id) {
        await patchScript(script.id, { teil2_corpus_id: next.id }).catch(() => undefined);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Teil 2 konnte nicht vorbereitet werden");
    } finally {
      setPreparingTeil2(false);
    }
  }

  return (
    <main
      className={`container col${script || corpus ? " pageWithPerformanceTransport" : ""}`}
    >
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
        <p className="textMuted" style={{ fontSize: "0.85rem", marginTop: 0 }}>
          Teil 1: <code>.zip</code> mit Stück und Stimmen · Teil 2: <code>.tmteil2.zip</code> mit Korpus und
          Timeline
        </p>
        <div className="row" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
          <button type="button" onClick={() => importInputRef.current?.click()} disabled={importing}>
            {importing ? "Import läuft …" : "Teil 1 importieren (.zip)"}
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
              {exporting ? "Export rendert Stimmen …" : "Teil 1 exportieren"}
            </button>
          ) : null}
          <button type="button" onClick={() => importTeil2InputRef.current?.click()} disabled={importingTeil2}>
            {importingTeil2 ? "Import läuft …" : "Teil 2 importieren (.tmteil2.zip)"}
          </button>
          <input
            ref={importTeil2InputRef}
            type="file"
            accept=".tmteil2.zip,.zip,application/zip"
            hidden
            onChange={(e) => void handleImportTeil2File(e.target.files?.[0] ?? null)}
          />
          {corpus?.composition?.moments?.length ? (
            <button
              type="button"
              onClick={() => void handleExportTeil2()}
              disabled={exportingTeil2 || anarchyPlayback.running}
            >
              {exportingTeil2 ? "Export läuft …" : "Teil 2 exportieren"}
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

      {loading ? <p className="textFaint">Lade Aufführung …</p> : null}
      {error ? (
        <div className="textError" role="alert">
          {error}
        </div>
      ) : null}
      {!scriptId && !corpusIdParam && !loading ? (
        <p className="textFaint">
          Kein Stück oder Teil-2-Korpus geladen — oben importieren,{" "}
          <button type="button" onClick={() => void handlePrepareTeil2()} disabled={preparingTeil2}>
            {preparingTeil2 ? "Teil 2 wird vorbereitet …" : "Teil 2 vorbereiten"}
          </button>
          , oder <Link href="/dramaturgie">Dramaturgie</Link> starten.
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
                onClick={() => handlePlayTeil1("full")}
                disabled={!canPlayTeil1 || playback.running}
              >
                {playback.running && playback.playbackMode === "full"
                  ? "Komplett läuft …"
                  : "▶ Komplett"}
              </button>
              <button
                type="button"
                onClick={() => handlePlayTeil1("discussion")}
                disabled={!canPlayTeil1 || playback.running}
              >
                {playback.running && playback.playbackMode === "discussion"
                  ? "Dramaturgie läuft …"
                  : "▶ Nur Dramaturgie"}
              </button>
              <button
                type="button"
                onClick={() => handlePlayTeil1("performance")}
                disabled={!canPlayTeil1 || playback.running}
              >
                {playback.running && playback.playbackMode === "performance"
                  ? "Stücktext läuft …"
                  : "▶ Nur Stücktext"}
              </button>
              {corpus?.composition?.moments?.length ? (
                <button
                  type="button"
                  onClick={handlePlayTeil2}
                  disabled={!canPlayTeil2 || (anarchyPlayback.running && !anarchyPlayback.paused)}
                >
                  {anarchyPlayback.running
                    ? anarchyPlayback.paused
                      ? "Teil 2 pausiert"
                      : "Teil 2 läuft …"
                    : "Teil 2 starten"}
                </button>
              ) : (
                <button type="button" onClick={() => void handlePrepareTeil2()} disabled={preparingTeil2}>
                  {preparingTeil2 ? "Teil 2 wird vorbereitet …" : "Teil 2 vorbereiten"}
                </button>
              )}
            </div>
            {playback.completed && performancePart === "part1_baerenklau" ? (
              <p className="textMuted">Teil 1 beendet.</p>
            ) : null}
            {anarchyPlayback.completed ? <p className="textMuted">Teil 2 beendet.</p> : null}
            {inszenierungBuffer && teil2NeedsTts && !teil2Ready && corpus ? (
              <p className="textMuted">{inszenierungBufferLabel(inszenierungBuffer)}</p>
            ) : null}
            {teil2BlockedReason && !anarchyPlayback.running ? (
              <p className="textMuted" style={{ fontSize: "0.85rem" }}>
                {teil2BlockedReason}
              </p>
            ) : null}
            {anarchyPlayback.running ? (
              <p className="textMuted" style={{ fontSize: "0.9rem" }}>
                Beat {anarchyPlayback.momentIndex + 1}/{teil2BeatCount}
                {activeTeil2Moment ? ` · ${momentSpeechLabel(activeTeil2Moment)}` : ""}
                {activeTeil2Moment?.avatar_layers?.length
                  ? ` · Beamer: ${
                      activeTeil2Moment.projector_mode === "all"
                        ? "alle"
                        : activeTeil2Moment.avatar_layers.map((l) => l.projector).join(", ")
                    }`
                  : ""}
                {" · "}Anarchie {Math.round(anarchyPlayback.anarchyLevel * 100)}%
                {anarchyPlayback.activeVoices > 0 ? ` · ${anarchyPlayback.activeVoices} Stimmen` : ""}
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

          {!anarchyPlayback.running && !anarchyPlayback.paused ? (
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
              playbackMode={playback.playbackMode}
              onPlay={() => handlePlayTeil1(playback.playbackMode ?? "full")}
              onPause={handlePause}
              onStop={handleStop}
              onSeek={handleSeek}
            />
          ) : null}
        </>
      ) : null}

      {corpus && (teil2Only || !script) ? (
        <>
          <section className="card col">
            <h2>{corpus.title || "Teil 2 — Anarchie"}</h2>
            <p className="textMuted" style={{ fontSize: "0.9rem" }}>
              {teil2BeatCount > 0
                ? `${teil2BeatCount} Beats · Avatar-Video parallel zu Anarchie-OSC`
                : "Noch keine Timeline — Komposition laden oder vorbereiten."}
            </p>
            <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap" }}>
              {teil2BeatCount > 0 ? (
                <button
                  type="button"
                  className="machineStartBtn"
                  onClick={handlePlayTeil2}
                  disabled={!canPlayTeil2 || (anarchyPlayback.running && !anarchyPlayback.paused)}
                >
                  {anarchyPlayback.running
                    ? anarchyPlayback.paused
                      ? "▶ Fortsetzen"
                      : "Teil 2 läuft …"
                    : "▶ Teil 2 starten"}
                </button>
              ) : (
                <button type="button" onClick={() => void handlePrepareTeil2()} disabled={preparingTeil2}>
                  {preparingTeil2 ? "Wird vorbereitet …" : "Timeline laden"}
                </button>
              )}
              <Link href={`/inszenierung/komposition?id=${corpus.id}`}>Komposition bearbeiten</Link>
            </div>
            {activeTeil2Moment ? (
              <p className="textMuted" style={{ fontSize: "0.9rem" }}>
                Aktiv: {momentSpeechLabel(activeTeil2Moment)}
              </p>
            ) : null}
            {teil2BlockedReason && !anarchyPlayback.running ? (
              <p className="textMuted">{teil2BlockedReason}</p>
            ) : null}
          </section>

          {teil2BeatCount > 0 ? (
            <section className="card col">
              <h2>Teil-2-Beats</h2>
              <ol style={{ margin: 0, paddingLeft: "1.25rem" }}>
                {teil2Moments.map((moment, index) => (
                  <li
                    key={moment.id}
                    style={{
                      marginBottom: "0.5rem",
                      opacity: anarchyPlayback.momentIndex === index && anarchyPlayback.running ? 1 : 0.85
                    }}
                  >
                    <strong>{momentSpeechLabel(moment)}</strong>
                    <span className="textMuted" style={{ fontSize: "0.85rem" }}>
                      {" "}
                      · Anarchie {(moment.anarchy_level * 100).toFixed(0)}%
                      {moment.avatar_layers?.length
                        ? ` · ${moment.projector_mode === "all" ? "alle Beamer" : moment.avatar_layers.map((l) => l.projector).join(", ")}`
                        : ""}
                    </span>
                    {moment.text_excerpt ? (
                      <p className="textMuted" style={{ fontSize: "0.85rem", margin: "0.15rem 0 0" }}>
                        {moment.text_excerpt}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ol>
            </section>
          ) : null}
        </>
      ) : null}

      {corpus && teil2BeatCount > 0 &&
      (teil2Only || !script || anarchyPlayback.running || anarchyPlayback.paused) ? (
        <footer className="performanceTransport" aria-label="Teil-2-Steuerung">
          <div className="performanceTransportInner">
              <div className="performanceTransportMeta">
                <strong>
                  Beat {anarchyPlayback.momentIndex >= 0 ? anarchyPlayback.momentIndex + 1 : "—"} / {teil2BeatCount}
                </strong>
                <span className="textMuted performanceTransportDetail">
                  {anarchyPlayback.completed
                    ? "Beendet"
                    : anarchyPlayback.running
                      ? anarchyPlayback.paused
                        ? "Pausiert"
                        : `${activeTeil2Moment ? momentSpeechLabel(activeTeil2Moment) : "Läuft"} · Anarchie ${(anarchyPlayback.anarchyLevel * 100).toFixed(0)}%`
                      : teil2BlockedReason ?? "Bereit"}
                </span>
              </div>
              <div className="performanceTransportControls">
                {!anarchyPlayback.running || anarchyPlayback.paused ? (
                  <button
                    type="button"
                    className="machineStartBtn"
                    disabled={!canPlayTeil2}
                    onClick={handlePlayTeil2}
                  >
                    {anarchyPlayback.paused ? "▶ Fortsetzen" : "▶ Play"}
                  </button>
                ) : (
                  <button type="button" onClick={handlePause}>
                    ⏸ Pause
                  </button>
                )}
                <button
                  type="button"
                  className="machineStopBtn"
                  onClick={handleStop}
                  disabled={!anarchyPlayback.running && !anarchyPlayback.paused}
                >
                  ⏹ Stop
                </button>
              </div>
            </div>
        </footer>
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
