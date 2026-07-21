"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchLightDeskStatus,
  fetchOscLogRecent,
  fetchTechnikStatus,
  postLightConnect,
  postLightDisconnect,
  postLightHoldStart,
  postLightSend,
  postLightStop,
  postOscTest,
  postTechnikStart,
  postTechnikStop,
  type LightDeskStatus,
  type TechnikHoldStatus
} from "@/lib/api/director";
import { fetchMediaCatalog } from "@/lib/api/media";
import type { MediaCatalog } from "@/lib/types/media";
import { formatLightChannelLabel } from "@/lib/types/media";
import { formatMidiTrigger } from "@/lib/midi/format";

export function OscTestPanel() {
  const [catalog, setCatalog] = useState<MediaCatalog | null>(null);
  const [clipId, setClipId] = useState("clyde");
  const [soundId, setSoundId] = useState("maschinen_grundader");
  const [lightId, setLightId] = useState("vorbuehnenzug");
  const [lightIntensityPercent, setLightIntensityPercent] = useState(100);
  const [useLightIntensity, setUseLightIntensity] = useState(false);
  const [videoLoading, setVideoLoading] = useState(false);
  const [soundLoading, setSoundLoading] = useState(false);
  const [lightLoading, setLightLoading] = useState(false);
  const [error, setError] = useState("");
  const [holdStatus, setHoldStatus] = useState<TechnikHoldStatus | null>(null);
  const [lightStatus, setLightStatus] = useState<LightDeskStatus | null>(null);
  const [lightOscLines, setLightOscLines] = useState<string[]>([]);

  const refreshLightOscLog = useCallback(async () => {
    try {
      const data = await fetchOscLogRecent(120);
      const lines = data.lines.filter(
        (line) => line.includes("[light]") || line.includes("/light/")
      );
      setLightOscLines(lines.slice(-6));
    } catch {
      setLightOscLines([]);
    }
  }, []);

  const refreshStatus = useCallback(() => {
    fetchTechnikStatus().then(setHoldStatus).catch(() => setHoldStatus(null));
    fetchLightDeskStatus()
      .then((status) => {
        setLightStatus(status);
      })
      .catch(() => setLightStatus(null));
    void refreshLightOscLog();
  }, [refreshLightOscLog]);

  useEffect(() => {
    fetchMediaCatalog("part2")
      .then((c) => {
        setCatalog(c);
        if (c.videos[0]) setClipId(c.videos[0].id);
        if (c.sounds[0]) setSoundId(c.sounds[0].id);
        if (c.lights[0]) setLightId(c.lights[0].id);
      })
      .catch(() => setError("Medien-Katalog nicht erreichbar"));
    refreshStatus();
    const id = setInterval(refreshStatus, 2000);
    return () => clearInterval(id);
  }, [refreshStatus]);

  const sendVideo = useCallback(async () => {
    setError("");
    setVideoLoading(true);
    try {
      await postOscTest({
        clip_id: clipId,
        send_visual: true,
        send_sound: false,
        send_light: false
      });
      refreshStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Video-Signal fehlgeschlagen");
    } finally {
      setVideoLoading(false);
    }
  }, [clipId, refreshStatus]);

  const holdVideo = useCallback(async () => {
    setError("");
    setVideoLoading(true);
    try {
      setHoldStatus(
        await postTechnikStart({
          clip_id: clipId,
          send_visual: true,
          send_sound: false,
          send_light: false,
          stagger: false
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Video-Hold fehlgeschlagen");
    } finally {
      setVideoLoading(false);
    }
  }, [clipId]);

  const stopVideo = useCallback(async () => {
    setError("");
    setVideoLoading(true);
    try {
      setHoldStatus(
        await postTechnikStop({
          send_visual: true,
          send_sound: false,
          send_light: false
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Video-Stopp fehlgeschlagen");
    } finally {
      setVideoLoading(false);
    }
  }, []);

  const sendSound = useCallback(async () => {
    setError("");
    setSoundLoading(true);
    try {
      await postOscTest({
        sound_cue_id: soundId,
        send_visual: false,
        send_sound: true,
        send_light: false
      });
      refreshStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sound-Signal fehlgeschlagen");
    } finally {
      setSoundLoading(false);
    }
  }, [refreshStatus, soundId]);

  const holdSound = useCallback(async () => {
    setError("");
    setSoundLoading(true);
    try {
      setHoldStatus(
        await postTechnikStart({
          sound_cue_id: soundId,
          send_visual: false,
          send_sound: true,
          send_light: false,
          stagger: false
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sound-Hold fehlgeschlagen");
    } finally {
      setSoundLoading(false);
    }
  }, [soundId]);

  const stopSound = useCallback(async () => {
    setError("");
    setSoundLoading(true);
    try {
      setHoldStatus(
        await postTechnikStop({
          send_visual: false,
          send_sound: true,
          send_light: false
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sound-Stopp fehlgeschlagen");
    } finally {
      setSoundLoading(false);
    }
  }, []);

  const connectLight = useCallback(async () => {
    setError("");
    setLightLoading(true);
    try {
      setLightStatus(await postLightConnect());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verbindung fehlgeschlagen");
    } finally {
      setLightLoading(false);
    }
  }, []);

  const disconnectLight = useCallback(async () => {
    setError("");
    setLightLoading(true);
    try {
      setLightStatus(await postLightDisconnect());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Trennen fehlgeschlagen");
    } finally {
      setLightLoading(false);
    }
  }, []);

  const lightIntensity = useLightIntensity ? lightIntensityPercent / 100 : null;

  const sendLight = useCallback(async () => {
    setError("");
    setLightLoading(true);
    try {
      setLightStatus(await postLightSend(lightId, { intensity: lightIntensity }));
      await refreshLightOscLog();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Licht-Signal fehlgeschlagen");
    } finally {
      setLightLoading(false);
    }
  }, [lightId, lightIntensity, refreshLightOscLog]);

  const holdLight = useCallback(async () => {
    setError("");
    setLightLoading(true);
    try {
      setLightStatus(await postLightHoldStart(lightId, { intensity: lightIntensity }));
      await refreshLightOscLog();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Licht-Hold fehlgeschlagen");
    } finally {
      setLightLoading(false);
    }
  }, [lightId, lightIntensity, refreshLightOscLog]);

  const stopLight = useCallback(async () => {
    setError("");
    setLightLoading(true);
    try {
      setLightStatus(await postLightStop());
      await refreshLightOscLog();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Licht-Stopp fehlgeschlagen");
    } finally {
      setLightLoading(false);
    }
  }, [refreshLightOscLog]);

  const dryRun = catalog?.touchdesigner?.osc_dry_run ?? false;
  const videoUsesPixera =
    catalog?.pixera?.output === "pixera" || catalog?.pixera?.output === "both";
  const videoTarget = videoUsesPixera
    ? `Pixera ${catalog?.pixera?.address ?? "/pixera/args/cue/apply"} · ${catalog?.pixera?.osc_host}:${catalog?.pixera?.osc_port}`
    : `TouchDesigner ${catalog?.touchdesigner?.osc_host}:${catalog?.touchdesigner?.osc_port}`;
  const soundTarget =
    catalog?.sound?.output === "midi" || catalog?.sound?.output === "both"
      ? `MIDI ${catalog.sound.midi_port || "auto"} · Kanal ${catalog.sound.midi_channel}`
      : catalog?.sound
        ? `OSC ${catalog.sound.osc_host}:${catalog.sound.osc_port}`
        : "—";
  const lightOutput = catalog?.lighting?.output ?? lightStatus?.output ?? "tcp";
  const lightNeedsTcpConnect = lightOutput === "tcp";
  const lightMirrorMode = lightOutput === "mirror";
  const lightTcpTarget = catalog?.lighting
    ? `TCP ${catalog.lighting.tcp_host}:${catalog.lighting.tcp_port}`
    : "—";
  const lightMirrorTarget = catalog?.lighting?.preview_osc_host
    ? `OSC ${catalog.lighting.preview_osc_host}:${catalog.lighting.preview_osc_port ?? 7000} ${catalog.lighting.preview_set_scene ?? "/light/set_scene"} → make qlab-relay → QLab :53000`
    : "OSC Mirror (LIGHT_OUTPUT=mirror in backend/.env)";
  const lightReady = lightNeedsTcpConnect
    ? (lightStatus?.tcp_connected ?? false)
    : Boolean(catalog?.lighting);
  const lightConnected = lightStatus?.tcp_connected ?? false;
  const lightActive = Boolean(lightStatus?.scene_id || lightStatus?.hold_active);
  const videoHolding = Boolean(holdStatus?.active && holdStatus.send_visual);
  const soundHolding = Boolean(holdStatus?.active && holdStatus.send_sound);

  return (
    <section className="card col oscTestPanel">
      <p className="textMuted" style={{ marginTop: 0 }}>
        Video, Sound und Licht jeweils einzeln testen — wie am Licht-Pult: Signal senden, halten oder stoppen.
        {dryRun ? <span className="oscTestWarn"> · DRY-RUN aktiv</span> : null}
      </p>

      <div className="oscTestGrid">
        <div className={`oscTestGroup${videoHolding ? " oscTestGroupActive" : ""}`}>
          <div className="oscTestGroupHead">
            <span className="oscTestGroupIcon oscTestGroupIconVideo" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <rect x="3" y="6" width="13" height="12" rx="2" />
                <path d="M16 10l5-3v10l-5-3" />
              </svg>
            </span>
            <div>
              <h3>Video</h3>
              <p className={videoHolding ? "oscTestActive" : "oscTestIdle"} role="status">
                {videoHolding ? `halten · Clip ${holdStatus?.clip_id}` : "inaktiv"}
              </p>
            </div>
          </div>
          <p className="textMuted oscTestTarget">
            Ziel: <code>{videoTarget}</code>
            {videoUsesPixera ? " · Testclip auf allen Beamern (RZ21, Adam, Eva, LED)" : null}
          </p>
          <label className="oscTestChannel">
            <span>Clip</span>
            <select value={clipId} onChange={(e) => setClipId(e.target.value)} disabled={videoLoading}>
              {(catalog?.videos ?? []).map((v) => (
                <option key={v.id} value={v.id}>{v.id}</option>
              ))}
            </select>
          </label>
          <div className="row oscTestActions">
            <button type="button" disabled={videoLoading} onClick={() => void sendVideo()}>
              Signal senden
            </button>
            <button type="button" className="machineStartBtn" disabled={videoLoading} onClick={() => void holdVideo()}>
              Signal halten
            </button>
            <button type="button" className="oscTestStopBtn" disabled={videoLoading} onClick={() => void stopVideo()}>
              Signal stoppen
            </button>
          </div>
        </div>

        <div className={`oscTestGroup${soundHolding ? " oscTestGroupActive" : ""}`}>
          <div className="oscTestGroupHead">
            <span className="oscTestGroupIcon oscTestGroupIconSound" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path d="M11 5 6 9H3v6h3l5 4V5Z" />
                <path d="M15.5 8.5a5 5 0 0 1 0 7" />
                <path d="M18 6a8 8 0 0 1 0 12" />
              </svg>
            </span>
            <div>
              <h3>Sound</h3>
              <p className={soundHolding ? "oscTestActive" : "oscTestIdle"} role="status">
                {soundHolding ? `halten · ${holdStatus?.sound_cue_id}` : "inaktiv"}
              </p>
            </div>
          </div>
          <p className="textMuted oscTestTarget">
            Ziel: <code>{soundTarget}</code>
            {catalog?.sound?.output === "midi" ? " · Note On/Off an Ableton" : null}
          </p>
          <label className="oscTestChannel">
            <span>Sound-Cue</span>
            <select value={soundId} onChange={(e) => setSoundId(e.target.value)} disabled={soundLoading}>
              {(catalog?.sounds ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.soundname || s.label || s.id}
                  {s.action && s.action !== "play" ? ` [${s.action}]` : ""}
                  {s.midi_note != null
                    ? ` · ${formatMidiTrigger(s.midi_note, s.channel ?? catalog?.sound?.midi_channel ?? 1)}`
                    : ""}
                </option>
              ))}
            </select>
          </label>
          <div className="row oscTestActions">
            <button type="button" disabled={soundLoading} onClick={() => void sendSound()}>
              Signal senden
            </button>
            <button type="button" className="machineStartBtn" disabled={soundLoading} onClick={() => void holdSound()}>
              Signal halten
            </button>
            <button type="button" className="oscTestStopBtn" disabled={soundLoading} onClick={() => void stopSound()}>
              Signal stoppen
            </button>
          </div>
        </div>

        <div className={`oscTestGroup${lightNeedsTcpConnect ? (lightConnected ? " oscTestGroupActive" : "") : lightActive ? " oscTestGroupActive" : ""}`}>
          <div className="oscTestGroupHead">
            <span className="oscTestGroupIcon oscTestGroupIconLight" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path d="M9 18h6" />
                <path d="M10 21h4" />
                <path d="M12 3a6 6 0 0 1 4 10c-.7.7-1 1.5-1 2.5v.5H9v-.5c0-1-.3-1.8-1-2.5A6 6 0 0 1 12 3Z" />
              </svg>
            </span>
            <div>
              <h3>Licht</h3>
              <p className={lightReady || lightActive ? "oscTestActive" : "oscTestIdle"} role="status">
                {lightMirrorMode
                  ? "QLab-Simulation — direkt senden"
                  : lightNeedsTcpConnect
                    ? lightConnected
                      ? "EOS verbunden"
                      : "EOS nicht verbunden"
                    : "OSC — direkt senden"}
                {lightStatus?.scene_id ? (
                  <span>
                    {" "}
                    · Signal:{" "}
                    {formatLightChannelLabel(
                      catalog?.lights.find((l) => l.id === lightStatus.scene_id) ?? {
                        id: lightStatus.scene_id,
                        description: "",
                        moods: [],
                        fade_time: 0
                      }
                    )}
                    {lightStatus.hold_active ? " (halten)" : ""}
                    {lightStatus.intensity != null ? (
                      <span> · {Math.round(lightStatus.intensity * 100)}&nbsp;%</span>
                    ) : null}
                  </span>
                ) : null}
              </p>
            </div>
          </div>
          {lightMirrorMode ? (
            <p className="textMuted oscTestTarget">
              Ziel: <code>{lightMirrorTarget}</code>
              {" · "}
              Kein EOS-TCP — Relay-Terminal und QLab Light Dashboard prüfen
            </p>
          ) : lightNeedsTcpConnect ? (
            <p className="textMuted oscTestTarget">
              EOS TCP <code>{lightTcpTarget}</code>: Socket verbinden, dann binäres OSC (4-Byte-Längenpräfix) auf
              derselben Verbindung — <code>/eos/chan/N/full</code> oder <code>/eos/chan/N</code> mit Prozent-Argument
              (0–100&nbsp;%) · Stopp: <code>/eos/key/out</code>
            </p>
          ) : (
            <p className="textMuted oscTestTarget">
              Ziel: OSC <code>{catalog?.lighting?.osc_host}:{catalog?.lighting?.osc_port}</code>
            </p>
          )}
          {lightNeedsTcpConnect ? (
            <div className="row oscTestActions">
              <button type="button" className="machineStartBtn" disabled={lightLoading || lightConnected} onClick={() => void connectLight()}>
                1. Verbindung aufbauen
              </button>
              <button type="button" disabled={lightLoading || !lightConnected} onClick={() => void disconnectLight()}>
                Verbindung trennen
              </button>
            </div>
          ) : null}
          <label className="oscTestChannel">
            <span>{lightNeedsTcpConnect ? "2. Licht-Szene" : "Licht-Szene"}</span>
            <select
              value={lightId}
              onChange={(e) => setLightId(e.target.value)}
              disabled={lightLoading || !lightReady}
            >
              {(catalog?.lights ?? []).filter((l) => l.id !== "blackout").map((l) => (
                <option key={l.id} value={l.id}>{formatLightChannelLabel(l)}</option>
              ))}
            </select>
          </label>
          {!lightNeedsTcpConnect ? (
            <p className="textMuted" style={{ margin: "0.25rem 0 0" }}>
              {lightMirrorMode
                ? "Mirror-Modus: Szene senden → Relay → QLab Light-Cue (TMPREVIEW)."
                : "Kein EOS-TCP nötig — Szene direkt per OSC senden."}
            </p>
          ) : (
            <label className="oscTestChannel oscTestIntensity">
              <span className="oscTestIntensityHeader">
                <span>Intensität testen</span>
                <label className="oscTestIntensityToggle">
                  <input
                    type="checkbox"
                    checked={useLightIntensity}
                    onChange={(e) => setUseLightIntensity(e.target.checked)}
                    disabled={lightLoading || !lightReady}
                  />
                  Teilhelligkeit
                </label>
              </span>
              <input
                type="range"
                min={1}
                max={100}
                step={1}
                value={lightIntensityPercent}
                onChange={(e) => setLightIntensityPercent(Number(e.target.value))}
                disabled={lightLoading || !lightReady || !useLightIntensity}
                aria-valuemin={1}
                aria-valuemax={100}
                aria-valuenow={lightIntensityPercent}
                aria-label="Lichtintensität in Prozent"
              />
              <div className="oscTestIntensityMeta">
                <strong>{useLightIntensity ? `${lightIntensityPercent} %` : "Full (100 %)"}</strong>
                <span className="textMuted">
                  {useLightIntensity
                    ? `→ /eos/chan/N ${lightIntensityPercent}`
                    : "→ /eos/chan/N/full"}
                </span>
              </div>
              <div className="row oscTestIntensityPresets">
                {[25, 50, 75, 100].map((pct) => (
                  <button
                    key={pct}
                    type="button"
                    disabled={lightLoading || !lightReady || !useLightIntensity}
                    onClick={() => setLightIntensityPercent(pct)}
                  >
                    {pct}%
                  </button>
                ))}
              </div>
            </label>
          )}
          <div className="row oscTestActions">
            <button type="button" disabled={lightLoading || !lightReady} onClick={() => void sendLight()}>
              Signal senden
            </button>
            <button type="button" disabled={lightLoading || !lightReady} onClick={() => void holdLight()}>
              Signal halten
            </button>
            <button type="button" className="oscTestStopBtn" disabled={lightLoading || !lightReady} onClick={() => void stopLight()}>
              {lightMirrorMode ? "Blackout (/light/blackout)" : "Signal aus (/eos/key/out)"}
            </button>
          </div>
          {!lightNeedsTcpConnect ? (
            <div className="oscTestLog" aria-live="polite">
              <p className="textMuted" style={{ marginTop: 0 }}>
                Letzte Licht-OSC (aus <code>logs/osc.log</code>):
              </p>
              {lightOscLines.length ? (
                <ul className="oscLogList">
                  {lightOscLines.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              ) : (
                <p className="textMuted">Noch kein Licht-OSC — Szene senden oder DRY-RUN prüfen.</p>
              )}
            </div>
          ) : null}
        </div>
      </div>

      {error ? <div className="textError" role="alert">{error}</div> : null}
    </section>
  );
}
