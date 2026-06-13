"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { AppNav } from "@/components/layout/AppNav";
import { ScriptBeatBlock } from "@/components/script/ScriptBeatBlock";
import { MachineStage } from "@/components/show/MachineStage";
import { StagePreview } from "@/components/stage/StagePreview";
import { fetchTTSStatus } from "@/lib/api/client";
import { fetchMediaCatalog } from "@/lib/api/media";
import { fetchScript } from "@/lib/api/script";
import {
  INITIAL_PLAYBACK_STATE,
  runScriptPlayback,
  stopScriptPlayback,
  type PlaybackState
} from "@/features/show/scriptPlayback";
import { buildMediaLookup, type MediaCatalog, type MediaLookup } from "@/lib/types/media";
import type { ProductionScript } from "@/lib/types/script";
import type { DirectorPayload } from "@/lib/types/director";

function AuffuehrungContent() {
  const searchParams = useSearchParams();
  const scriptId = searchParams.get("id") ?? sessionStorage.getItem("currentScriptId") ?? "";
  const [script, setScript] = useState<ProductionScript | null>(null);
  const [playback, setPlayback] = useState<PlaybackState>(INITIAL_PLAYBACK_STATE);
  const [mediaCatalog, setMediaCatalog] = useState<MediaCatalog | null>(null);
  const [media, setMedia] = useState<MediaLookup | undefined>();
  const [ttsAvailable, setTtsAvailable] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const abortRef = useRef(false);
  const playbackGenRef = useRef(0);

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
      .then((s) => setTtsAvailable(s.available))
      .catch(() => undefined);
    fetchMediaCatalog()
      .then((catalog) => {
        setMediaCatalog(catalog);
        setMedia(buildMediaLookup(catalog));
      })
      .catch(() => undefined);
  }, [load]);

  const ready = script?.status === "ready";
  const currentBeat = playback.beatIndex >= 0 ? script?.beats[playback.beatIndex] : undefined;
  const canResume = playback.paused && !playback.completed && playback.beatIndex >= 0;

  const directorPayload: DirectorPayload | undefined = currentBeat?.dramaturgy
    ? {
        event: {},
        decision: currentBeat.dramaturgy,
        executed: playback.showPhase === "sent",
        blocked_reason: null,
        planned_commands: currentBeat.planned_commands,
        osc_commands: []
      }
    : undefined;

  const playFrom = useCallback(
    async (startIndex: number) => {
      if (!script || !ready) return;
      const gen = ++playbackGenRef.current;
      setError("");
      abortRef.current = false;
      setPlayback((prev) => ({ ...prev, beatIndex: startIndex, paused: false, completed: false }));

      await runScriptPlayback(
        script.beats,
        ttsAvailable,
        startIndex,
        (update) => {
          if (gen === playbackGenRef.current) {
            setPlayback((prev) => ({ ...prev, ...update }));
          }
        },
        () => abortRef.current
      );
    },
    [script, ready, ttsAvailable]
  );

  function handleStart() {
    const from = canResume ? playback.beatIndex : playback.beatIndex >= 0 ? playback.beatIndex : 0;
    void playFrom(from);
  }

  function handleStop() {
    abortRef.current = true;
    playbackGenRef.current += 1;
    stopScriptPlayback();
    setPlayback((prev) => ({
      ...prev,
      running: false,
      paused: true,
      activeOscBridge: null,
      activeOscCommand: null
    }));
  }

  function handleJumpToBeat(index: number) {
    if (!script || index < 0 || index >= script.beats.length) return;
    setPlayback((prev) => ({ ...prev, beatIndex: index, paused: true, completed: false }));

    if (playback.running) {
      abortRef.current = true;
      playbackGenRef.current += 1;
      stopScriptPlayback();
      void playFrom(index);
    }
  }

  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Aufführung</h1>
        <AppNav />
      </div>
      <p className="textMuted">
        Timeline oder Textabschnitt anklicken zum Springen. Stoppen und an derselben Stelle fortsetzen.
      </p>

      {loading ? <p className="textFaint">Lade Stück …</p> : null}
      {error ? <div className="textError" role="alert">{error}</div> : null}
      {!scriptId && !loading ? (
        <p className="textFaint">
          Kein Stück. <Link href="/dramaturgie">Dramaturgie</Link> oder <Link href="/stueck">Stücktext</Link>
        </p>
      ) : null}

      {script ? (
        <>
          <section className="card col">
            <h2>{script.title}</h2>
            {mediaCatalog ? (
              <p className="textMuted" style={{ fontSize: "0.85rem" }}>
                Medien-Datenbank: <code>{mediaCatalog.data_dir}/media.json</code> · TouchDesigner OSC{" "}
                <code>
                  {mediaCatalog.touchdesigner.osc_host}:{mediaCatalog.touchdesigner.osc_port}
                </code>
                {mediaCatalog.touchdesigner.osc_dry_run ? " (DRY-RUN)" : ""}
              </p>
            ) : null}
            <StagePreview
              beats={script.beats}
              activeBeatIndex={playback.beatIndex}
              activeOscBridge={playback.activeOscBridge}
              running={playback.running}
              paused={playback.paused}
              onBeatSelect={ready ? handleJumpToBeat : undefined}
              media={media}
            />
            <div className="row">
              <button
                type="button"
                className="machineStartBtn"
                onClick={handleStart}
                disabled={!ready || playback.running}
              >
                {playback.running
                  ? "Läuft …"
                  : canResume
                    ? `Fortsetzen ab Abschnitt ${playback.beatIndex + 1}`
                    : playback.beatIndex > 0
                      ? `Starten ab Abschnitt ${playback.beatIndex + 1}`
                      : "Maschine starten"}
              </button>
              {playback.running || playback.paused ? (
                <button type="button" className="machineStopBtn" onClick={handleStop} disabled={!playback.running}>
                  Stoppen
                </button>
              ) : null}
            </div>
            {!ready ? (
              <p className="textFaint">Stück noch nicht bereit — zuerst Dramaturgie abschließen.</p>
            ) : null}
            {playback.completed ? (
              <p className="textMuted">Aufführung beendet. Erneut starten oder Abschnitt wählen.</p>
            ) : null}
          </section>

          <MachineStage
            running={playback.running}
            beatIndex={Math.max(playback.beatIndex, 0)}
            beatTotal={script.beats.length}
            speaker={
              currentBeat?.speaker === "AI_A"
                ? "openai"
                : currentBeat?.speaker === "AI_B"
                  ? "anthropic"
                  : currentBeat?.speaker === "narrator"
                    ? "narrator"
                    : undefined
            }
            director={directorPayload}
            showPhase={playback.showPhase}
            activeOscBridge={playback.activeOscBridge}
            activeOscCommand={playback.activeOscCommand}
            onStop={handleStop}
          />

          <section className="card col scriptDocument">
            <h2>Stücktext (klickbar)</h2>
            <p className="textMuted" style={{ fontSize: "0.9rem" }}>
              Klick auf einen Abschnitt springt dorthin{playback.running ? " und setzt die Wiedergabe fort" : ""}.
            </p>
            {script.beats.map((beat, index) => (
              <ScriptBeatBlock
                key={beat.id}
                beat={beat}
                media={media}
                highlight={index === playback.beatIndex && (playback.running || playback.paused)}
                sentenceIndex={index === playback.beatIndex ? playback.sentenceIndex : undefined}
                clickable={ready}
                onSelect={() => handleJumpToBeat(index)}
              />
            ))}
          </section>
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
