import type { CompositionMoment, CompositionPlan } from "@/lib/types/inszenierung";
import type { DramaturgyDecision, OscCommand } from "@/lib/types/director";
import type { VisualCue } from "@/lib/types/visual";
import { isDirectorPerformanceAborted, postDirectorExecuteLayered } from "@/lib/api/director";

export async function executeAvatarVisualCue(
  visual: VisualCue,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  textExcerpt?: string
): Promise<boolean> {
  if (shouldAbort() || isDirectorPerformanceAborted()) return false;
  const decision: DramaturgyDecision = {
    reason: "Avatar-Sprache",
    tags: ["teil2", "avatar"],
    mood: "tension",
    intensity: anarchyLevel,
    visual
  };
  try {
    const result = await postDirectorExecuteLayered(decision, {
      anarchy_level: anarchyLevel,
      stack: true,
      skip_interval_check: true,
      stagger: false,
      text_excerpt: textExcerpt
    });
    if (shouldAbort() || isDirectorPerformanceAborted()) return false;
    if (result.osc_commands.length > 0) {
      void onCommands(result.osc_commands).catch((err) => {
        console.warn("Avatar cue highlight failed (playback continues):", err);
      });
    }
    return result.executed;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return false;
    console.warn("Avatar cue failed (playback continues):", err);
    return false;
  }
}

export function avatarVisualCuesForMoment(moment: CompositionMoment): VisualCue[] {
  const fromLayers = (moment.avatar_layers ?? [])
    .map((layer) => layer.visual_cue)
    .filter((cue): cue is VisualCue => Boolean(cue));
  if (fromLayers.length > 0) return fromLayers;
  if (moment.avatar_video_cue) return [moment.avatar_video_cue];
  return [];
}

export async function fireAvatarMomentCues(
  moment: CompositionMoment,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): Promise<void> {
  for (const visual of avatarVisualCuesForMoment(moment)) {
    if (shouldAbort()) return;
    await executeAvatarVisualCue(visual, anarchyLevel, onCommands, shouldAbort, moment.text_excerpt);
  }
}

export function momentNeedsAvatarVisualRefresh(moment: CompositionMoment): boolean {
  if ((moment.speech_mode ?? "tts") !== "avatar_video") return false;
  if (!moment.avatar_layers?.length && !moment.avatar_speech_id && !moment.avatar_video_clip_id) {
    return false;
  }
  return avatarVisualCuesForMoment(moment).length === 0;
}

export function planNeedsAvatarVisualRefresh(plan: CompositionPlan): boolean {
  return plan.moments.some((moment) => momentNeedsAvatarVisualRefresh(moment));
}

export function planRequiresTts(plan: CompositionPlan): boolean {
  return plan.moments.some((moment) => (moment.speech_mode ?? "tts") === "tts");
}
