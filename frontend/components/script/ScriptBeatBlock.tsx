import { MediaCueDetail } from "@/components/script/MediaCueDetail";
import type { MediaLookup } from "@/lib/types/media";
import type { ScriptBeat, ScriptSpeaker } from "@/lib/types/script";
import { speakerLabel } from "@/lib/types/script";

export function ScriptBeatBlock({
  beat,
  editable = false,
  onSpeakerChange,
  highlight = false,
  sentenceIndex,
  clickable = false,
  onSelect,
  media
}: {
  beat: ScriptBeat;
  editable?: boolean;
  onSpeakerChange?: (speaker: ScriptSpeaker) => void;
  highlight?: boolean;
  sentenceIndex?: number;
  clickable?: boolean;
  onSelect?: () => void;
  media?: MediaLookup;
}) {
  const d = beat.dramaturgy;
  const mood = d?.mood ?? "—";

  const content = (
    <>
      <header className="scriptBeatHeader">
        <span className="scriptBeatMeta">
          [{editable ? (
            <select
              value={beat.speaker}
              onChange={(e) => onSpeakerChange?.(e.target.value as ScriptSpeaker)}
              aria-label="Sprecher"
              onClick={(e) => e.stopPropagation()}
            >
              <option value="AI_A">Stimme A</option>
              <option value="AI_B">Stimme B</option>
              <option value="narrator">Erzähler</option>
            </select>
          ) : (
            speakerLabel(beat.speaker)
          )}
          {" · "}
          {mood}]
        </span>
      </header>
      <blockquote className="scriptBeatText">{beat.text}</blockquote>
      {d ? (
        <>
          <MediaCueDetail dramaturgy={d} media={media} />
          {d.reason ? <p className="scriptBeatReason">Begründung: {d.reason}</p> : null}
        </>
      ) : (
        <p className="textFaint">Noch keine Regieentscheidung.</p>
      )}
      {highlight && sentenceIndex !== undefined ? (
        <p className="textMuted" style={{ fontSize: "0.85rem" }}>
          Satz {sentenceIndex + 1} wird gesprochen …
        </p>
      ) : null}
    </>
  );

  if (clickable && onSelect) {
    return (
      <button
        type="button"
        className={`scriptBeatBlock scriptBeatBlockButton${highlight ? " scriptBeatBlockActive" : ""}`}
        onClick={onSelect}
        aria-label={`Abschnitt ${beat.order + 1} abspielen`}
      >
        {content}
      </button>
    );
  }

  return (
    <article className={`scriptBeatBlock${highlight ? " scriptBeatBlockActive" : ""}`}>
      {content}
    </article>
  );
}
