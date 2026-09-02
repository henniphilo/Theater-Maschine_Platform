import { armDirectorForPerformance, startFrontendPlaybackTrace, stopDirectorPerformance } from "@/lib/api/director";
import { getPlaybackRate, playBlob, sleepWallMs, waitWhilePlaybackPaused } from "@/lib/api/client";
import type { DramaturgyDecision, PerformanceSpeaker } from "@/lib/types/director";
import type { AvatarTextSegment, SceneCorpus, Teil2PerformancePlan } from "@/lib/types/inszenierung";
import {
  createCuePlaybackContext,
  firePerformanceEndCues,
  fireSentenceCues,
  fireStartCues,
  fireTimeCues,
  markTimeCuesBefore
} from "@/features/show/cuePlayback";
import {
  bindAvatarChainContext,
  countUnfiredAvatarSegments,
  clearPendingAvatarDoneGate,
  drainRemainingAvatarChain,
  resetAvatarPlaybackState,
  fireInitialAvatarSegments,
  markAvatarSegmentsBeforeSentenceIndex,
  resolveSentenceCharStarts
} from "@/features/inszenierung/avatarCuePlayback";
import { resolveSentenceSpeech } from "@/features/inszenierung/inszenierungBuffer";

/** Approximate German TTS rate for seek-clock estimates (chars / second). */
export const NARRATION_CHARS_PER_SEC = 14;

export type TextSyncPlaybackState = {
  running: boolean;
  paused: boolean;
  sentenceIndex: number;
  anarchyLevel: number;
  activeAvatarSegment: AvatarTextSegment | null;
  completed: boolean;
  activeOscBridge: string | null;
};

export const INITIAL_TEXT_SYNC_STATE: TextSyncPlaybackState = {
  running: false,
  paused: false,
  sentenceIndex: -1,
  anarchyLevel: 0,
  activeAvatarSegment: null,
  completed: false,
  activeOscBridge: null
};

function anarchyForSentence(
  sentenceIndex: number,
  total: number,
  plan: Teil2PerformancePlan,
  corpus: SceneCorpus
): number {
  const start = corpus.gesamtkonzept?.anarchy_curve?.start ?? 0.35;
  const end = plan.anarchy_level_end;
  if (total <= 1) return end;
  const t = sentenceIndex / (total - 1);
  return start + (end - start) * t;
}

/** Hard stop: emergency-stop director (blackout). Prefer softAbortTextSyncPlayback during Teil-2 show control. */
export function stopTextSyncPlayback(): void {
  resetAvatarPlaybackState();
  void stopDirectorPerformance().catch(() => undefined);
}

/**
 * Soft seek abort: clear Done-gate / chain context without emergency_stop
 * (avoids racing Probebetrieb re-arm).
 */
export function softAbortTextSyncPlayback(): void {
  resetAvatarPlaybackState();
}

/** Sum estimated narration seconds for sentences [0, beforeIndex). */
export function estimateNarrationSecondsBefore(
  sentences: string[],
  beforeIndex: number,
  charsPerSec = NARRATION_CHARS_PER_SEC
): number {
  const rate = charsPerSec > 0 ? charsPerSec : NARRATION_CHARS_PER_SEC;
  let chars = 0;
  const end = Math.max(0, Math.min(beforeIndex, sentences.length));
  for (let i = 0; i < end; i++) {
    chars += sentences[i]?.length ?? 0;
  }
  return chars / rate;
}

function scaledHighlightMs(): number {
  return 150 / getPlaybackRate();
}

function atmosphereDramaturgy(plan: Teil2PerformancePlan): DramaturgyDecision {
  return {
    ...plan.dramaturgy,
    visual: null,
    sound: null,
    light: null,
    reason: "Teil-2 Atmosphäre (parallel)",
    tags: ["teil2", "atmosphere"],
    cue_points: plan.atmosphere_cue_points ?? []
  };
}

