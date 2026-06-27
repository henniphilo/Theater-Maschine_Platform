import type { DramaturgyDecision, OscCommand } from "@/lib/types/director";
import { isDirectorPerformanceAborted, postDirectorExecuteLayered } from "@/lib/api/director";
import { decisionFromCuePoint, normalizeCuePoints } from "@/features/show/cuePlayback";

export async function executeLayeredCueSafely(
  decision: DramaturgyDecision,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): Promise<boolean> {
  if (shouldAbort() || isDirectorPerformanceAborted()) return false;
  try {
    const result = await postDirectorExecuteLayered(decision, {
      anarchy_level: anarchyLevel,
      stack: true,
      skip_interval_check: true,
      stagger: false
    });
    if (shouldAbort() || isDirectorPerformanceAborted()) return false;
    if (result.osc_commands.length > 0) {
      void onCommands(result.osc_commands).catch((err) => {
        console.warn("Layered cue highlight failed (playback continues):", err);
      });
    }
    return result.executed;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return false;
    console.warn("Layered cue failed (playback continues):", err);
    return false;
  }
}

export function fireLayeredMomentCues(
  dramaturgy: DramaturgyDecision,
  anarchyLevel: number,
  excerpt: string,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): void {
  const points = normalizeCuePoints(dramaturgy);
  if (points.length === 0) return;

  const startPoints = points.filter((p) => p.trigger === "start");
  const targets = startPoints.length > 0 ? startPoints : [points[0]];

  for (const point of targets) {
    if (shouldAbort()) return;
    const decision = decisionFromCuePoint(dramaturgy, point);
    void executeLayeredCueSafely(decision, anarchyLevel, onCommands, shouldAbort);
  }
}
