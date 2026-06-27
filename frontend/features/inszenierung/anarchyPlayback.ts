import { armDirectorForPerformance, postDirectorExecuteLayered, stopDirectorPerformance } from "@/lib/api/director";
import type { CompositionMoment, CompositionPlan, SceneCorpus } from "@/lib/types/inszenierung";
import { waitWhilePlaybackPaused } from "@/lib/api/client";
import {
  activeLayeredVoiceCount,
  playBlobLayered,
  stopAllLayeredAudio,
  waitForVoiceSlot
} from "@/features/inszenierung/audioLayerManager";
import { fireAvatarMomentCues, planRequiresTts } from "@/features/inszenierung/avatarCuePlayback";
import { fireLayeredMomentCues } from "@/features/inszenierung/layeredCuePlayback";
import { resolveMomentSpeech } from "@/features/inszenierung/inszenierungBuffer";

export type AnarchyPlaybackState = {
  running: boolean;
  paused: boolean;
  momentIndex: number;
  anarchyLevel: number;
  activeVoices: number;
  completed: boolean;
  activeOscBridge: string | null;
};

export const INITIAL_ANARCHY_STATE: AnarchyPlaybackState = {
  running: false,
  paused: false,
  momentIndex: -1,
  anarchyLevel: 0,
  activeVoices: 0,
  completed: false,
  activeOscBridge: null
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function sleepAbortable(ms: number, shouldAbort: () => boolean): Promise<void> {
  const step = 100;
  let remaining = ms;
  while (remaining > 0 && !shouldAbort()) {
    await sleep(Math.min(step, remaining));
    remaining -= step;
  }
}

export function computeMomentDelayMs(moment: CompositionMoment, index: number): number {
  if (moment.speech_mode === "avatar_video") {
    return Math.max(0, moment.start_delay_ms);
  }
  const overlap = index > 0 ? moment.overlap_with_previous : 0;
  return Math.max(0, moment.start_delay_ms - Math.round(overlap * 1200));
}

export function avatarBeatHoldMs(moment: CompositionMoment): number {
  if (moment.duration_hint_ms != null && moment.duration_hint_ms > 0) {
    return moment.duration_hint_ms;
  }
  const fromLayers = (moment.avatar_layers ?? [])
    .map((layer) => layer.visual_cue?.duration_ms)
    .filter((duration): duration is number => duration != null && duration > 0);
  if (fromLayers.length > 0) {
    return Math.max(...fromLayers);
  }
  return 8000;
}

export function stopAnarchyPlayback(): void {
  stopAllLayeredAudio();
  stopDirectorPerformance();
}

export async function runAnarchyPlayback(
  corpus: SceneCorpus,
  plan: CompositionPlan,
  ttsAvailable: boolean,
  onUpdate: (patch: Partial<AnarchyPlaybackState>) => void,
  shouldAbort: () => boolean
): Promise<void> {
  armDirectorForPerformance();
  const moments = [...plan.moments].sort((a, b) => a.order - b.order);
  const maxVoices = plan.max_concurrent_voices ?? 3;
  const needsTts = planRequiresTts(plan);

  for (let index = 0; index < moments.length; index++) {
    if (shouldAbort()) break;
    if (!(await waitWhilePlaybackPaused(shouldAbort))) break;

    const moment = moments[index];
    const delay = computeMomentDelayMs(moment, index);

    onUpdate({
      momentIndex: index,
      anarchyLevel: moment.anarchy_level,
      activeVoices: activeLayeredVoiceCount()
    });

    if (delay > 0) {
      await sleepAbortable(delay, shouldAbort);
      if (shouldAbort()) break;
    }

    const speechMode = moment.speech_mode ?? "tts";
    const onCommands = async (commands: { bridge?: string }[]) => {
      const bridge = commands[0]?.bridge ?? null;
      onUpdate({ activeOscBridge: bridge });
      await sleep(150);
      onUpdate({ activeOscBridge: null });
    };

    if (speechMode === "avatar_video") {
      await fireAvatarMomentCues(moment, moment.anarchy_level, onCommands, shouldAbort);
      if (shouldAbort()) break;
    }
    if (moment.dramaturgy) {
      fireLayeredMomentCues(
        moment.dramaturgy,
        moment.anarchy_level,
        moment.text_excerpt,
        onCommands,
        shouldAbort
      );
    }

    if (speechMode === "avatar_video") {
      const waitMs = avatarBeatHoldMs(moment);
      await sleepAbortable(waitMs, shouldAbort);
      continue;
    }

    if (speechMode === "silent") {
      const waitMs = moment.duration_hint_ms ?? 4000;
      await sleepAbortable(waitMs, shouldAbort);
      continue;
    }

    if (!ttsAvailable || !needsTts) continue;

    await waitForVoiceSlot(maxVoices, shouldAbort);
    if (shouldAbort()) break;

    const overlap = index > 0 ? moment.overlap_with_previous : 0;
    const volume = Math.min(1, 0.55 + moment.anarchy_level * 0.45);
    const blob = await resolveMomentSpeech(corpus.id, moment);
    const speechPromise = playBlobLayered(blob, volume, shouldAbort);

    onUpdate({ activeVoices: activeLayeredVoiceCount() });

    if (overlap < 0.35) {
      await speechPromise.catch(() => undefined);
    } else {
      void speechPromise.catch(() => undefined);
      await sleep(Math.max(400, 1800 - Math.round(overlap * 1400)));
    }
  }

  while (activeLayeredVoiceCount() > 0 && !shouldAbort()) {
    onUpdate({ activeVoices: activeLayeredVoiceCount() });
    await sleep(120);
  }

  if (!shouldAbort()) {
    try {
      await postDirectorExecuteLayered(
        {
          reason: "Teil 2 Kollaps",
          visual: { action: "play_clip", clip_id: "black" },
          light: { action: "set_scene", scene_id: "blackout", replace_previous: true },
          tags: ["teil2", "kollaps"],
          mood: "collapse",
          intensity: 1,
          timestamp: Date.now()
        },
        { anarchy_level: 1, stack: false, skip_interval_check: true, stagger: false }
      );
    } catch {
      // playback continues even if collapse cues fail
    }
    await sleep(1200);
  }

  onUpdate({
    running: false,
    completed: !shouldAbort(),
    momentIndex: moments.length - 1,
    activeVoices: 0,
    activeOscBridge: null
  });
}