export async function runTextSyncPlayback(
  corpus: SceneCorpus,
  plan: Teil2PerformancePlan,
  speaker: PerformanceSpeaker,
  ttsAvailable: boolean,
  onUpdate: (patch: Partial<TextSyncPlaybackState>) => void,
  shouldAbort: () => boolean,
  options?: { tryout?: boolean; startSentenceIndex?: number; endSentenceIndex?: number; playbackGeneration?: number }
): Promise<void> {
  if (options?.playbackGeneration != null) {
    startFrontendPlaybackTrace({
      generation: options.playbackGeneration,
      source: "teil2_text_sync",
      route: "/auffuehrung"
    });
  }
  // Drop leftover locks/timers from a previous Stop so the second run starts clean.
  resetAvatarPlaybackState();
  await armDirectorForPerformance({ tryout: options?.tryout });
  const sentences = plan.sentences;
  const startIndex = Math.max(0, Math.min(options?.startSentenceIndex ?? 0, sentences.length - 1));
  const endIndex = Math.max(
    startIndex,
    Math.min(options?.endSentenceIndex ?? sentences.length - 1, sentences.length - 1)
  );
  const scriptText = corpus.script_text ?? sentences.join(" ");
  const sentenceCharStarts = resolveSentenceCharStarts(plan, scriptText);
  const firedSegments = new Set<string>();
  let cumulativeTime =
    startIndex > 0 ? estimateNarrationSecondsBefore(sentences, startIndex) : 0;
  let lastIndex = startIndex;

  const cueCtx = createCuePlaybackContext(
    plan.dramaturgy,
    scriptText,
    async (commands) => {
      const bridge = commands[0]?.bridge ?? null;
      onUpdate({ activeOscBridge: bridge });
      await sleepWallMs(scaledHighlightMs(), shouldAbort);
      onUpdate({ activeOscBridge: null });
    },
    shouldAbort
  );

  const atmosphereCtx = createCuePlaybackContext(
    atmosphereDramaturgy(plan),
    scriptText,
    cueCtx.onCommands,
    shouldAbort
  );

  // Jump mid-show: skip earlier avatars; mark only past time cues relative to seek clock.
  if (startIndex > 0) {
    markAvatarSegmentsBeforeSentenceIndex(plan, startIndex, firedSegments);
    markTimeCuesBefore(cueCtx, cumulativeTime);
    markTimeCuesBefore(atmosphereCtx, cumulativeTime);
  }

  const fireTimedCues = (elapsedSec: number) => {
    fireTimeCues(cueCtx, elapsedSec);
    fireTimeCues(atmosphereCtx, elapsedSec);
  };

  const onSegmentFired = (segment: AvatarTextSegment) => {
    onUpdate({ activeAvatarSegment: segment });
  };

  const anarchyForSegment = (segment: AvatarTextSegment) =>
    anarchyForSentence(segment.start_sentence_index, sentences.length, plan, corpus);

  bindAvatarChainContext({
    plan,
    fired: firedSegments,
    sentenceCharStarts,
    scriptText,
    anarchyLevelFor: anarchyForSegment,
    onCommands: cueCtx.onCommands,
    shouldAbort,
    onSegmentFired
  });

  if (startIndex === 0) {
    fireStartCues(cueCtx);
  }
  await fireInitialAvatarSegments(
    plan,
    firedSegments,
    sentenceCharStarts,
    anarchyForSegment,
    cueCtx.onCommands,
    shouldAbort,
    onSegmentFired,
    scriptText
  );

  try {
    for (let index = startIndex; index <= endIndex; index++) {
      if (shouldAbort()) break;
      if (!(await waitWhilePlaybackPaused(shouldAbort))) break;

      lastIndex = index;
      const sentence = sentences[index];
      const anarchyLevel = anarchyForSentence(index, sentences.length, plan, corpus);
      // Keep activeAvatarSegment from the CSV chain — clearing it here hid process/text UI.
      onUpdate({ sentenceIndex: index, anarchyLevel });

      fireSentenceCues(cueCtx, index, sentence);

      if (!ttsAvailable) {
        cumulativeTime += 1.2;
        if (!(await sleepWallMs(1200, shouldAbort))) break;
        continue;
      }

      let blob: Blob;
      try {
        blob = await resolveSentenceSpeech(corpus.id, index, sentence, speaker);
      } catch (err) {
        console.warn(`[teil2] TTS failed for sentence ${index} — skipping:`, err);
        const fallbackSec = Math.max(1.2, Math.min(12, sentence.length / 14));
        cumulativeTime += fallbackSec;
        if (!(await sleepWallMs(fallbackSec * 1000, shouldAbort))) break;
        continue;
      }
      if (shouldAbort()) break;

      const sentenceStart = cumulativeTime;
      let lastDuration = 0;
      try {
        await playBlob(blob, {
          shouldAbort,
          onTimeUpdate: (current, duration) => {
            if (Number.isFinite(duration)) lastDuration = duration;
            void fireTimedCues(sentenceStart + current);
          }
        });
      } catch (err) {
        console.warn(`[teil2] Audio playback failed for sentence ${index} — continuing:`, err);
      }

      if (shouldAbort()) break;
      cumulativeTime += Number.isFinite(lastDuration) ? lastDuration : 0;
    }

    if (!shouldAbort()) {
      // TTS may finish while long CSV clips (e.g. sch7 ~45s) are still queued —
      // drain the avatar chain before tearing down context or firing end Black.
      await drainRemainingAvatarChain(shouldAbort, plan, firedSegments);
      bindAvatarChainContext(null);
      const unfired = countUnfiredAvatarSegments(plan, firedSegments);
      if (unfired > 0) {
        console.warn(
          `[teil2] ${unfired} Avatar-Segmente nicht ausgelöst — CSV-Reihenfolge / Clip-Dauer prüfen.`
        );
      }
      await firePerformanceEndCues(cueCtx.onCommands, shouldAbort);
    } else {
      clearPendingAvatarDoneGate();
    }
  } finally {
    bindAvatarChainContext(null);
  }

  onUpdate({
    running: false,
    completed: !shouldAbort(),
    // On abort keep the live sentence so Stop→Play / soft seek can resume.
    sentenceIndex: shouldAbort() ? lastIndex : endIndex,
    activeOscBridge: null,
    activeAvatarSegment: null
  });
}
