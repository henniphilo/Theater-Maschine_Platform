"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Teil2PerformanceBar } from "@/components/show/Teil2PerformanceBar";
import { Teil2AvatarSegmentBlock } from "@/components/show/Teil2AvatarSegmentBlock";
import { activeAvatarSegmentIndex } from "@/features/inszenierung/teil2AvatarSections";
import { readPerformanceTryout } from "@/components/show/PerformanceTryoutControl";
import { fetchTTSStatus, setPlaybackPaused, stopPlayback } from "@/lib/api/client";
import { fetchCorpus } from "@/lib/api/inszenierung";
import type { PerformanceSpeaker } from "@/lib/types/director";
import {
  INITIAL_TEXT_SYNC_STATE,
  runTextSyncPlayback,
  stopTextSyncPlayback,
  type TextSyncPlaybackState
} from "@/features/inszenierung/teil2TextSyncPlayback";
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
  planSpeechLabel,
  startInszenierungBuffer,
  subscribeInszenierungBuffer
} from "@/features/inszenierung/inszenierungBuffer";
import type { SceneCorpus } from "@/lib/types/inszenierung";
import { sessionGet } from "@/lib/browser/session";
import { useRemoteTransportListener } from "@/features/show/useRemoteTransportListener";

function AuffuehrungContent() {
  const searchParams = useSearchParams();
  const corpusId = searchParams.get("id") ?? sessionGet("currentCorpusId") ?? "";
  const [corpus, setCorpus] = useState<SceneCorpus | null>(null);
  const [textSyncPlayback, setTextSyncPlayback] = useState<TextSyncPlaybackState>(INITIAL_TEXT_SYNC_STATE);
  const [anarchyPlayback, setAnarchyPlayback] = useState<AnarchyPlaybackState>(INITIAL_ANARCHY_STATE);
  const [ttsAvailable, setTtsAvailable] = useState(false);
  const [bufferState, setBufferState] = useState<InszenierungBufferState | null>(null);
  const [speaker, setSpeaker] = useState<PerformanceSpeaker>("narrator");
  const abortRef = useRef(false);
  const genRef = useRef(0);

  const usesTextSync = Boolean(corpus?.teil2_plan?.sentences?.length);
  const plan = corpus?.teil2_plan ?? null;

  useEffect(() => {
    return subscribeInszenierungBuffer(setBufferState);
  }, []);

  useEffect(() => {
    if (!corpusId) return;
    void fetchCorpus(corpusId).then((data) => {
      setCorpus(data);
      if (data.teil2_plan?.performance_speaker) {
        setSpeaker(data.teil2_plan.performance_speaker);
      }
    });
    fetchTTSStatus()
      .then((s) => setTtsAvailable(s.available))
      .catch(() => undefined);
  }, [corpusId]);

  const hasPlan = usesTextSync || (corpus?.composition?.moments?.length ?? 0) > 0;
  const needsTts = usesTextSync ? ttsAvailable : corpus?.composition ? planRequiresTts(corpus.composition) : false;
  const bufferReady = corpus ? isInszenierungBuffered(corpus.id, ttsAvailable) : false;
  const canPlay = hasPlan && (!needsTts || bufferReady || !ttsAvailable);
  const running = usesTextSync ? textSyncPlayback.running : anarchyPlayback.running;
  const paused = usesTextSync ? textSyncPlayback.paused : anarchyPlayback.paused;

  useEffect(() => {
    if (!corpus || !hasPlan || bufferReady || !needsTts) return;
    if (ttsAvailable) startInszenierungBuffer(corpus, ttsAvailable, speaker);
  }, [corpus, hasPlan, bufferReady, ttsAvailable, needsTts, speaker]);

  useEffect(() => {
    if (!corpus || !usesTextSync || !ttsAvailable) return;
    startInszenierungBuffer(corpus, ttsAvailable, speaker);
  }, [speaker, corpus, usesTextSync, ttsAvailable]);

  const play = useCallback(
    async (startSentenceIndex = 0, endSentenceIndex?: number, options?: { forceRestart?: boolean }) => {
      if (!corpus || (!canPlay && !options?.forceRestart)) return;
      if (!options?.forceRestart) {
        if (paused && running) {
          setPlaybackPaused(false);
          if (usesTextSync) setTextSyncPlayback((prev) => ({ ...prev, paused: false }));
          else setAnarchyPlayback((prev) => ({ ...prev, paused: false }));
          return;
        }
        if (running) return;
      }
      const gen = ++genRef.current;
      abortRef.current = false;
      const shouldAbort = () => abortRef.current || gen !== genRef.current;
      setPlaybackPaused(false);

      if (usesTextSync && plan) {
        setTextSyncPlayback({
          ...INITIAL_TEXT_SYNC_STATE,
          running: true,
          paused: false,
          sentenceIndex: startSentenceIndex
        });
        await runTextSyncPlayback(
          corpus,
          plan,
          speaker,
          ttsAvailable,
          (patch) => {
            if (gen === genRef.current) setTextSyncPlayback((prev) => ({ ...prev, ...patch }));
          },
          shouldAbort,
          { tryout: readPerformanceTryout(), startSentenceIndex, endSentenceIndex, playbackGeneration: gen }
        );
        return;
      }

      if (!corpus.composition) return;
      setAnarchyPlayback({ ...INITIAL_ANARCHY_STATE, running: true, paused: false });
      await runAnarchyPlayback(
        corpus,
        corpus.composition,
        ttsAvailable,
        (patch) => {
          if (gen === genRef.current) setAnarchyPlayback((prev) => ({ ...prev, ...patch }));
        },
        shouldAbort,
        { playbackGeneration: gen, tryout: readPerformanceTryout() }
      );
    },
    [corpus, canPlay, ttsAvailable, usesTextSync, plan, speaker, paused, running]
  );

  function pause() {
    setPlaybackPaused(true);
    if (usesTextSync) setTextSyncPlayback((prev) => ({ ...prev, paused: true }));
    else setAnarchyPlayback((prev) => ({ ...prev, paused: true }));
  }

  function resume() {
    setPlaybackPaused(false);
    if (usesTextSync) setTextSyncPlayback((prev) => ({ ...prev, paused: false }));
    else setAnarchyPlayback((prev) => ({ ...prev, paused: false }));
  }

  function stop() {
    abortRef.current = true;
    genRef.current += 1;
    stopPlayback();
    if (usesTextSync) stopTextSyncPlayback();
    else stopAnarchyPlayback();
    setTextSyncPlayback({ ...INITIAL_TEXT_SYNC_STATE, paused: true });
    setAnarchyPlayback({ ...INITIAL_ANARCHY_STATE, paused: true });
  }

  function handlePlay(startSentenceIndex = 0) {
    if (paused && running) {
      resume();
      return;
    }
    if (running) return;
    void play(startSentenceIndex);
  }

  useRemoteTransportListener({
    onPlay: () => handlePlay(0),
    onPause: pause,
    onStop: stop
  });

  function handleJumpToAvatarSegment(segmentIndex: number) {
    if (!canPlay || !usesTextSync || !plan) return;
    const segment = plan.avatar_segments[segmentIndex];
    if (!segment) return;
    // Soft seek — no emergency_stop (races with Probebetrieb re-arm).
    abortRef.current = true;
    genRef.current += 1;
    stopPlayback();
    setTextSyncPlayback((prev) => ({ ...prev, running: false, paused: true }));
    setAnarchyPlayback((prev) => ({ ...prev, running: false, paused: true }));
    window.setTimeout(() => {
      void play(segment.start_sentence_index, undefined, { forceRestart: true });
    }, 0);
  }

  const sectionCount = plan?.avatar_segments.length ?? 0;
  const progressIndex = usesTextSync ? textSyncPlayback.sentenceIndex : anarchyPlayback.momentIndex;
  const activeSegmentIndex =
    usesTextSync && plan ? activeAvatarSegmentIndex(plan.avatar_segments, progressIndex) : -1;
  const completed = usesTextSync ? textSyncPlayback.completed : anarchyPlayback.completed;
  const anarchyLevel = usesTextSync ? textSyncPlayback.anarchyLevel : anarchyPlayback.anarchyLevel;

  const statusDetail = usesTextSync
    ? completed
      ? "Beendet"
      : running
        ? paused
          ? "Pausiert"
          : `${planSpeechLabel(plan!)} · Anarchie ${(anarchyLevel * 100).toFixed(0)}%`
        : needsTts && !bufferReady && ttsAvailable
          ? bufferState
            ? bufferStatusLabel(bufferState)
            : "Lädt …"
          : "Bereit"
    : completed
      ? "Beendet"
      : running
        ? paused
          ? "Pausiert"
          : "Läuft"
        : "Bereit";

  return (
    <main className={`container col livePage${corpus ? " pageWithPerformanceTransport" : ""}`}>
      <div className="pageHeader">
        <h1>Teil 2 — Aufführung</h1>
        {running ? <span className="liveBadge">{paused ? "Pausiert" : "Live"}</span> : null}
      </div>
      <p className="textMuted" style={{ fontSize: "0.85rem" }}>
        Remote vom Handy: diese Seite offen lassen, dann{" "}
        <Link href="/remote">/remote</Link> auf dem Handy öffnen (
        <code>http://&lt;Mac-IP&gt;:3003/remote</code>).
      </p>

      {corpus ? (
        <section className="card col">
          <h2>{corpus.title}</h2>
          {!hasPlan ? (
            <p className="textFaint">Zuerst auf der Inszenierungsseite vorbereiten.</p>
          ) : usesTextSync ? (
            <>
              <label htmlFor="playback-speaker">Stimme</label>
              <select
                id="playback-speaker"
                value={speaker}
                disabled={running}
                onChange={(e) => setSpeaker(e.target.value as PerformanceSpeaker)}
              >
                <option value="narrator">Erzähler</option>
                <option value="AI_A">Stimme A</option>
                <option value="AI_B">Stimme B</option>
              </select>
              <p className="textMuted">
                {sectionCount} Avatar-Abschnitte · {planSpeechLabel(plan!)} · TTS in {plan?.sentences.length ?? 0}{" "}
                Satzschritten
              </p>
              {needsTts && !bufferReady && ttsAvailable ? (
                <p className="textMuted">{bufferState ? bufferStatusLabel(bufferState) : "Stimme wird vorbereitet …"}</p>
              ) : null}
              {textSyncPlayback.activeAvatarSegment ? (
                <p className="textMuted">Avatar: {textSyncPlayback.activeAvatarSegment.csv_cue_ids.join(", ")}</p>
              ) : null}
            </>
          ) : (
            <p className="textMuted">{corpus.composition?.moments.length} Beats (Legacy-Timeline)</p>
          )}
        </section>
      ) : null}

      {corpus && usesTextSync && plan && sectionCount > 0 ? (
        <section className="card col scriptDocument">
          <h2>Avatar-Abschnitte</h2>
          <p className="textMuted" style={{ fontSize: "0.9rem", marginTop: 0 }}>
            Wie in der CSV — Klick testet Stimme und Signale für diesen Abschnitt.
          </p>
          <ul className="teil2SentenceList liveSectionList">
            {plan.avatar_segments.map((segment, index) => (
              <li key={segment.csv_cue_ids.join("-")}>
                <Teil2AvatarSegmentBlock
                  segment={segment}
                  index={index}
                  active={activeSegmentIndex === index && (running || paused)}
                  clickable={canPlay}
                  onSelect={() => handleJumpToAvatarSegment(index)}
                />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {corpus && hasPlan ? (
        <Teil2PerformanceBar
          positionLabel={
            usesTextSync
              ? `Abschnitt ${activeSegmentIndex >= 0 ? activeSegmentIndex + 1 : "—"} / ${sectionCount}`
              : `Beat ${progressIndex >= 0 ? progressIndex + 1 : "—"} / ${corpus.composition?.moments.length ?? 0}`
          }
          currentIndex={
            usesTextSync
              ? activeSegmentIndex >= 0
                ? activeSegmentIndex + 1
                : null
              : progressIndex >= 0
                ? progressIndex + 1
                : null
          }
          totalCount={usesTextSync ? sectionCount : corpus.composition?.moments.length ?? 0}
          detail={statusDetail}
          running={running}
          paused={paused}
          canPlay={canPlay}
          onPlay={() => handlePlay(0)}
          onPause={pause}
          onStop={stop}
        />
      ) : null}

      <Link href={`/inszenierung?id=${corpusId}`}>← Inszenierung</Link>
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
