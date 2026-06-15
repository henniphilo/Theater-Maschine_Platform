import type { MediaLookup } from "@/lib/types/media";
import { formatMidiTrigger } from "@/lib/midi/format";
import type { CuePoint, DramaturgyDecision } from "@/lib/types/director";
import { formatVisualCueLabel } from "@/lib/types/visual";
import { normalizeCuePoints } from "@/features/show/cuePlayback";

function VisualChips({ visual }: { visual: CuePoint["visual"] }) {
  if (!visual) return null;
  const label = formatVisualCueLabel(visual);
  if (!label) return null;
  if (visual.outputs?.length) {
    return (
      <>
        {visual.outputs.map((item) => (
          <span key={item.output_id} className="scriptCueChip scriptCueVideo">
            {item.output_id.toUpperCase()} {item.clip_id || visual.clip_id || "—"}
          </span>
        ))}
      </>
    );
  }
  return <span className="scriptCueChip scriptCueVideo">VIDEO {label}</span>;
}

function CuePointRow({ point, media }: { point: CuePoint; media?: MediaLookup }) {
  const videoId = point.visual?.clip_id;
  const soundId = point.sound?.cue_id;
  const lightId = point.light?.scene_id;
  const video = videoId ? media?.videoById[videoId] : undefined;
  const sound = soundId ? media?.soundById[soundId] : undefined;
  const light = lightId ? media?.lightById[lightId] : undefined;

  return (
    <li className="cuePointItem">
      <strong>
        {point.trigger}
        {point.keyword ? ` · „${point.keyword}"` : ""}
        {point.function ? ` · ${point.function}` : ""}
      </strong>
      <div className="scriptCueRow">
        <VisualChips visual={point.visual} />
        {point.visual?.action === "stop_clip" || point.visual?.action === "fade_to_black" ? (
          <span className="scriptCueChip scriptCueVideo">VIDEO aus</span>
        ) : null}
        {soundId ? <span className="scriptCueChip scriptCueSound">SOUND {soundId}</span> : null}
        {point.sound?.action === "stop_cue" ? (
          <span className="scriptCueChip scriptCueSound">SOUND aus</span>
        ) : null}
        {lightId ? <span className="scriptCueChip scriptCueLight">LICHT {lightId}</span> : null}
        {point.light?.action === "fade_blackout" ? (
          <span className="scriptCueChip scriptCueLight">LICHT blackout</span>
        ) : null}
      </div>
      {!video && !sound && !light ? null : (
        <span className="textMuted" style={{ fontSize: "0.85rem" }}>
          {video ? video.path : ""}
          {sound
            ? sound.midi_note != null
              ? ` · MIDI ${formatMidiTrigger(sound.midi_note, sound.channel ?? 1)}`
              : sound.label
                ? ` · ${sound.label}`
                : ""
            : ""}
          {light ? ` · ${light.description || light.id}` : ""}
        </span>
      )}
    </li>
  );
}

export function MediaCueDetail({
  dramaturgy,
  media,
  compact = false
}: {
  dramaturgy: DramaturgyDecision;
  media?: MediaLookup;
  compact?: boolean;
}) {
  const cuePoints = normalizeCuePoints(dramaturgy);
  const video = dramaturgy.visual?.clip_id ? media?.videoById[dramaturgy.visual.clip_id] : undefined;
  const sound = dramaturgy.sound?.cue_id ? media?.soundById[dramaturgy.sound.cue_id] : undefined;
  const lightScene = dramaturgy.light?.scene_id ? media?.lightById[dramaturgy.light.scene_id] : undefined;

  return (
    <div className={`mediaCueDetail${compact ? " mediaCueDetailCompact" : ""}`}>
      {dramaturgy.dramaturgical_reading ? (
        <p className="textMuted" style={{ fontSize: "0.9rem" }}>
          Lesart: {dramaturgy.dramaturgical_reading}
        </p>
      ) : null}
      {cuePoints.length > 1 ? (
        <ul className="mediaFileList">
          {cuePoints.map((point, index) => (
            <CuePointRow key={`${point.trigger}-${index}`} point={point} media={media} />
          ))}
        </ul>
      ) : (
        <>
          <div className="scriptCueRow">
            <VisualChips visual={dramaturgy.visual} />
            {dramaturgy.sound?.cue_id ? (
              <span className="scriptCueChip scriptCueSound">SOUND {dramaturgy.sound.cue_id}</span>
            ) : null}
            {dramaturgy.light?.scene_id ? (
              <span className="scriptCueChip scriptCueLight">LICHT {dramaturgy.light.scene_id}</span>
            ) : null}
          </div>
          {!compact ? (
            <ul className="mediaFileList">
              {video ? (
                <li>
                  <strong>Video-Datei:</strong> <code>{video.path}</code>
                  <br />
                  <code>/pixera/args/cue/apply {formatVisualCueLabel(dramaturgy.visual)}</code>
                </li>
              ) : null}
              {sound ? (
                <li>
                  <strong>Sound:</strong> {sound.soundname || sound.label || sound.id}
                  {sound.action && sound.action !== "play" ? ` (${sound.action})` : ""}
                  {sound.midi_note != null ? (
                    <>
                      {" "}
                      · <code>{formatMidiTrigger(sound.midi_note, sound.channel ?? 1)}</code>
                    </>
                  ) : null}
                  {sound.description ? (
                    <>
                      <br />
                      {sound.description}
                    </>
                  ) : null}
                  {sound.ableton_hint ? (
                    <>
                      <br />
                      <span className="textMuted">Ableton: {sound.ableton_hint}</span>
                    </>
                  ) : null}
                </li>
              ) : null}
              {lightScene ? (
                <li>
                  <strong>Licht:</strong> {lightScene.description || lightScene.id}
                </li>
              ) : null}
            </ul>
          ) : null}
        </>
      )}
    </div>
  );
}
