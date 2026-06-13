import type { MediaLookup } from "@/lib/types/media";
import type { ScriptBeat } from "@/lib/types/script";
import { speakerLabel } from "@/lib/types/script";

export function StagePreview({
  beats,
  activeBeatIndex = -1,
  activeOscBridge = null,
  running = false,
  paused = false,
  onBeatSelect,
  media
}: {
  beats: ScriptBeat[];
  activeBeatIndex?: number;
  activeOscBridge?: string | null;
  running?: boolean;
  paused?: boolean;
  onBeatSelect?: (index: number) => void;
  media?: MediaLookup;
}) {
  const activeVideo =
    activeBeatIndex >= 0 ? beats[activeBeatIndex]?.dramaturgy?.visual?.clip_id : undefined;
  const activeVideoPath = activeVideo ? media?.videoById[activeVideo]?.path : undefined;

  return (
    <div className="stagePreview">
      <div className="stageCanvas" aria-label="Abstrakte Bühnenansicht">
        <div className={`stageZone stageZoneScreen${activeOscBridge === "visual" ? " stageZoneActive" : ""}`}>
          <span>Beamer / Video</span>
          {activeVideo ? (
            <small className="stageZoneDetail">
              {activeVideo}
              {activeVideoPath ? ` → ${activeVideoPath}` : ""}
            </small>
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
            Vorschau — Timeline oder Textabschnitt wählen, dann starten. Videos aus{" "}
            <code>data/media.json</code> → TouchDesigner per OSC.
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
          const d = beat.dramaturgy;
          const videoPath = d?.visual?.clip_id ? media?.videoById[d.visual.clip_id]?.path : undefined;
          const rowClass = `stageTimelineRow${active ? " stageTimelineRowActive" : ""}${onBeatSelect ? " stageTimelineRowClickable" : ""}`;
          const title = videoPath ? `${d?.visual?.clip_id}: ${videoPath}` : beat.text.slice(0, 80);
          const cells = (
            <>
              <span className="stageTimelineCell">{index + 1}</span>
              <span className="stageTimelineCell">{speakerLabel(beat.speaker)}</span>
              <span className="stageTimelineCell">{d?.visual?.clip_id ?? "—"}</span>
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
