import { MediaCueDetail } from "@/components/script/MediaCueDetail";
import type { MediaLookup } from "@/lib/types/media";
import type { ScriptBeat, ScriptSpeaker } from "@/lib/types/script";
import { dramaturgSpeakerLabel, speakerLabel } from "@/lib/types/script";
import { displayReasonShort, dramaturgicalFunctionLabel } from "@/lib/dramaturgy/labels";

export function ScriptBeatBlock({
  beat,
  editable = false,
  onSpeakerChange,
  highlight = false,
  sentenceIndex,
  segmentPhase,
  discussionTurnIndex,
  clickable = false,
  onSelect,
  media
}: {
  beat: ScriptBeat;
  editable?: boolean;
  onSpeakerChange?: (speaker: ScriptSpeaker) => void;
  highlight?: boolean;
  sentenceIndex?: number;
  segmentPhase?: "discussion" | "performance";
  discussionTurnIndex?: number;
  clickable?: boolean;
  onSelect?: () => void;
  media?: MediaLookup;
}) {
  const d = beat.dramaturgy;
  const mood = d?.mood ?? "—";
  const reasonShort = d ? displayReasonShort(d.reason_short, d.reason) : "";
  const functionLabel = d?.dramaturgical_function
    ? dramaturgicalFunctionLabel(d.dramaturgical_function)
    : "";
  const turns = beat.discussion_turns ?? [];

  const content = (
    <>
      <header className="scriptBeatHeader">
        <span className="scriptBeatMeta">
          {beat.scene_title ? (
            <>
              <strong>{beat.scene_title}</strong>
              {" · "}
            </>
          ) : null}
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
        {d?.performance_speakers?.length ? (
          <span className="textMuted" style={{ fontSize: "0.85rem", marginLeft: "0.5rem" }}>
            Stück-Stimmen: {d.performance_speakers.map((s) => speakerLabel(s)).join(", ")}
          </span>
        ) : null}
      </header>

      {turns.length > 0 ? (
        <div className="scriptBeatDiscussion col" style={{ gap: "0.5rem", marginBottom: "0.75rem" }}>
          <span className="textMuted" style={{ fontSize: "0.85rem" }}>
            Dramaturgen-Gespräch ({turns.length} Beiträge)
          </span>
          {turns.map((turn, index) => (
            <blockquote
              key={`${beat.id}-turn-${index}`}
              className={`scriptBeatDiscussionTurn${
                highlight && segmentPhase === "discussion" && discussionTurnIndex === index
                  ? " scriptBeatBlockActive"
                  : ""
              }`}
              style={{ margin: 0, paddingLeft: "0.75rem", borderLeft: "2px solid var(--border, #444)" }}
            >
              <strong style={{ fontSize: "0.85rem" }}>{dramaturgSpeakerLabel(turn.speaker)}</strong>
              <div style={{ fontSize: "0.9rem" }}>{turn.content}</div>
            </blockquote>
          ))}
        </div>
      ) : null}

      <blockquote className="scriptBeatText">{beat.text}</blockquote>
      {d ? (
        <>
          <MediaCueDetail dramaturgy={d} media={media} />
          {reasonShort ? (
            <p className="scriptBeatReason">
              {functionLabel ? <span className="textMuted">{functionLabel} · </span> : null}
              – {reasonShort}
            </p>
          ) : null}
        </>
      ) : (
        <p className="textFaint">Noch keine Regieentscheidung.</p>
      )}
      {highlight && segmentPhase === "performance" && sentenceIndex !== undefined ? (
        <p className="textMuted" style={{ fontSize: "0.85rem" }}>
          Satz {sentenceIndex + 1} wird gesprochen …
        </p>
      ) : null}
      {highlight && segmentPhase === "discussion" && discussionTurnIndex !== undefined ? (
        <p className="textMuted" style={{ fontSize: "0.85rem" }}>
          Dramaturgen-Turn {discussionTurnIndex + 1} wird vertont …
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
