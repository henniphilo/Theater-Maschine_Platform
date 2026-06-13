import { fetchSpeechBlob, playBlob, stopPlayback } from "@/lib/api/client";
import { sentenceIndexForProgress } from "@/lib/text/splitSentences";
import type { OscCommand } from "@/lib/types/director";
import type { ScriptBeat } from "@/lib/types/script";
import {
  createCuePlaybackContext,
  fireSentenceCues,
  fireStartCues,
  fireTimeCues,
  sentencesForBeat
} from "@/features/show/cuePlayback";

const OSC_HIGHLIGHT_MS = 150;

export type PlaybackState = {
  running: boolean;
  paused: boolean;
  beatIndex: number;
  sentenceIndex: number;
  activeOscBridge: string | null;
  activeOscCommand: OscCommand | null;
  showPhase?: string;
  completed: boolean;
};

export const INITIAL_PLAYBACK_STATE: PlaybackState = {
  running: false,
  paused: false,
  beatIndex: 0,
  sentenceIndex: 0,
  activeOscBridge: null,
  activeOscCommand: null,
  completed: false
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function highlightOscSequence(
  commands: OscCommand[],
  onHighlight: (cmd: OscCommand | null, bridge: string | null) => void,
  shouldAbort: () => boolean
) {
  for (const cmd of commands) {
    if (shouldAbort()) break;
    onHighlight(cmd, cmd.bridge);
    await sleep(OSC_HIGHLIGHT_MS);
  }
  onHighlight(null, null);
}

async function playBeat(
  beat: ScriptBeat,
  beatIndex: number,
  ttsAvailable: boolean,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean
): Promise<boolean> {
  if (!beat.dramaturgy) return true;

  onState({ beatIndex, sentenceIndex: 0, showPhase: "planned", paused: false });

  const sentences = sentencesForBeat(beat.text);
  let lastSentenceIndex = -1;

  const cueCtx = createCuePlaybackContext(
    beat.dramaturgy,
    beat.text,
    async (commands) => {
      await highlightOscSequence(
        commands,
        (cmd, bridge) => onState({ activeOscCommand: cmd, activeOscBridge: bridge }),
        shouldAbort
      );
    },
    shouldAbort
  );

  if (!ttsAvailable) {
    onState({ showPhase: "cues_active" });
    await fireStartCues(cueCtx);
    for (let i = 0; i < sentences.length; i++) {
      if (shouldAbort()) return false;
      await fireSentenceCues(cueCtx, i, sentences[i]);
      onState({ sentenceIndex: i });
      await sleep(800);
    }
    onState({ showPhase: "sent" });
    return !shouldAbort();
  }

  onState({ showPhase: "speaking" });
  let cuesStarted = false;

  try {
    const blob = await fetchSpeechBlob(beat.text, beat.speaker);
    if (shouldAbort()) return false;

    await playBlob(blob, {
      onPlay: () => {
        if (cuesStarted) return;
        cuesStarted = true;
        onState({ showPhase: "cues_active" });
        void fireStartCues(cueCtx).then(() => {
          if (!shouldAbort()) onState({ showPhase: "sent" });
        });
      },
      onTimeUpdate: (current, duration) => {
        if (shouldAbort()) return;
        const sentenceIndex = sentenceIndexForProgress(current, duration, sentences.length);
        onState({ sentenceIndex });
        void fireTimeCues(cueCtx, current);
        if (sentenceIndex !== lastSentenceIndex) {
          lastSentenceIndex = sentenceIndex;
          void fireSentenceCues(cueCtx, sentenceIndex, sentences[sentenceIndex] ?? "");
        }
      }
    });

    if (shouldAbort()) return false;

    if (!cuesStarted) {
      onState({ showPhase: "cues_active" });
      await fireStartCues(cueCtx);
      for (let i = 0; i < sentences.length; i++) {
        await fireSentenceCues(cueCtx, i, sentences[i]);
      }
    }
    return !shouldAbort();
  } catch {
    if (!shouldAbort()) onState({ showPhase: "blocked" });
    return false;
  }
}

export async function runScriptPlayback(
  beats: ScriptBeat[],
  ttsAvailable: boolean,
  startBeatIndex: number,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean
): Promise<void> {
  const start = Math.max(0, Math.min(startBeatIndex, beats.length - 1));
  onState({
    running: true,
    paused: false,
    completed: false,
    beatIndex: start,
    sentenceIndex: 0,
    activeOscBridge: null,
    activeOscCommand: null
  });

  for (let index = start; index < beats.length; index++) {
    if (shouldAbort()) {
      onState({
        running: false,
        paused: true,
        beatIndex: index,
        activeOscBridge: null,
        activeOscCommand: null
      });
      return;
    }

    const ok = await playBeat(beats[index], index, ttsAvailable, onState, shouldAbort);
    if (!ok) {
      onState({
        running: false,
        paused: true,
        beatIndex: index,
        activeOscBridge: null,
        activeOscCommand: null
      });
      return;
    }
  }

  onState({
    running: false,
    paused: false,
    completed: true,
    beatIndex: 0,
    activeOscBridge: null,
    activeOscCommand: null,
    showPhase: undefined
  });
}

export function stopScriptPlayback() {
  stopPlayback();
}
