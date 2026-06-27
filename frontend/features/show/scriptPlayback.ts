import { getCachedSpeech, prefetchSpeech } from "@/lib/tts/prefetch";
import { performanceAudioUrl, prefetchPrerenderedSpeech } from "@/lib/api/performance";
import { playBlob, setPlaybackPaused, stopPlayback, waitWhilePlaybackPaused } from "@/lib/api/client";
import { armDirectorForPerformance, stopDirectorPerformance } from "@/lib/api/director";
import { sentenceIndexForProgress } from "@/lib/text/splitSentences";
import { speakerForPerformanceSentence } from "@/lib/show/performanceVoices";
import { progressFromBeat } from "@/lib/show/performanceTimeline";
import { part1Beats } from "@/lib/show/baerenklauBeat";
import type { OscCommand, PerformanceSpeaker, ShowPhase } from "@/lib/types/director";
import type { DiscussionTurn, DramaturgSpeaker, ProductionScript, ScriptBeat, ScriptSpeaker } from "@/lib/types/script";
import {
  createCuePlaybackContext,
  fireSentenceCues,
  fireStartCues,
  fireTimeCues,
  sentencesForBeat
} from "@/features/show/cuePlayback";
import {
  createDiscussionCueContext,
  fireDiscussionMentionsAtPosition,
  scheduleDiscussionCue,
  textPositionForPlayback
} from "@/features/show/discussionCuePlayback";
import type { MediaCatalog } from "@/lib/types/media";
import {
  allowlistFromPart1Selection,
  resolveTurnPlayback,
  type MediaAliasIndex,
  type MediaAllowlist
} from "@/features/show/mediaMentions";
import type { Part1BaerenklauSelection } from "@/lib/types/part1";

const OSC_HIGHLIGHT_MS = 150;
const DISCUSSION_FALLBACK_MS = 1500;
export const PERFORMANCE_PREP_PAUSE_MS = 800;

export type SegmentPhase = "discussion" | "performance";
export type PlaybackMode = "full" | "discussion" | "performance";

export type PlaybackAudioOptions = {
  ttsAvailable: boolean;
  scriptId?: string;
  hasRenderedAudio?: boolean;
  mediaAllowlist?: MediaAllowlist | null;
  mediaAliasIndex?: MediaAliasIndex | null;
  mediaCatalog?: MediaCatalog | null;
};

export type PlaybackState = {
  running: boolean;
  paused: boolean;
  beatIndex: number;
  sentenceIndex: number;
  activeOscBridge: string | null;
  activeOscCommand: OscCommand | null;
  segmentPhase?: SegmentPhase;
  discussionTurnIndex?: number;
  dramaturgSpeaker?: DramaturgSpeaker;
  performanceSpeaker?: ScriptSpeaker;
  showPhase?: ShowPhase;
  completed: boolean;
  timelineProgress: number;
  playbackMode?: PlaybackMode;
};

