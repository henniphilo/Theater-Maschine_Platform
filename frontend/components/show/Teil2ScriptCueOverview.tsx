"use client";

import { useMemo, useState } from "react";

import type { CueAnnotationKind, ScriptCueOverview } from "@/lib/types/inszenierung";

const KIND_LABELS: Record<CueAnnotationKind, string> = {
  light: "Licht",
  sound: "Sound",
  video: "Video",
  avatar: "Avatar"
};

const KIND_CLASS: Record<CueAnnotationKind, string> = {
  light: "teil2CueBadgeLight",
  sound: "teil2CueBadgeSound",
  video: "teil2CueBadgeVideo",
  avatar: "teil2CueBadgeAvatar"
};

type Teil2ScriptCueOverviewProps = {
  overview: ScriptCueOverview;
};

export function Teil2ScriptCueOverview({ overview }: Teil2ScriptCueOverviewProps) {
  const [filter, setFilter] = useState<CueAnnotationKind | "all">("all");

  const visibleRows = useMemo(() => {
    if (filter === "all") return overview.rows;
    return overview.rows
      .map((row) => ({
        ...row,
        annotations: row.annotations.filter((item) => item.kind === filter)
      }))
      .filter((row) => row.annotations.length > 0);
  }, [filter, overview.rows]);

  const atmosphere = useMemo(() => {
    if (filter === "all") return overview.atmosphere_timeline;
    return overview.atmosphere_timeline.filter((item) => item.kind === filter);
  }, [filter, overview.atmosphere_timeline]);

  return (
    <section className="col" style={{ gap: "1rem" }}>
      <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
        <span className="textMuted">Filter:</span>
        {(["all", "light", "sound", "video", "avatar"] as const).map((kind) => (
          <button
            key={kind}
            type="button"
            className={filter === kind ? "machineStartBtn" : ""}
            onClick={() => setFilter(kind)}
          >
            {kind === "all" ? "Alle" : KIND_LABELS[kind]}
          </button>
        ))}
      </div>

      <div className="col teil2CueOverviewScript">
        {visibleRows.map((row) => (
          <article key={row.sentence_index} className="teil2CueOverviewRow">
            <header className="teil2CueOverviewRowHeader">
              <span className="textMuted">Satz {row.sentence_index + 1}</span>
              {row.annotations.length > 0 ? (
                <div className="teil2CueBadgeRow">
                  {row.annotations.map((annotation, index) => (
                    <span key={`${row.sentence_index}-${annotation.kind}-${annotation.label}-${index}`}>
                      <span
                        className={`teil2CueBadge ${KIND_CLASS[annotation.kind]}`}
                        title={annotation.reason ?? undefined}
                      >
                        {KIND_LABELS[annotation.kind]}: {annotation.label}
                        {annotation.projector ? ` @ ${annotation.projector}` : ""}
                      </span>
                      {annotation.reason ? (
                        <span className="teil2CueReasonInline textMuted"> – {annotation.reason}</span>
                      ) : null}
                    </span>
                  ))}
                </div>
              ) : null}
            </header>
            <p className="teil2SentenceText">{row.text}</p>
          </article>
        ))}
      </div>

      {atmosphere.length > 0 ? (
        <section className="card col">
          <h3>Atmosphäre (parallel)</h3>
          <p className="textMuted">Zeitbasierte B-Roll auf freien Beamern — unabhängig vom Avatar-Rhythmus.</p>
          <ul className="teil2CueTimeline" style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {atmosphere.map((item, index) => (
              <li key={`${item.time_sec}-${item.label}-${index}`} className="teil2CueTimelineItem">
                <time className="textMuted">{formatTime(item.time_sec)}</time>
                <span className={`teil2CueBadge ${KIND_CLASS[item.kind]}`}>
                  {item.label}
                  {item.projector ? ` @ ${item.projector}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}

function formatTime(timeSec: number | null | undefined): string {
  if (timeSec == null) return "—";
  const minutes = Math.floor(timeSec / 60);
  const seconds = Math.floor(timeSec % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
