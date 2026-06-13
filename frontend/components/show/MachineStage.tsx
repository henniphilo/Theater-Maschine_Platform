import type { DirectorPayload, OscCommand } from "@/lib/types/director";
import { formatOscCommand } from "@/lib/types/director";
import type { DebateSpeaker } from "@/lib/types/chat";

function speakerName(speaker: DebateSpeaker | "narrator") {
  if (speaker === "openai") return "GPT";
  if (speaker === "anthropic") return "Claude";
  return "Erzähler";
}

function cueChips(director: DirectorPayload | undefined) {
  if (!director) return [];
  const d = director.decision;
  const chips: { id: string; label: string; bridge: string }[] = [];
  if (d.visual?.clip_id) chips.push({ id: "visual", label: `Video: ${d.visual.clip_id}`, bridge: "visual" });
  if (d.sound?.cue_id) chips.push({ id: "sound", label: `Sound: ${d.sound.cue_id}`, bridge: "sound" });
  if (d.light?.scene_id) chips.push({ id: "light", label: `Licht: ${d.light.scene_id}`, bridge: "light" });
  return chips;
}

export function MachineStage({
  running,
  beatIndex,
  beatTotal,
  speaker,
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
  director?: DirectorPayload;
  showPhase?: string;
  activeOscBridge?: string | null;
  activeOscCommand?: OscCommand | null;
  onStop: () => void;
}) {
  if (!running) return null;

  const progress = beatTotal > 0 ? ((beatIndex + 1) / beatTotal) * 100 : 0;
  const chips = cueChips(director);
  const phaseLabel =
    showPhase === "speaking"
      ? "Stimme"
      : showPhase === "cues_active"
        ? "Cues aktiv"
        : showPhase === "sent"
          ? "Cues gesendet"
          : showPhase === "blocked"
            ? "Blockiert"
            : "Bereit";

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
          {speaker ? ` · ${speakerName(speaker)}` : ""}
          {director ? ` · ${director.decision.mood}` : ""}
        </span>
        <div className="machineProgressTrack" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
          <div className="machineProgressFill" style={{ width: `${progress}%` }} />
        </div>
      </div>

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
