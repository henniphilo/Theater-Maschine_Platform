"use client";

import type { PlaybackMode, SegmentPhase } from "@/features/show/scriptPlayback";
import {
  beatIndexFromProgress,
  formatTimelineLabel,
  progressFromBeat
} from "@/lib/show/performanceTimeline";
import type { ShowPhase } from "@/lib/types/director";
import type { ScriptBeat } from "@/lib/types/script";
import { dramaturgSpeakerLabel, speakerLabel } from "@/lib/types/script";

type PerformanceTransportProps = {
  beats: ScriptBeat[];
  beatIndex: number;
  beatCount: number;
  timelineProgress: number;
  running: boolean;
  paused: boolean;
  completed: boolean;
  canPlay: boolean;
  playBlockedReason?: string;
  segmentPhase?: SegmentPhase;
  discussionTurnIndex?: number;
  sentenceIndex?: number;
  showPhase?: ShowPhase;
  activeOscBridge?: string | null;
  playbackMode?: PlaybackMode;
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  onSeek: (progress: number) => void;
};

function phaseDetail(
  segmentPhase: SegmentPhase | undefined,
  beat: ScriptBeat | undefined,
  discussionTurnIndex?: number,
  sentenceIndex?: number,
  showPhase?: ShowPhase,
  activeOscBridge?: string | null,
  playbackMode?: PlaybackMode
): string {
  const modeLabel =
    playbackMode === "discussion"
      ? "Nur Dramaturgie"
      : playbackMode === "performance"
        ? "Nur Stücktext"
        : null;
  if (!beat) return modeLabel ?? "";
  if (segmentPhase === "discussion") {
    const n = beat.discussion_turns?.length ?? 0;
    const turn = discussionTurnIndex !== undefined ? discussionTurnIndex + 1 : 1;
    const speaker = beat.discussion_turns?.[discussionTurnIndex ?? 0]?.speaker;
    const cueHint =
      showPhase === "cues_active" && activeOscBridge
        ? ` · Probe-Cues (${activeOscBridge})`
        : "";
    return `Dramaturgie · Turn ${turn}${n ? `/${n}` : ""}${speaker ? ` · ${dramaturgSpeakerLabel(speaker)}` : ""}${cueHint}${modeLabel ? ` · ${modeLabel}` : ""}`;
  }
  if (segmentPhase === "performance") {
    return `Stücktext · ${speakerLabel(beat.speaker)}${sentenceIndex !== undefined ? ` · Satz ${sentenceIndex + 1}` : ""}${modeLabel ? ` · ${modeLabel}` : ""}`;
  }
  if (beat.discussion_turns?.length) {
    return modeLabel ? `${modeLabel} · Bereit` : "Bereit · mit Dramaturgie";
  }
  return `${modeLabel ? `${modeLabel} · ` : ""}Stücktext · ${speakerLabel(beat.speaker)}`;
}

export function PerformanceTransport({
  beats,
  beatIndex,
  beatCount,
  timelineProgress,
  running,
  paused,
  completed,
  canPlay,
  playBlockedReason,
  segmentPhase,
  discussionTurnIndex,
  sentenceIndex,
  showPhase,
  activeOscBridge,
  playbackMode,
  onPlay,
  onPause,
  onStop,
  onSeek
}: PerformanceTransportProps) {
  const safeBeatIndex = beatIndex >= 0 ? beatIndex : 0;
  const currentBeat = beats[safeBeatIndex];
  const sliderValue = Math.round(Math.max(0, Math.min(1, timelineProgress)) * 1000);
  const showPause = running && !paused;
  const showPlay = !running || paused;

  return (
    <footer className="performanceTransport" aria-label="Aufführungs-Zeitspur">
      <div className="performanceTransportInner">
        <div className="performanceTransportMeta">
          <strong>{formatTimelineLabel(safeBeatIndex, beatCount)}</strong>
          <span className="textMuted performanceTransportDetail">
            {completed
              ? "Beendet"
              : running
                ? paused
                  ? "Pausiert"
                  : "Läuft"
                : playBlockedReason || "Bereit"}
            {currentBeat
              ? ` · ${phaseDetail(segmentPhase, currentBeat, discussionTurnIndex, sentenceIndex, showPhase, activeOscBridge, playbackMode)}`
              : ""}
          </span>
        </div>

        <div className="performanceTransportScrub">
          <input
            type="range"
            min={0}
            max={1000}
            value={sliderValue}
            disabled={!canPlay || beatCount === 0}
            aria-label="Zeitspur — Abschnitt wählen"
            onChange={(e) => onSeek(Number(e.target.value) / 1000)}
          />
          <div className="performanceTransportTicks" aria-hidden>
            {beats.map((beat, index) => (
              <button
                key={beat.id}
                type="button"
                className={`performanceTransportTick${index === safeBeatIndex ? " performanceTransportTickActive" : ""}${
                  index < safeBeatIndex || completed ? " performanceTransportTickDone" : ""
                }`}
                title={`Abschnitt ${index + 1}`}
                disabled={!canPlay}
                onClick={() => onSeek(progressFromBeat(index, beatCount, 0))}
              />
            ))}
          </div>
        </div>

        <div className="performanceTransportControls">
          {showPlay ? (
            <button
              type="button"
              className="machineStartBtn"
              disabled={!canPlay}
              onClick={onPlay}
              aria-label={paused ? "Fortsetzen" : "Abspielen"}
            >
              {paused ? "▶ Fortsetzen" : "▶ Play"}
            </button>
          ) : null}
          {showPause ? (
            <button type="button" disabled={!canPlay} onClick={onPause} aria-label="Pause">
              ⏸ Pause
            </button>
          ) : null}
          <button
            type="button"
            className="machineStopBtn"
            disabled={!canPlay || (!running && !paused && beatIndex < 0)}
            onClick={onStop}
            aria-label="Stoppen"
          >
            ⏹ Stop
          </button>
        </div>
      </div>
    </footer>
  );
}

export { beatIndexFromProgress };
