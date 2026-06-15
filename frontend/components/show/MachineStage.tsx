import type { DirectorPayload, OscCommand, ShowPhase } from "@/lib/types/director";
import { formatOscCommand } from "@/lib/types/director";
import type { DebateSpeaker } from "@/lib/types/chat";
import type { DramaturgSpeaker, ScriptSpeaker } from "@/lib/types/script";
import { dramaturgSpeakerLabel, speakerLabel } from "@/lib/types/script";
import { formatVisualCueLabel } from "@/lib/types/visual";

function speakerName(speaker: DebateSpeaker | "narrator") {
  if (speaker === "openai") return "GPT";
  if (speaker === "anthropic") return "Claude";
  return "Erzähler";
}

function cueChips(director: DirectorPayload | undefined) {
  if (!director) return [];
  const d = director.decision;
  const chips: { id: string; label: string; bridge: string }[] = [];
  if (d.visual) {
    const label = formatVisualCueLabel(d.visual);
    if (label) chips.push({ id: "visual", label: `Video: ${label}`, bridge: "visual" });
  }
  if (d.sound?.cue_id) chips.push({ id: "sound", label: `Sound: ${d.sound.cue_id}`, bridge: "sound" });
  if (d.light?.scene_id) chips.push({ id: "light", label: `Licht: ${d.light.scene_id}`, bridge: "light" });
  return chips;
}

export function MachineStage({
  running,
  beatIndex,
  beatTotal,
  speaker,
  dramaturgSpeaker,
  performanceSpeaker,
  segmentPhase,
  discussionTurnIndex,
  discussionText,
  director,
  showPhase,
  activeOscBridge,
  activeOscCommand,
  onStop
}: {
  running: boolean;
  beatIndex: number;
  beatTotal: number;
  speaker?: DebateSpeaker | "narrator";
  dramaturgSpeaker?: DramaturgSpeaker;
  performanceSpeaker?: ScriptSpeaker;
  segmentPhase?: "discussion" | "performance";
  discussionTurnIndex?: number;
  discussionText?: string;
  director?: DirectorPayload;
  showPhase?: ShowPhase;
  activeOscBridge?: string | null;
  activeOscCommand?: OscCommand | null;
  onStop: () => void;
}) {
  if (!running) return null;

  const progress = beatTotal > 0 ? ((beatIndex + 1) / beatTotal) * 100 : 0;
  const inPerformance = segmentPhase !== "discussion";
  const chips = inPerformance ? cueChips(director) : [];
  const phaseLabel =
    showPhase === "dramaturg_discussion"
      ? "Dramaturgen"
      : showPhase === "speaking"
        ? "Stimme"
        : showPhase === "cues_active"
          ? "Cues aktiv"
          : showPhase === "sent"
            ? "Cues gesendet"
            : showPhase === "blocked"
              ? "Blockiert"
              : "Bereit";

  const speakerLine =
    showPhase === "dramaturg_discussion" && dramaturgSpeaker
      ? dramaturgSpeakerLabel(dramaturgSpeaker)
      : inPerformance && performanceSpeaker
        ? speakerLabel(performanceSpeaker)
        : speaker
          ? speakerName(speaker)
          : "";

  return (
    <section className="machineStage card col" aria-label="Maschinen-Steuerung">
      <div className="machineStageHeader">
        <div>
          <strong>Maschine läuft</strong>
          <span className="machinePhaseBadge">{phaseLabel}</span>
        </div>
        <button type="button" className="machineStopBtn" onClick={onStop}>
          Stoppen
        </button>
      </div>

      <div className="machineProgressRow">
        <span className="textMuted">
          Beitrag {Math.min(beatIndex + 1, beatTotal)} / {beatTotal}
          {speakerLine ? ` · ${speakerLine}` : ""}
          {inPerformance && director ? ` · ${director.decision.mood}` : ""}
          {showPhase === "dramaturg_discussion" && discussionTurnIndex !== undefined
            ? ` · Turn ${discussionTurnIndex + 1}`
            : ""}
        </span>
        <div className="machineProgressTrack" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
          <div className="machineProgressFill" style={{ width: `${progress}%` }} />
        </div>
      </div>

      {showPhase === "dramaturg_discussion" && discussionText ? (
        <p className="textMuted" style={{ fontSize: "0.9rem", margin: 0 }}>
          {discussionText.length > 160 ? `${discussionText.slice(0, 160)}…` : discussionText}
        </p>
      ) : null}

      {chips.length > 0 ? (
        <div className="machineCueRow">
          <span className="machineCueLabel">Cues:</span>
          {chips.map((chip) => (
            <span
              key={chip.id}
              className={`machineCueChip${activeOscBridge === chip.bridge ? " machineCueChipActive" : ""}${
                showPhase === "sent" ? " machineCueChipDone" : ""
              }`}
            >
              {chip.label}
            </span>
          ))}
        </div>
      ) : null}

      {activeOscCommand ? (
        <p className="machineOscLive">
          <strong>Aktuell:</strong> <code>{formatOscCommand(activeOscCommand)}</code>
        </p>
      ) : null}
    </section>
  );
}
