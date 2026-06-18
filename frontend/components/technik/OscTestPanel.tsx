"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchLightDeskStatus,
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
  const [videoLoading, setVideoLoading] = useState(false);
  const [soundLoading, setSoundLoading] = useState(false);
  const [lightLoading, setLightLoading] = useState(false);
  const [error, setError] = useState("");
  const [holdStatus, setHoldStatus] = useState<TechnikHoldStatus | null>(null);
  const [lightStatus, setLightStatus] = useState<LightDeskStatus | null>(null);

  const refreshStatus = useCallback(() => {
    fetchTechnikStatus().then(setHoldStatus).catch(() => setHoldStatus(null));
    fetchLightDeskStatus().then(setLightStatus).catch(() => setLightStatus(null));
  }, []);

  useEffect(() => {
    fetchMediaCatalog()
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

  const sendLight = useCallback(async () => {
    setError("");
    setLightLoading(true);
    try {
      setLightStatus(await postLightSend(lightId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Licht-Signal fehlgeschlagen");
    } finally {
      setLightLoading(false);
    }
  }, [lightId]);

  const holdLight = useCallback(async () => {
    setError("");
    setLightLoading(true);
    try {
      setLightStatus(await postLightHoldStart(lightId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Licht-Hold fehlgeschlagen");
    } finally {
      setLightLoading(false);
    }
  }, [lightId]);

  const stopLight = useCallback(async () => {
    setError("");
    setLightLoading(true);
    try {
      setLightStatus(await postLightStop());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Licht-Stopp fehlgeschlagen");
    } finally {
      setLightLoading(false);
    }
  }, []);

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
  const lightTcpTarget = catalog?.lighting
    ? `TCP ${catalog.lighting.tcp_host}:${catalog.lighting.tcp_port}`
    : "—";
  const lightConnected = lightStatus?.tcp_connected ?? false;
  const videoHolding = Boolean(holdStatus?.active && holdStatus.send_visual);
  const soundHolding = Boolean(holdStatus?.active && holdStatus.send_sound);

  return (
    <section className="card col oscTestPanel">
      <h2>Technik-Test</h2>
      <p className="textMuted" style={{ marginTop: 0 }}>
        Video, Sound und Licht jeweils einzeln testen — wie am Licht-Pult: Signal senden, halten oder stoppen.
        {dryRun ? <span className="oscTestWarn"> · DRY-RUN aktiv</span> : null}
      </p>

      <h3 style={{ margin: "0 0 0.5rem" }}>Video</h3>
      <p className="textMuted" style={{ marginTop: 0 }}>
        Ziel: <code>{videoTarget}</code>
        {videoUsesPixera ? " · Testclip auf RZ21 (Front)" : null}
      </p>

      <p className={videoHolding ? "oscTestActive" : "textMuted"} role="status">
        <strong>Status:</strong>{" "}
        {videoHolding ? `halten · Clip ${holdStatus?.clip_id}` : "inaktiv"}
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

      <hr style={{ width: "100%", border: "none", borderTop: "1px solid var(--border)", margin: "1.25rem 0" }} />

      <h3 style={{ margin: "0 0 0.5rem" }}>Sound</h3>
      <p className="textMuted" style={{ marginTop: 0 }}>
        Ziel: <code>{soundTarget}</code>
        {catalog?.sound?.output === "midi" ? " · Note On/Off an Ableton" : null}
      </p>

      <p className={soundHolding ? "oscTestActive" : "textMuted"} role="status">
        <strong>Status:</strong>{" "}
        {soundHolding ? `halten · ${holdStatus?.sound_cue_id}` : "inaktiv"}
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

      <hr style={{ width: "100%", border: "none", borderTop: "1px solid var(--border)", margin: "1.25rem 0" }} />

      <h3 style={{ margin: "0 0 0.5rem" }}>Licht</h3>
      <p className="textMuted" style={{ marginTop: 0 }}>
        EOS TCP <code>{lightTcpTarget}</code>: Socket verbinden, dann binäres OSC (4-Byte-Längenpräfix) auf
        derselben Verbindung — <code>/eos/chan/N/full</code> · Stopp: <code>/eos/key/out</code>
      </p>

      <p className={lightConnected ? "oscTestActive" : "textMuted"} role="status">
        <strong>TCP:</strong> {lightConnected ? "verbunden" : "nicht verbunden"}
        {lightStatus?.scene_id ? (
          <span> · Signal: {formatLightChannelLabel(
            catalog?.lights.find((l) => l.id === lightStatus.scene_id) ?? {
              id: lightStatus.scene_id,
              description: "",
              moods: [],
              fade_time: 0
            }
          )}{lightStatus.hold_active ? " (halten)" : ""}</span>
        ) : null}
      </p>

      <div className="row oscTestActions">
        <button type="button" className="machineStartBtn" disabled={lightLoading || lightConnected} onClick={() => void connectLight()}>
          1. Verbindung aufbauen
        </button>
        <button type="button" disabled={lightLoading || !lightConnected} onClick={() => void disconnectLight()}>
          Verbindung trennen
        </button>
      </div>

      <label className="oscTestChannel" style={{ marginTop: "0.75rem" }}>
        <span>2. Licht-Szene</span>
        <select
          value={lightId}
          onChange={(e) => setLightId(e.target.value)}
          disabled={lightLoading || !lightConnected}
        >
          {(catalog?.lights ?? []).filter((l) => l.id !== "blackout").map((l) => (
            <option key={l.id} value={l.id}>{formatLightChannelLabel(l)}</option>
          ))}
        </select>
      </label>

      <div className="row oscTestActions">
        <button type="button" disabled={lightLoading || !lightConnected} onClick={() => void sendLight()}>
          Signal senden
        </button>
        <button type="button" disabled={lightLoading || !lightConnected} onClick={() => void holdLight()}>
          Signal halten
        </button>
        <button type="button" className="oscTestStopBtn" disabled={lightLoading || !lightConnected} onClick={() => void stopLight()}>
          Signal aus (/eos/key/out)
        </button>
      </div>

      {error ? <div className="textError" role="alert">{error}</div> : null}
    </section>
  );
}