export const INITIAL_PLAYBACK_STATE: PlaybackState = {
  running: false,
  paused: false,
  beatIndex: 0,
  sentenceIndex: 0,
  activeOscBridge: null,
  activeOscCommand: null,
  completed: false,
  timelineProgress: 0,
  playbackMode: "full"
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function gatePlayback(shouldAbort: () => boolean): Promise<boolean> {
  return waitWhilePlaybackPaused(shouldAbort);
}

function audioReady(options: PlaybackAudioOptions): boolean {
  return Boolean(options.hasRenderedAudio || options.ttsAvailable);
}

function performanceSpeakerPool(beat: ScriptBeat): PerformanceSpeaker[] | undefined {
  const pool = beat.dramaturgy?.performance_speakers;
  return pool?.length ? pool : undefined;
}

function beatPerformanceSpeaker(
  beat: ScriptBeat,
  sentenceIndex: number
): ScriptSpeaker {
  return speakerForPerformanceSentence(
    beat.speaker,
    sentenceIndex,
    beat.order,
    performanceSpeakerPool(beat)
  );
}

async function resolveDiscussionSpeechBlob(
  options: PlaybackAudioOptions,
  beatId: string,
  turnIndex: number,
  text: string,
  speaker: DramaturgSpeaker
): Promise<Blob> {
  if (options.hasRenderedAudio && options.scriptId) {
    return prefetchPrerenderedSpeech(
      performanceAudioUrl(options.scriptId, beatId, "discussion", turnIndex)
    );
  }
  return getCachedSpeech(text, speaker);
}

async function resolvePerformanceSpeechBlob(
  options: PlaybackAudioOptions,
  beatId: string,
  sentenceIndex: number,
  sentenceText: string,
  speaker: ScriptSpeaker,
  useLegacyWholeBeat: boolean
): Promise<Blob> {
  if (options.hasRenderedAudio && options.scriptId) {
    if (useLegacyWholeBeat) {
      return prefetchPrerenderedSpeech(
        performanceAudioUrl(options.scriptId, beatId, "performance")
      );
    }
    try {
      return await prefetchPrerenderedSpeech(
        performanceAudioUrl(options.scriptId, beatId, "performance", undefined, sentenceIndex)
      );
    } catch {
      if (sentenceIndex === 0) {
        return prefetchPrerenderedSpeech(
          performanceAudioUrl(options.scriptId, beatId, "performance")
        );
      }
      throw new Error("Vorgespeicherte Satz-Audio-Datei nicht gefunden");
    }
  }
  return getCachedSpeech(sentenceText, speaker, { profile: "performance" });
}

function discussionTextForTurn(
  turn: DiscussionTurn,
  options: PlaybackAudioOptions,
  part1Selection?: Part1BaerenklauSelection | null
): { spoken: string; mentions: import("@/lib/types/script").MediaMention[] } {
  const allowlist =
    options.mediaAllowlist ??
    (part1Selection ? allowlistFromPart1Selection(part1Selection) : null);
  return resolveTurnPlayback(
    turn,
    allowlist,
    options.mediaAliasIndex ?? undefined,
    options.mediaCatalog ?? undefined
  );
}

function prefetchDiscussionTurn(
  options: PlaybackAudioOptions,
  beatId: string,
  turn: DiscussionTurn,
  turnIndex: number,
  part1Selection?: Part1BaerenklauSelection | null
): void {
  if (options.hasRenderedAudio && options.scriptId) {
    void prefetchPrerenderedSpeech(
      performanceAudioUrl(options.scriptId, beatId, "discussion", turnIndex)
    );
    return;
  }
  if (options.ttsAvailable) {
    const { spoken } = discussionTextForTurn(turn, options, part1Selection);
    prefetchSpeech(spoken, turn.speaker);
  }
}

function prefetchAllDiscussionTurns(
  options: PlaybackAudioOptions,
  beat: ScriptBeat,
  part1Selection?: Part1BaerenklauSelection | null
): void {
  const turns = beat.discussion_turns ?? [];
  for (let i = 0; i < turns.length; i++) {
    prefetchDiscussionTurn(options, beat.id, turns[i], i, part1Selection);
  }
}

/** Buffer TTS for the beat; resolves when the first spoken line is ready. */
export async function warmBeatPlayback(
  beat: ScriptBeat,
  options: PlaybackAudioOptions,
  part1Selection?: Part1BaerenklauSelection | null
): Promise<void> {
  prefetchPerformanceSentences(options, beat, beat.order);
  if (!audioReady(options)) return;

  const turns = beat.discussion_turns ?? [];
  if (turns.length > 0) {
    prefetchAllDiscussionTurns(options, beat, part1Selection);
    const firstTurn = discussionTextForTurn(turns[0], options, part1Selection);
    const first = resolveDiscussionSpeechBlob(
      options,
      beat.id,
      0,
      firstTurn.spoken,
      turns[0].speaker
    );
    const rest = turns.slice(1).map((turn, index) => {
      const { spoken } = discussionTextForTurn(turn, options, part1Selection);
      return resolveDiscussionSpeechBlob(
        options,
        beat.id,
        index + 1,
        spoken,
        turn.speaker
      );
    });
    await first;
    void Promise.all(rest);
    return;
  }

  const sentences = sentencesForBeat(beat.text);
  if (sentences.length === 0) return;
  await resolvePerformanceSpeechBlob(
    options,
    beat.id,
    0,
    sentences[0],
    beatPerformanceSpeaker(beat, 0),
    false
  ).catch(() => undefined);
}

export type ScriptBufferProgress = {
  loaded: number;
  total: number;
};

/** Buffer all discussion + performance TTS for the full script. */
export async function warmScriptPlayback(
  script: ProductionScript,
  options: PlaybackAudioOptions,
  onProgress?: (progress: ScriptBufferProgress) => void
): Promise<void> {
  const part1Selection = script.part1_selection ?? null;
  if (options.hasRenderedAudio || !audioReady(options)) {
    onProgress?.({ loaded: 0, total: 0 });
    return;
  }

  const tasks: Promise<void>[] = [];
  for (const beat of script.beats) {
    if (!beat.dramaturgy) continue;

    const turns = beat.discussion_turns ?? [];
    for (let i = 0; i < turns.length; i++) {
      const { spoken } = discussionTextForTurn(turns[i], options, part1Selection);
      tasks.push(
        resolveDiscussionSpeechBlob(
          options,
          beat.id,
          i,
          spoken,
          turns[i].speaker
        ).then(() => undefined)
      );
    }

    const sentences = sentencesForBeat(beat.text);
    for (let i = 0; i < sentences.length; i++) {
      tasks.push(
        resolvePerformanceSpeechBlob(
          options,
          beat.id,
          i,
          sentences[i],
          beatPerformanceSpeaker(beat, i),
          false
        ).then(() => undefined)
      );
    }
  }

  const total = tasks.length;
  if (total === 0) {
    onProgress?.({ loaded: 0, total: 0 });
    return;
  }

  let loaded = 0;
  onProgress?.({ loaded, total });

  await Promise.all(
    tasks.map((task) =>
      task
        .catch((err) => {
          console.warn("Script buffer item failed:", err);
        })
        .finally(() => {
          loaded += 1;
          onProgress?.({ loaded, total });
        })
    )
  );
}

function prefetchPerformanceSentences(
  options: PlaybackAudioOptions,
  beat: ScriptBeat,
  beatIndex: number
): void {
  const sentences = sentencesForBeat(beat.text);
  if (sentences.length === 0) return;

  if (options.hasRenderedAudio && options.scriptId) {
    for (let i = 0; i < sentences.length; i++) {
      void prefetchPrerenderedSpeech(
        performanceAudioUrl(options.scriptId, beat.id, "performance", undefined, i)
      ).catch(() => {
        if (i === 0) {
          void prefetchPrerenderedSpeech(
            performanceAudioUrl(options.scriptId!, beat.id, "performance")
          );
        }
      });
    }
    return;
  }

  if (!options.ttsAvailable) return;
  const pool = performanceSpeakerPool(beat);
  for (let i = 0; i < sentences.length; i++) {
    const speaker = speakerForPerformanceSentence(beat.speaker, i, beat.order, pool);
    prefetchSpeech(sentences[i], speaker, { profile: "performance" });
  }
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

async function playDiscussionPhase(
  turns: DiscussionTurn[],
  beat: ScriptBeat,
  beatIndex: number,
  beatCount: number,
  options: PlaybackAudioOptions,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean,
  topic: string,
  part1Selection?: Part1BaerenklauSelection | null
): Promise<boolean> {
  if (turns.length === 0) return true;

  await warmBeatPlayback(beat, options, part1Selection);

  const discussionCueCtx = createDiscussionCueContext(
    async (commands) => {
      await highlightOscSequence(
        commands,
        (cmd, bridge) => onState({ activeOscCommand: cmd, activeOscBridge: bridge, showPhase: "cues_active" }),
        shouldAbort
      );
    },
    shouldAbort
  );

  onState({
    beatIndex,
    sentenceIndex: 0,
    segmentPhase: "discussion",
    showPhase: "dramaturg_discussion",
    performanceSpeaker: undefined,
    activeOscBridge: null,
    activeOscCommand: null,
    paused: false
  });

  for (let turnIndex = 0; turnIndex < turns.length; turnIndex++) {
    if (shouldAbort()) return false;
    if (!(await gatePlayback(shouldAbort))) return false;

    const turn = turns[turnIndex];
    const next = turns[turnIndex + 1];
    if (next) prefetchDiscussionTurn(options, beat.id, next, turnIndex + 1, part1Selection);

    onState({
      discussionTurnIndex: turnIndex,
      dramaturgSpeaker: turn.speaker,
      timelineProgress: progressFromBeat(
        beatIndex,
        beatCount,
        ((turnIndex + 0.1) / Math.max(1, turns.length)) * 0.25
      )
    });

    const { spoken, mentions } = discussionTextForTurn(turn, options, part1Selection);
    const firedMentions = new Set<string>();
    scheduleDiscussionCue(discussionCueCtx, turn, beat.text, topic);

    if (!audioReady(options)) {
      fireDiscussionMentionsAtPosition(
        discussionCueCtx,
        mentions,
        spoken.length,
        firedMentions
      );
      await sleep(DISCUSSION_FALLBACK_MS);
      continue;
    }

    try {
      const blob = await resolveDiscussionSpeechBlob(
        options,
        beat.id,
        turnIndex,
        spoken,
        turn.speaker
      );
      if (shouldAbort()) return false;
      await playBlob(blob, {
        shouldAbort,
        onTimeUpdate: (current, duration) => {
          const textPosition = textPositionForPlayback(current, duration, spoken.length);
          void fireDiscussionMentionsAtPosition(
            discussionCueCtx,
            mentions,
            textPosition,
            firedMentions
          );
        }
      });
      fireDiscussionMentionsAtPosition(
        discussionCueCtx,
        mentions,
        spoken.length,
        firedMentions
      );
    } catch (err) {
      console.warn("Discussion TTS failed:", err);
      if (!shouldAbort()) onState({ showPhase: "blocked" });
      return false;
    }
  }

  return !shouldAbort();
}

async function hasPerSentencePrerender(scriptId: string, beatId: string): Promise<boolean> {
  const url = performanceAudioUrl(scriptId, beatId, "performance", undefined, 0);
  const res = await fetch(url, { method: "HEAD" });
  return res.ok;
}

async function playLegacyPerformanceBlob(
  beat: ScriptBeat,
  beatIndex: number,
  beatCount: number,
  sentences: string[],
  options: PlaybackAudioOptions,
  cueCtx: ReturnType<typeof createCuePlaybackContext>,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean
): Promise<boolean> {
  let lastSentenceIndex = -1;
  const firstSpeaker = beatPerformanceSpeaker(beat, 0);
  onState({ showPhase: "speaking", performanceSpeaker: firstSpeaker });

  try {
    const blob = await resolvePerformanceSpeechBlob(
      options,
      beat.id,
      0,
      beat.text,
      firstSpeaker,
      true
    );
    if (shouldAbort()) return false;

    let cuesStarted = false;
    await playBlob(blob, {
      shouldAbort,
      onPlay: () => {
        if (cuesStarted) return;
        cuesStarted = true;
        onState({ showPhase: "cues_active" });
        void fireStartCues(cueCtx);
      },
      onTimeUpdate: (current, duration) => {
        if (shouldAbort()) return;
        const sentenceIndex = sentenceIndexForProgress(current, duration, sentences.length);
        const speaker = beatPerformanceSpeaker(beat, sentenceIndex);
        onState({ sentenceIndex, performanceSpeaker: speaker });
        void fireTimeCues(cueCtx, current);
        if (sentenceIndex !== lastSentenceIndex) {
          lastSentenceIndex = sentenceIndex;
          void fireSentenceCues(cueCtx, sentenceIndex, sentences[sentenceIndex] ?? "");
        }
      }
    });

    if (!cuesStarted) {
      onState({ showPhase: "cues_active" });
      fireStartCues(cueCtx);
      for (let i = 0; i < sentences.length; i++) {
        fireSentenceCues(cueCtx, i, sentences[i]);
      }
    }
    return !shouldAbort();
  } catch (err) {
    console.warn("Legacy performance TTS failed:", err);
    if (!shouldAbort()) onState({ showPhase: "blocked" });
    return false;
  }
}

async function playPerformancePhase(
  beat: ScriptBeat,
  beatIndex: number,
  beatCount: number,
  options: PlaybackAudioOptions,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean
): Promise<boolean> {
  onState({
    beatIndex,
    sentenceIndex: 0,
    segmentPhase: "performance",
    discussionTurnIndex: undefined,
    dramaturgSpeaker: undefined,
    performanceSpeaker: undefined,
    showPhase: "planned",
    activeOscBridge: null,
    activeOscCommand: null,
    paused: false
  });

  const sentences = sentencesForBeat(beat.text);
  if (sentences.length === 0) return !shouldAbort();

  const cueCtx = createCuePlaybackContext(
    beat.dramaturgy!,
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

  if (!audioReady(options)) {
    onState({ showPhase: "cues_active" });
    fireStartCues(cueCtx);
    for (let i = 0; i < sentences.length; i++) {
      if (shouldAbort()) return false;
      const speaker = beatPerformanceSpeaker(beat, i);
      onState({ sentenceIndex: i, performanceSpeaker: speaker });
      fireSentenceCues(cueCtx, i, sentences[i]);
      await sleep(800);
    }
    onState({ showPhase: "sent" });
    return !shouldAbort();
  }

  if (options.hasRenderedAudio && options.scriptId) {
    const perSentence = await hasPerSentencePrerender(options.scriptId, beat.id);
    if (!perSentence && !options.ttsAvailable) {
      return playLegacyPerformanceBlob(
        beat,
        beatIndex,
        beatCount,
        sentences,
        options,
        cueCtx,
        onState,
        shouldAbort
      );
    }
  }

  onState({ showPhase: "speaking" });
  let cumulativeTime = 0;
  let cuesStarted = false;

  for (let i = 0; i < sentences.length; i++) {
    if (shouldAbort()) return false;
    if (!(await gatePlayback(shouldAbort))) return false;

    const sentence = sentences[i];
    const speaker = beatPerformanceSpeaker(beat, i);
    const segmentFraction = 0.25 + (i + 0.05) / Math.max(1, sentences.length) * 0.75;

    onState({
      sentenceIndex: i,
      performanceSpeaker: speaker,
      timelineProgress: progressFromBeat(beatIndex, beatCount, segmentFraction)
    });

    if (i === 0) {
      onState({ showPhase: "cues_active" });
      fireStartCues(cueCtx);
      cuesStarted = true;
    }
    fireSentenceCues(cueCtx, i, sentence);

    const nextSentence = sentences[i + 1];
    if (nextSentence) {
      const nextSpeaker = beatPerformanceSpeaker(beat, i + 1);
      if (options.ttsAvailable) prefetchSpeech(nextSentence, nextSpeaker, { profile: "performance" });
    }

    try {
      const blob = await resolvePerformanceSpeechBlob(
        options,
        beat.id,
        i,
        sentence,
        speaker,
        false
      );
      if (shouldAbort()) return false;

      let lastDuration = 0;
      const sentenceStart = cumulativeTime;
      await playBlob(blob, {
        shouldAbort,
        onTimeUpdate: (current, duration) => {
          if (Number.isFinite(duration)) lastDuration = duration;
          const audioFraction =
            duration > 0 ? current / duration / Math.max(1, sentences.length) : 0;
          onState({
            timelineProgress: progressFromBeat(
              beatIndex,
              beatCount,
              0.25 + (i + audioFraction) * 0.75
            )
          });
          void fireTimeCues(cueCtx, sentenceStart + current);
        }
      });
      cumulativeTime += Number.isFinite(lastDuration) ? lastDuration : 0;
    } catch (err) {
      console.warn("Performance TTS failed:", err);
      if (!shouldAbort()) onState({ showPhase: "blocked" });
      return false;
    }
  }

  if (cuesStarted && !shouldAbort()) onState({ showPhase: "sent" });
  return !shouldAbort();
}

async function playBeat(
  beat: ScriptBeat,
  beatIndex: number,
  beats: ScriptBeat[],
  options: PlaybackAudioOptions,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean,
  topic: string,
  part1Selection: Part1BaerenklauSelection | null | undefined,
  mode: PlaybackMode
): Promise<boolean> {
  if (!beat.dramaturgy) return true;

  const nextBeat = beats[beatIndex + 1];
  if (nextBeat) {
    prefetchBeatStart(nextBeat, options, beatIndex + 1);
    void warmBeatPlayback(nextBeat, options, part1Selection);
  }

  const turns = beat.discussion_turns ?? [];
  const playDiscussion = mode === "full" || mode === "discussion";
  const playPerformance = mode === "full" || mode === "performance";

  if (playDiscussion && turns.length > 0) {
    const discussionOk = await playDiscussionPhase(
      turns,
      beat,
      beatIndex,
      beats.length,
      options,
      onState,
      shouldAbort,
      topic,
      part1Selection
    );
    if (!discussionOk) return false;

    if (playPerformance) {
      setPlaybackPaused(false);
      await sleep(PERFORMANCE_PREP_PAUSE_MS);
    }
  } else if (playPerformance) {
    prefetchPerformanceSentences(options, beat, beatIndex);
  }

  if (!playPerformance) return true;

  setPlaybackPaused(false);
  return playPerformancePhase(
    beat,
    beatIndex,
    beats.length,
    options,
    onState,
    shouldAbort
  );
}

export function prefetchBeatStart(
  beat: ScriptBeat,
  options: PlaybackAudioOptions,
  beatIndex = beat.order
): void {
  const turns = beat.discussion_turns ?? [];
  if (turns.length > 0) {
    prefetchAllDiscussionTurns(options, beat);
    prefetchPerformanceSentences(options, beat, beatIndex);
    return;
  }
  prefetchPerformanceSentences(options, beat, beatIndex);
}

export async function runPart1ScriptPlayback(
  beats: ScriptBeat[],
  options: PlaybackAudioOptions,
  startBeatIndex: number,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean,
  topic = "Teil 1 — Bärenklau",
  part1Selection?: Part1BaerenklauSelection | null,
  mode: PlaybackMode = "full"
): Promise<void> {
  const part1 = part1Beats(beats);
  return runScriptPlayback(
    part1,
    options,
    startBeatIndex,
    onState,
    shouldAbort,
    topic,
    part1Selection,
    mode
  );
}

export async function runPart1DiscussionPlayback(
  beats: ScriptBeat[],
  options: PlaybackAudioOptions,
  startBeatIndex: number,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean,
  topic = "Teil 1 — Bärenklau",
  part1Selection?: Part1BaerenklauSelection | null
): Promise<void> {
  return runPart1ScriptPlayback(
    beats,
    options,
    startBeatIndex,
    onState,
    shouldAbort,
    topic,
    part1Selection,
    "discussion"
  );
}

export async function runPart1PerformancePlayback(
  beats: ScriptBeat[],
  options: PlaybackAudioOptions,
  startBeatIndex: number,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean,
  topic = "Teil 1 — Bärenklau",
  part1Selection?: Part1BaerenklauSelection | null
): Promise<void> {
  return runPart1ScriptPlayback(
    beats,
    options,
    startBeatIndex,
    onState,
    shouldAbort,
    topic,
    part1Selection,
    "performance"
  );
}

export async function runScriptPlayback(
  beats: ScriptBeat[],
  options: PlaybackAudioOptions,
  startBeatIndex: number,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean,
  topic = "Aufführung",
  part1Selection?: Part1BaerenklauSelection | null,
  mode: PlaybackMode = "full"
): Promise<void> {
  armDirectorForPerformance();
  const start = Math.max(0, Math.min(startBeatIndex, beats.length - 1));
  onState({
    running: true,
    paused: false,
    completed: false,
    beatIndex: start,
    sentenceIndex: 0,
    segmentPhase: undefined,
    discussionTurnIndex: undefined,
    dramaturgSpeaker: undefined,
    performanceSpeaker: undefined,
    activeOscBridge: null,
    activeOscCommand: null,
    playbackMode: mode,
    timelineProgress: progressFromBeat(start, beats.length, 0)
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

    const ok = await playBeat(
      beats[index],
      index,
      beats,
      options,
      onState,
      shouldAbort,
      topic,
      part1Selection,
      mode
    );
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
    segmentPhase: undefined,
    discussionTurnIndex: undefined,
    dramaturgSpeaker: undefined,
    performanceSpeaker: undefined,
    activeOscBridge: null,
    activeOscCommand: null,
    showPhase: undefined,
    timelineProgress: 1
  });
}

export function stopScriptPlayback() {
  stopPlayback();
  stopDirectorPerformance();
}
