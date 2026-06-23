import { postDirectorExecuteLayered } from "@/lib/api/director";
import type { CompositionMoment, CompositionPlan, SceneCorpus } from "@/lib/types/inszenierung";
import { waitWhilePlaybackPaused } from "@/lib/api/client";
import {
  activeLayeredVoiceCount,
  playBlobLayered,
  stopAllLayeredAudio,
  waitForVoiceSlot
} from "@/features/inszenierung/audioLayerManager";
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

export function computeMomentDelayMs(moment: CompositionMoment, index: number): number {
  const overlap = index > 0 ? moment.overlap_with_previous : 0;
  return Math.max(0, moment.start_delay_ms - Math.round(overlap * 1200));
}

export function stopAnarchyPlayback(): void {
  stopAllLayeredAudio();
}

export async function runAnarchyPlayback(
  corpus: SceneCorpus,
  plan: CompositionPlan,
  ttsAvailable: boolean,
  onUpdate: (patch: Partial<AnarchyPlaybackState>) => void,
  shouldAbort: () => boolean
): Promise<void> {
  const moments = [...plan.moments].sort((a, b) => a.order - b.order);
  const maxVoices = plan.max_concurrent_voices ?? 3;

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
      await sleep(delay);
      if (shouldAbort()) break;
    }

    if (moment.dramaturgy) {
      void fireLayeredMomentCues(
        moment.dramaturgy,
        moment.anarchy_level,
        moment.text_excerpt,
        async (commands) => {
          const bridge = commands[0]?.bridge ?? null;
          onUpdate({ activeOscBridge: bridge });
          await sleep(150);
          onUpdate({ activeOscBridge: null });
        },
        shouldAbort
      );
    }

    const speechMode = moment.speech_mode ?? "tts";

    if (speechMode === "avatar_video") {
      const waitMs = moment.duration_hint_ms ?? 8000;
      await sleep(waitMs);
      continue;
    }

    if (speechMode === "silent") {
      const waitMs = moment.duration_hint_ms ?? 4000;
      await sleep(waitMs);
      continue;
    }

    if (!ttsAvailable) continue;

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
          visual: { clip_id: "black", blend_mode: "replace" },
          light: { scene_id: "blackout", replace_previous: true },
          intensity: 1
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
