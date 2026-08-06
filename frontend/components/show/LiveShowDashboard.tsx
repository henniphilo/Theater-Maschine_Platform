"use client";

import Link from "next/link";

import { NarratorVolumeControl } from "@/components/show/NarratorVolumeControl";
import { PlaybackSpeedControl } from "@/components/show/PlaybackSpeedControl";
import { PerformanceTryoutControl } from "@/components/show/PerformanceTryoutControl";
import { SignalMonitoringPanel } from "@/components/show/SignalMonitoringPanel";
import type { MediaCatalog } from "@/lib/types/media";

export type LiveTimelineItem = {
  id: string;
  label: string;
};

type LiveShowDashboardProps = {
  title: string;
  subtitle?: string;
  running: boolean;
  paused: boolean;
  completed: boolean;
  canPlay: boolean;
  blockedReason?: string | null;
  currentIndex: number | null;
  totalCount: number;
  currentText: string;
  currentLabel?: string;
  items: LiveTimelineItem[];
  mediaCatalog?: MediaCatalog | null;
  editHref?: string;
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  onSkipNext?: () => void;
  onSkipPrev?: () => void;
  onJumpToIndex?: (index: number) => void;
};

function connectionLines(catalog: MediaCatalog | null | undefined) {
  const videoUsesPixera =
    catalog?.pixera?.output === "pixera" || catalog?.pixera?.output === "both";
  const video = videoUsesPixera
    ? `Pixera ${catalog?.pixera?.osc_host}:${catalog?.pixera?.osc_port}`
    : catalog?.touchdesigner
      ? `TD ${catalog.touchdesigner.osc_host}:${catalog.touchdesigner.osc_port}`
      : "—";
  const sound =
    catalog?.sound?.output === "midi" || catalog?.sound?.output === "both"
      ? `MIDI ${catalog.sound.midi_port || "auto"} · Ch. ${catalog.sound.midi_channel}`
      : catalog?.sound
        ? `OSC ${catalog.sound.osc_host}:${catalog.sound.osc_port}`
        : "—";
  const light = catalog?.lighting
    ? `TCP ${catalog.lighting.tcp_host}:${catalog.lighting.tcp_port}`
    : "—";
  return { video, sound, light };
}

