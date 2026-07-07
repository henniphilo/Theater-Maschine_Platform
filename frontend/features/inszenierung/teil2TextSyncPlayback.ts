import { armDirectorForPerformance, stopDirectorPerformance } from "@/lib/api/director";
import { getPlaybackRate, playBlob, sleepWallMs, waitWhilePlaybackPaused } from "@/lib/api/client";
import type { PerformanceSpeaker } from "@/lib/types/director";
import type { AvatarTextSegment, SceneCorpus, Teil2PerformancePlan } from "@/lib/types/inszenierung";
import {
  createCuePlaybackContext,
  firePerformanceEndCues,
  fireSentenceCues,
  fireStartCues,
  fireTimeCues
} from "@/features/show/cuePlayback";
import { textPositionForPlayback } from "@/features/show/mediaMentions";
import {
  fireAllRemainingAvatarSegments,
  fireInitialAvatarSegments,
  fireRemainingSentenceSegments,
  resolveSentenceCharStarts,
  scheduleAvatarSegmentsAtPosition,
  sentenceSpanLength
} from "@/features/inszenierung/avatarCuePlayback";
import { resolveSentenceSpeech } from "@/features/inszenierung/inszenierungBuffer";

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

export function stopTextSyncPlayback(): void {
  stopDirectorPerformance();
}

function scaledHighlightMs(): number {
  return 150 / getPlaybackRate();
}

export async function runTextSyncPlayback(
  corpus: SceneCorpus,
  plan: Teil2PerformancePlan,
  speaker: PerformanceSpeaker,
  ttsAvailable: boolean,
  onUpdate: (patch: Partial<TextSyncPlaybackState>) => void,
  shouldAbort: () => boolean,
  options?: { tryout?: boolean; startSentenceIndex?: number; endSentenceIndex?: number }
): Promise<void> {
  armDirectorForPerformance({ tryout: options?.tryout });
  const sentences = plan.sentences;
  const startIndex = Math.max(0, Math.min(options?.startSentenceIndex ?? 0, sentences.length - 1));
  const endIndex = Math.max(
    startIndex,
    Math.min(options?.endSentenceIndex ?? sentences.length - 1, sentences.length - 1)
  );
  const scriptText = corpus.script_text ?? sentences.join(" ");
  const sentenceCharStarts = resolveSentenceCharStarts(plan, scriptText);
  const firedSegments = new Set<string>();
  let cumulativeTime = 0;

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

  const onSegmentFired = (segment: AvatarTextSegment) => {
    onUpdate({ activeAvatarSegment: segment });
  };

  const anarchyForSegment = (segment: AvatarTextSegment) =>
    anarchyForSentence(segment.start_sentence_index, sentences.length, plan, corpus);

  if (startIndex === 0) {
    fireStartCues(cueCtx);
    await fireInitialAvatarSegments(
      plan,
      firedSegments,
      sentenceCharStarts,
      anarchyForSegment,
      cueCtx.onCommands,
      shouldAbort,
      onSegmentFired
    );
  }

  for (let index = startIndex; index <= endIndex; index++) {
    if (shouldAbort()) break;
    if (!(await waitWhilePlaybackPaused(shouldAbort))) break;

    const sentence = sentences[index];
    const anarchyLevel = anarchyForSentence(index, sentences.length, plan, corpus);
    onUpdate({ sentenceIndex: index, anarchyLevel, activeAvatarSegment: null });

    fireSentenceCues(cueCtx, index, sentence);

    if (!ttsAvailable) {
      if (!(await sleepWallMs(1200, shouldAbort))) break;
      await fireRemainingSentenceSegments(
        plan,
        index,
        firedSegments,
        sentenceCharStarts,
        scriptText.length,
        anarchyLevel,
        cueCtx.onCommands,
        shouldAbort,
        onSegmentFired
      );
      continue;
    }

    const blob = await resolveSentenceSpeech(corpus.id, index, sentence, speaker);
    if (shouldAbort()) break;

    const sentenceStart = cumulativeTime;
    let lastDuration = 0;
    await playBlob(blob, {
      shouldAbort,
      onTimeUpdate: (current, duration) => {
        if (Number.isFinite(duration)) lastDuration = duration;
        void fireTimeCues(cueCtx, sentenceStart + current);
        const spanLength = sentenceSpanLength(index, sentenceCharStarts, scriptText.length);
        const localPos = textPositionForPlayback(current, duration, spanLength);
        const globalPos = sentenceCharStarts[index] + localPos;
        scheduleAvatarSegmentsAtPosition(
          plan,
          globalPos,
          firedSegments,
          sentenceCharStarts,
          anarchyForSegment,
          cueCtx.onCommands,
          shouldAbort,
          onSegmentFired
        );
      }
    });

    await fireRemainingSentenceSegments(
      plan,
      index,
      firedSegments,
      sentenceCharStarts,
      scriptText.length,
      anarchyLevel,
      cueCtx.onCommands,
      shouldAbort,
      onSegmentFired
    );

    cumulativeTime += Number.isFinite(lastDuration) ? lastDuration : 0;
  }

  if (!shouldAbort()) {
    await fireAllRemainingAvatarSegments(
      plan,
      firedSegments,
      sentenceCharStarts,
      anarchyForSegment,
      cueCtx.onCommands,
      shouldAbort,
      onSegmentFired
    );
    await firePerformanceEndCues(cueCtx.onCommands, shouldAbort);
  }

  onUpdate({
    running: false,
    completed: !shouldAbort(),
    sentenceIndex: shouldAbort() ? startIndex : endIndex,
    activeOscBridge: null,
    activeAvatarSegment: null
  });
}
