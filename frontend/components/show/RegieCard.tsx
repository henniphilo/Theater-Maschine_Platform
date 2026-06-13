import type { DirectorPayload, OscCommand, ShowPhase } from "@/lib/types/director";
import { formatOscCommand } from "@/lib/types/director";

const PHASE_LABELS: Record<ShowPhase, string> = {
  planned: "Regie geplant",
  speaking: "Stimme läuft …",
  cues_active: "Cues werden gesendet …",
  sent: "Cues gesendet",
  blocked: "Cues blockiert"
};

function cueSummary(director: DirectorPayload): string[] {
  const lines: string[] = [];
  const d = director.decision;
  if (d.visual?.clip_id) lines.push(`Video: ${d.visual.clip_id}`);
  if (d.sound?.cue_id) lines.push(`Sound: ${d.sound.cue_id}`);
  if (d.light?.scene_id) lines.push(`Licht: ${d.light.scene_id}`);
  return lines;
}

export function RegieCard({
  director,
  showPhase,
  oscCommands,
  activeOscBridge
}: {
  director: DirectorPayload;
  showPhase?: ShowPhase;
  oscCommands?: OscCommand[];
  activeOscBridge?: string | null;
}) {
  const phase = showPhase ?? (director.executed ? "sent" : "planned");
  const planned = director.planned_commands ?? [];
  const sent = oscCommands ?? director.osc_commands ?? [];
  const displayCommands = sent.length > 0 ? sent : planned;

  return (
    <div className="regieCard">
      <div className="regieCardHeader">
        <strong>Live-Regie</strong>
        <span className={`regiePhase regiePhase-${phase}`}>{PHASE_LABELS[phase]}</span>
      </div>
      <p className="regieMeta">
        Stimmung: {director.decision.mood} · Intensität: {director.decision.intensity.toFixed(2)}
        {director.decision.tags.length ? ` · Tags: ${director.decision.tags.join(", ")}` : ""}
      </p>
      {director.decision.reason ? <p className="regieReason">{director.decision.reason}</p> : null}
      {cueSummary(director).length > 0 ? (
        <ul className="regieCueList">
          {cueSummary(director).map((line) => {
            const bridge =
              line.startsWith("Video:")
                ? "visual"
                : line.startsWith("Sound:")
                  ? "sound"
                  : line.startsWith("Licht:")
                    ? "light"
                    : "";
            const active = activeOscBridge && bridge === activeOscBridge;
            return (
              <li key={line} className={active ? "regieCueActive" : undefined}>
                {line}
                {active ? " ▶" : ""}
              </li>
            );
          })}
        </ul>
      ) : null}
      {director.blocked_reason && phase === "blocked" ? (
        <p className="textError">Blockiert: {director.blocked_reason}</p>
      ) : null}
      {displayCommands.length > 0 ? (
        <div className="regieOscBlock">
          <strong>OSC {sent.length > 0 ? "gesendet" : "geplant"}</strong>
          <ul className="regieOscList">
            {displayCommands.map((cmd, i) => (
              <li key={`${cmd.address}-${i}`}>
                <code>{formatOscCommand(cmd)}</code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
