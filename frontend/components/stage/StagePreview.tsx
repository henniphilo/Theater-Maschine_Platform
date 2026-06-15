import { formatVisualCueLabel } from "@/lib/types/visual";
import type { MediaLookup } from "@/lib/types/media";
import type { ScriptBeat } from "@/lib/types/script";
import { speakerLabel } from "@/lib/types/script";

export function StagePreview({
  beats,
  activeBeatIndex = -1,
  activeOscBridge = null,
  segmentPhase,
  running = false,
  paused = false,
  onBeatSelect,
  media
}: {
  beats: ScriptBeat[];
  activeBeatIndex?: number;
  activeOscBridge?: string | null;
  segmentPhase?: "discussion" | "performance";
  running?: boolean;
  paused?: boolean;
  onBeatSelect?: (index: number) => void;
  media?: MediaLookup;
}) {
  const activeVisual =
    activeBeatIndex >= 0 ? beats[activeBeatIndex]?.dramaturgy?.visual : undefined;
  const activeVideoLabel = formatVisualCueLabel(activeVisual);

  return (
    <div className="stagePreview">
      <div className="stageCanvas" aria-label="Abstrakte Bühnenansicht">
        <div className={`stageZone stageZoneScreen${activeOscBridge === "visual" ? " stageZoneActive" : ""}`}>
          <span>Beamer / Video</span>
          {activeVideoLabel ? (
            <small className="stageZoneDetail">{activeVideoLabel}</small>
          ) : null}
        </div>
        <div className="stageZoneRow">
          <div className={`stageZone stageZoneSound${activeOscBridge === "sound" ? " stageZoneActive" : ""}`}>
            <span>Sound</span>
          </div>
          <div className={`stageZone stageZoneLight${activeOscBridge === "light" ? " stageZoneActive" : ""}`}>
            <span>Licht</span>
          </div>
        </div>
        {!running && !paused ? (
          <p className="textFaint stageCanvasHint">
            Vorschau — Timeline oder Textabschnitt wählen, dann starten. Video per Pixera OSC (
            <code>/pixera/args/cue/apply</code>).
          </p>
        ) : paused ? (
          <p className="textFaint stageCanvasHint">Pausiert — Fortsetzen oder anderen Abschnitt wählen.</p>
        ) : null}
      </div>

      <div className="stageTimeline" aria-label="Ablauf-Timeline">
        <div className="stageTimelineHeader">
          <span>#</span>
          <span>Sprecher</span>
          <span>Video</span>
          <span>Sound</span>
          <span>Licht</span>
        </div>
        {beats.map((beat, index) => {
          const active = index === activeBeatIndex;
          const phaseMarker =
            active && running
              ? segmentPhase === "discussion"
                ? "D"
                : segmentPhase === "performance"
                  ? "▶"
                  : ""
              : beat.discussion_turns?.length
                ? "D"
                : "";
          const d = beat.dramaturgy;
          const rowClass = `stageTimelineRow${active ? " stageTimelineRowActive" : ""}${onBeatSelect ? " stageTimelineRowClickable" : ""}`;
          const title = formatVisualCueLabel(d?.visual) || beat.text.slice(0, 80);
          const cells = (
            <>
              <span className="stageTimelineCell">
                {phaseMarker ? `${phaseMarker} ` : ""}
                {index + 1}
              </span>
              <span className="stageTimelineCell">{speakerLabel(beat.speaker)}</span>
              <span className="stageTimelineCell">{formatVisualCueLabel(d?.visual) || "—"}</span>
              <span className="stageTimelineCell">{d?.sound?.cue_id ?? "—"}</span>
              <span className="stageTimelineCell">{d?.light?.scene_id ?? "—"}</span>
            </>
          );
          if (onBeatSelect) {
            return (
              <button
                key={beat.id}
                type="button"
                className={rowClass}
                onClick={() => onBeatSelect(index)}
                title={title}
              >
                {cells}
              </button>
            );
          }
          return (
            <div key={beat.id} className={rowClass} title={title}>
              {cells}
            </div>
          );
        })}
      </div>
    </div>
  );
}
