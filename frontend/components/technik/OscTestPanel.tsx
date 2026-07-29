"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchLightDeskStatus,
  fetchOscLogRecent,
  fetchOutputTargets,
  fetchQlabRelayStatus,
  fetchTechnikStatus,
  patchOutputTargets,
  postLightConnect,
  postLightDisconnect,
  postLightHoldStart,
  postLightSend,
  postLightStop,
  postOscTest,
  postQlabRelayStart,
  postQlabRelayStop,
  postTechnikStart,
  postTechnikStop,
  type LightDeskStatus,
  type OutputTargets,
  type QlabRelayStatus,
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
  const [outputTargets, setOutputTargets] = useState<OutputTargets | null>(null);
  const [videoHost, setVideoHost] = useState("");
  const [videoPort, setVideoPort] = useState("");
  const [lightHost, setLightHost] = useState("");
  const [lightPort, setLightPort] = useState("");
  const [targetsLoading, setTargetsLoading] = useState(false);
  const [targetsDirty, setTargetsDirty] = useState(false);
  const [relayStatus, setRelayStatus] = useState<QlabRelayStatus | null>(null);
  const [relayLoading, setRelayLoading] = useState(false);

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
    fetchQlabRelayStatus().then(setRelayStatus).catch(() => setRelayStatus(null));
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
    fetchOutputTargets()
      .then((targets) => {
        setOutputTargets(targets);
        setVideoHost(targets.video.effective.host);
        setVideoPort(String(targets.video.effective.port));
        setLightHost(targets.light.effective.host);
        setLightPort(String(targets.light.effective.port));
        setTargetsDirty(false);
      })
      .catch(() => {
        /* catalog fallback used for display */
      });
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

  const applyOutputTargets = useCallback(async () => {
    setError("");
    setTargetsLoading(true);
    const videoPortNum = Number(videoPort);
    const lightPortNum = Number(lightPort);
    if (!videoHost.trim() || !Number.isFinite(videoPortNum) || videoPortNum < 1 || videoPortNum > 65535) {
      setError("Video-Ziel: gültige IP/Host und Port (1–65535) eingeben");
      setTargetsLoading(false);
      return;
    }
    if (!lightHost.trim() || !Number.isFinite(lightPortNum) || lightPortNum < 1 || lightPortNum > 65535) {
      setError("Licht-Ziel: gültige IP/Host und Port (1–65535) eingeben");
      setTargetsLoading(false);
      return;
    }
    try {
      const wasLightConnected = lightStatus?.tcp_connected ?? false;
      const targets = await patchOutputTargets({
        video_host: videoHost.trim(),
        video_port: videoPortNum,
        light_host: lightHost.trim(),
        light_port: lightPortNum
      });
      setOutputTargets(targets);
      setTargetsDirty(false);
      const catalogRes = await fetchMediaCatalog("part2");
      setCatalog(catalogRes);
      if (wasLightConnected) {
        setLightStatus(await fetchLightDeskStatus());
      }
      refreshStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ziel-Konfiguration fehlgeschlagen");
    } finally {
      setTargetsLoading(false);
    }
  }, [videoHost, videoPort, lightHost, lightPort, lightStatus?.tcp_connected, refreshStatus]);

  const startRelay = useCallback(async () => {
    setError("");
    setRelayLoading(true);
    try {
      setRelayStatus(await postQlabRelayStart());
      refreshStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Relay start fehlgeschlagen");
      try {
        setRelayStatus(await fetchQlabRelayStatus());
      } catch {
        /* ignore */
      }
    } finally {
      setRelayLoading(false);
    }
  }, [refreshStatus]);

  const stopRelay = useCallback(async () => {
    setError("");
    setRelayLoading(true);
    try {
      setRelayStatus(await postQlabRelayStop());
      refreshStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Relay stop fehlgeschlagen");
    } finally {
      setRelayLoading(false);
    }
  }, [refreshStatus]);

  const dryRun = catalog?.touchdesigner?.osc_dry_run ?? false;
  const videoUsesPixera =
    (outputTargets?.visual_output ?? catalog?.pixera?.output) === "pixera" ||
    (outputTargets?.visual_output ?? catalog?.pixera?.output) === "both";
  const effectiveVideo = outputTargets?.video.effective;
  const effectiveLight = outputTargets?.light.effective;
  const videoTarget = effectiveVideo
    ? videoUsesPixera
      ? `Pixera ${catalog?.pixera?.address ?? "/pixera/args/cue/apply"} · ${effectiveVideo.host}:${effectiveVideo.port}`
      : `TouchDesigner ${effectiveVideo.host}:${effectiveVideo.port}`
    : videoUsesPixera
      ? `Pixera ${catalog?.pixera?.address ?? "/pixera/args/cue/apply"} · ${catalog?.pixera?.osc_host}:${catalog?.pixera?.osc_port}`
      : `TouchDesigner ${catalog?.touchdesigner?.osc_host}:${catalog?.touchdesigner?.osc_port}`;
  const soundTarget =
    catalog?.sound?.output === "midi" || catalog?.sound?.output === "both"
      ? `MIDI ${catalog.sound.midi_port || "auto"} · Kanal ${catalog.sound.midi_channel}`
      : catalog?.sound
        ? `OSC ${catalog.sound.osc_host}:${catalog.sound.osc_port}`
        : "—";
  const lightOutput = outputTargets?.light_output ?? catalog?.lighting?.output ?? lightStatus?.output ?? "tcp";
  const lightNeedsTcpConnect = lightOutput === "tcp";
  const lightMirrorMode = lightOutput === "mirror";
  const lightTcpTarget = effectiveLight
    ? `TCP ${effectiveLight.host}:${effectiveLight.port}`
    : catalog?.lighting
      ? `TCP ${catalog.lighting.tcp_host}:${catalog.lighting.tcp_port}`
      : "—";
  const lightMirrorTarget = effectiveLight
    ? `OSC ${effectiveLight.host}:${effectiveLight.port} ${catalog?.lighting?.preview_set_scene ?? "/light/set_scene"} → QLab Relay → QLab :53000`
    : catalog?.lighting?.preview_osc_host
      ? `OSC ${catalog.lighting.preview_osc_host}:${catalog.lighting.preview_osc_port ?? 7000} ${catalog.lighting.preview_set_scene ?? "/light/set_scene"} → QLab Relay → QLab :53000`
      : "OSC Mirror (LIGHT_OUTPUT=mirror in backend/.env)";
  const relayTargetLabel = relayStatus
    ? `Pixera :${relayStatus.pixera_listen_port}${relayStatus.light_listener_enabled ? ` · Licht :${relayStatus.light_listen_port}` : ""} → QLab ${relayStatus.qlab_host}:${relayStatus.qlab_port}`
    : "—";
  const relayRunning = relayStatus?.running ?? false;
  const relayManaged = relayStatus?.managed ?? false;
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

      <div className={`oscTestGroup oscTestRelay${relayRunning ? " oscTestGroupActive" : ""}`}>
        <div className="oscTestGroupHead">
          <span className="oscTestGroupIcon oscTestGroupIconRelay" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <path d="M4 12h6" />
              <path d="M14 12h6" />
              <path d="m10 8 4 4-4 4" />
            </svg>
          </span>
          <div>
            <h3>OSC Relay (QLab)</h3>
            <p className={relayRunning ? "oscTestActive" : "oscTestIdle"} role="status">
              {relayRunning
                ? relayManaged
                  ? `aktiv · PID ${relayStatus?.pid ?? "—"}`
                  : "aktiv (extern — z. B. make qlab-relay)"
                : "inaktiv"}
              {relayStatus?.feedback_enabled ? " · Avatar-Done-Feedback" : null}
            </p>
          </div>
        </div>
        <p className="textMuted oscTestTarget">
          Leitet Pixera- und Licht-OSC an QLab weiter. Ersetzt das separate Terminal{" "}
          <code>make qlab-relay</code>.
          <br />
          Route: <code>{relayTargetLabel}</code>
        </p>
        <div className="row oscTestActions">
          <button
            type="button"
            className="machineStartBtn"
            disabled={relayLoading || relayRunning}
            onClick={() => void startRelay()}
          >
            Relay starten
          </button>
          <button
            type="button"
            className="oscTestStopBtn"
            disabled={relayLoading || !relayManaged}
            onClick={() => void stopRelay()}
          >
            Relay stoppen
          </button>
        </div>
        {relayStatus?.error && !relayManaged ? (
          <p className="textMuted oscTestWarn" role="status">
            {relayStatus.error}
          </p>
        ) : null}
      </div>

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
          <div className="oscTestTargetFields row">
            <label className="oscTestChannel">
              <span>Video IP/Host</span>
              <input
                type="text"
                value={videoHost}
                onChange={(e) => {
                  setVideoHost(e.target.value);
                  setTargetsDirty(true);
                }}
                disabled={targetsLoading}
                autoComplete="off"
              />
            </label>
            <label className="oscTestChannel">
              <span>Port</span>
              <input
                type="number"
                min={1}
                max={65535}
                value={videoPort}
                onChange={(e) => {
                  setVideoPort(e.target.value);
                  setTargetsDirty(true);
                }}
                disabled={targetsLoading}
              />
            </label>
            <button
              type="button"
              className="machineStartBtn"
              disabled={targetsLoading || !targetsDirty}
              onClick={() => void applyOutputTargets()}
            >
              Ziel übernehmen
            </button>
          </div>
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
              Kein EOS-TCP — Relay und QLab Light Dashboard prüfen
            </p>
          ) : lightNeedsTcpConnect ? (
            <p className="textMuted oscTestTarget">
              EOS TCP <code>{lightTcpTarget}</code>: Socket verbinden, dann binäres OSC (4-Byte-Längenpräfix) auf
              derselben Verbindung — <code>/eos/chan/N/full</code> oder <code>/eos/chan/N</code> mit Prozent-Argument
              (0–100&nbsp;%) · Stopp: <code>/eos/key/out</code>
            </p>
          ) : (
            <p className="textMuted oscTestTarget">
              Ziel: OSC <code>{effectiveLight ? `${effectiveLight.host}:${effectiveLight.port}` : `${catalog?.lighting?.osc_host}:${catalog?.lighting?.osc_port}`}</code>
            </p>
          )}
          <div className="oscTestTargetFields row">
            <label className="oscTestChannel">
              <span>Licht IP/Host</span>
              <input
                type="text"
                value={lightHost}
                onChange={(e) => {
                  setLightHost(e.target.value);
                  setTargetsDirty(true);
                }}
                disabled={targetsLoading}
                autoComplete="off"
              />
            </label>
            <label className="oscTestChannel">
              <span>Port</span>
              <input
                type="number"
                min={1}
                max={65535}
                value={lightPort}
                onChange={(e) => {
                  setLightPort(e.target.value);
                  setTargetsDirty(true);
                }}
                disabled={targetsLoading}
              />
            </label>
            <button
              type="button"
              className="machineStartBtn"
              disabled={targetsLoading || !targetsDirty}
              onClick={() => void applyOutputTargets()}
            >
              Ziel übernehmen
            </button>
          </div>
          {lightNeedsTcpConnect && lightConnected && targetsDirty ? (
            <p className="textMuted oscTestWarn">
              Licht-Ziel geändert — nach „Ziel übernehmen“ EOS-Verbindung neu aufbauen.
            </p>
          ) : null}
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