export function LiveShowDashboard({
  title,
  subtitle,
  running,
  paused,
  completed,
  canPlay,
  blockedReason,
  currentIndex,
  totalCount,
  currentText,
  currentLabel,
  items,
  mediaCatalog,
  editHref,
  onPlay,
  onPause,
  onStop,
  onSkipNext,
  onSkipPrev,
  onJumpToIndex
}: LiveShowDashboardProps) {
  const showPause = running && !paused;
  const showPlay = !running || paused;
  const connections = connectionLines(mediaCatalog);
  const displayIndex = currentIndex != null && currentIndex > 0 ? currentIndex : "—";
  const statusText = completed
    ? "Aufführung beendet."
    : running
      ? paused
        ? "Pausiert — Signale gestoppt bis Fortsetzen."
        : "Inszenierung läuft. Signale werden gesendet."
      : blockedReason || "Bereit für Start.";

  return (
    <section className="liveDashboard col" aria-label="Live-Aufführung">
      <header className="liveDashboardHeader">
        <div>
          <div className="liveDashboardTitleRow">
            <h2 className="liveDashboardTitle">{title}</h2>
            {running ? <span className="liveBadge">{paused ? "Pausiert" : "Live"}</span> : null}
          </div>
          <p className="textMuted liveDashboardSubtitle">{subtitle ? `${subtitle} · ` : ""}{statusText}</p>
        </div>
        <div className="liveDashboardHeaderControls">
          <PlaybackSpeedControl compact disabled={running && !paused} />
          <span className={`statusPill${running && !paused ? " statusPillAccent" : " statusPillMuted"}`}>
            System {running && !paused ? "OK" : "Bereit"}
          </span>
        </div>
      </header>

      <div className="liveDashboardGrid">
        <section className="card col liveAbschnittCard">
          <div className="liveCounterCard liveCounterCardEmbedded">
            <p className="liveCounterValue">
              {displayIndex}
              <span> / {totalCount || "—"}</span>
            </p>
            <p className="liveCounterMeta">{currentLabel || "Abschnitt"}</p>
          </div>

          <div className="liveAbschnittTabs" role="tablist" aria-label="Stimme">
            <span className="statusPill statusPillAccent" role="tab" aria-selected="true">
              Erzähler
            </span>
          </div>

          <div className="liveAbschnittText" aria-live="polite">
            {currentText.trim() ? currentText : <span className="textFaint">Kein Text für diesen Abschnitt.</span>}
          </div>

          <NarratorVolumeControl disabled={!canPlay && !running} />

          <div className="liveActionRow">
            {onSkipNext ? (
              <button type="button" disabled={!canPlay || !running} onClick={onSkipNext}>
                Abschnitt überspringen
              </button>
            ) : null}
            {editHref ? (
              <Link href={editHref as "/inszenierung"}>Inszenierung bearbeiten</Link>
            ) : null}
          </div>
        </section>

        <section className="card col liveTransportCard" aria-label="Transport">
          <div className="liveTransportMain">
            <button
              type="button"
              className="machineStopBtn transportBtn transportBtnStop"
              disabled={!canPlay || (!running && !paused)}
              onClick={onStop}
              aria-label="Stoppen"
            >
              ⏹
            </button>
            {showPlay ? (
              <button
                type="button"
                className="machineStartBtn transportBtn transportBtnPlay"
                disabled={!canPlay}
                onClick={onPlay}
                aria-label={paused ? "Fortsetzen" : "Abspielen"}
              >
                ▶
              </button>
            ) : null}
            {showPause ? (
              <button
                type="button"
                className="transportBtn transportBtnPause"
                disabled={!canPlay}
                onClick={onPause}
                aria-label="Pause"
              >
                ⏸
              </button>
            ) : null}
            {onSkipNext ? (
              <button
                type="button"
                className="transportBtn"
                disabled={!canPlay || currentIndex == null || currentIndex >= totalCount}
                onClick={onSkipNext}
                aria-label="Nächster Abschnitt"
              >
                ⏭
              </button>
            ) : null}
          </div>
          <div className="liveTransportSecondary">
            <button type="button" disabled={!canPlay} onClick={onStop}>
              Reset
            </button>
            {onSkipPrev ? (
              <button
                type="button"
                disabled={!canPlay || currentIndex == null || currentIndex <= 1}
                onClick={onSkipPrev}
              >
                Zurück
              </button>
            ) : null}
            {onSkipNext ? (
              <button
                type="button"
                disabled={!canPlay || currentIndex == null || currentIndex >= totalCount}
                onClick={onSkipNext}
              >
                Weiter
              </button>
            ) : null}
          </div>
          <PerformanceTryoutControl />
        </section>

        <SignalMonitoringPanel />
      </div>

      {items.length > 0 ? (
        <section className="card col liveTimelineCard" aria-label="Abschnittsübersicht">
          <header className="liveTimelineHeader">
            <h3>Abschnittsübersicht</h3>
            <span className="textMuted">{totalCount} Abschnitte</span>
          </header>
          <div className="liveTimelineTrack" role="list">
            {items.map((item, index) => {
              const active = currentIndex === index + 1;
              const done = currentIndex != null && index + 1 < currentIndex;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="listitem"
                  className={`liveTimelineTick${active ? " liveTimelineTickActive" : ""}${done ? " liveTimelineTickDone" : ""}`}
                  title={`${item.label} — ab hier starten`}
                  disabled={!onJumpToIndex || (!canPlay && !running && !paused)}
                  onClick={() => onJumpToIndex?.(index)}
                >
                  <span className="liveTimelineTickLabel">{index + 1}</span>
                </button>
              );
            })}
          </div>
        </section>
      ) : null}

      <footer className="liveConnectionBar" aria-label="Verbindungen">
        <span className="liveConnectionLabel">Verbindungen</span>
        <div className="liveConnectionItems">
          <span className="liveConnectionItem">
            <strong>Video</strong>
            <code>{connections.video}</code>
          </span>
          <span className="liveConnectionItem">
            <strong>Ton</strong>
            <code>{connections.sound}</code>
          </span>
          <span className="liveConnectionItem">
            <strong>Licht</strong>
            <code>{connections.light}</code>
          </span>
        </div>
        <Link className="liveConnectionLink" href="/technik">
          Technik-Test
        </Link>
        <Link className="liveConnectionLink" href="/director">
          Protokoll
        </Link>
      </footer>
    </section>
  );
}
