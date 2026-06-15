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
  postTechnikStart,
  postTechnikStop,
  type LightDeskStatus,
  type TechnikHoldStatus
} from "@/lib/api/director";
import { fetchMediaCatalog } from "@/lib/api/media";
import type { MediaCatalog } from "@/lib/types/media";
import { formatLightChannelLabel } from "@/lib/types/media";
import { formatMidiTrigger } from "@/lib/midi/format";

type Channel = "visual" | "sound";

export function OscTestPanel() {
  const [catalog, setCatalog] = useState<MediaCatalog | null>(null);
  const [clipId, setClipId] = useState("clyde");
  const [soundId, setSoundId] = useState("maschinen_grundader");
  const [lightId, setLightId] = useState("vorbuehnenzug");
  const [sendVisual, setSendVisual] = useState(true);
  const [sendSound, setSendSound] = useState(true);
  const [loading, setLoading] = useState(false);
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

  const startHold = useCallback(
    async (channels: Channel[] | "all") => {
      setError("");
      setLoading(true);
      const visual = channels === "all" ? sendVisual : channels.includes("visual");
      const sound = channels === "all" ? sendSound : channels.includes("sound");

      if (!visual && !sound) {
        setError("Mindestens Video oder Sound auswählen.");
        setLoading(false);
        return;
      }

      try {
        const result = await postTechnikStart({
          clip_id: clipId,
          sound_cue_id: soundId,
          send_visual: visual,
          send_sound: sound,
          send_light: false,
          stagger: false
        });
        setHoldStatus(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Technik-Start fehlgeschlagen");
      } finally {
        setLoading(false);
      }
    },
    [clipId, sendSound, sendVisual, soundId]
  );

  const stopHold = useCallback(async (channels?: Channel[] | "all") => {
    setError("");
    setLoading(true);
    const all = channels === "all" || channels === undefined;
    try {
      const result = await postTechnikStop({
        send_visual: all || channels?.includes("visual"),
        send_sound: all || channels?.includes("sound"),
        send_light: false
      });
      setHoldStatus(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Technik-Stopp fehlgeschlagen");
    } finally {
      setLoading(false);
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

  const oscTarget = catalog?.touchdesigner
    ? `${catalog.touchdesigner.osc_host}:${catalog.touchdesigner.osc_port}`
    : "—";
  const soundTarget =
    catalog?.sound?.output === "midi" || catalog?.sound?.output === "both"
      ? `MIDI ${catalog.sound.midi_port || "auto"} · Kanal ${catalog.sound.midi_channel}`
      : catalog?.sound
        ? `OSC ${catalog.sound.osc_host}:${catalog.sound.osc_port}`
        : oscTarget;
  const lightTcpTarget = catalog?.lighting
    ? `TCP ${catalog.lighting.tcp_host}:${catalog.lighting.tcp_port}`
    : "—";
  const dryRun = catalog?.touchdesigner?.osc_dry_run ?? false;
  const lightConnected = lightStatus?.tcp_connected ?? false;
  const lightBusy = loading || lightLoading;

  const activeLabel = holdStatus?.active
    ? [
        holdStatus.send_visual ? `Video (${holdStatus.clip_id})` : null,
        holdStatus.send_sound ? `Sound (${holdStatus.sound_cue_id})` : null
      ]
        .filter(Boolean)
        .join(" · ")
    : null;

  return (
    <section className="card col oscTestPanel">
      <h2>OSC Technik-Test</h2>
      <p className="textMuted" style={{ marginTop: 0 }}>
        Video: <code>{oscTarget}</code>
        {dryRun ? <span className="oscTestWarn"> · DRY-RUN</span> : null}
        {" · "}
        Sound: <code>{soundTarget}</code>
        {!dryRun && catalog?.sound?.output !== "osc" ? <span> · aktiv</span> : null}
      </p>

      {activeLabel ? (
        <p className="oscTestActive" role="status">
          <strong>Aktiv:</strong> {activeLabel}
        </p>
      ) : null}

      <div className="oscTestGrid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <label className="oscTestChannel">
          <input type="checkbox" checked={sendVisual} onChange={(e) => setSendVisual(e.target.checked)} />
          <span>Video</span>
          <select value={clipId} onChange={(e) => setClipId(e.target.value)} disabled={lightBusy}>
            {(catalog?.videos ?? []).map((v) => (
              <option key={v.id} value={v.id}>{v.id}</option>
            ))}
          </select>
        </label>

        <label className="oscTestChannel">
          <input type="checkbox" checked={sendSound} onChange={(e) => setSendSound(e.target.checked)} />
          <span>Sound</span>
          <select value={soundId} onChange={(e) => setSoundId(e.target.value)} disabled={lightBusy}>
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
      </div>

      <div className="row oscTestActions">
        <button type="button" className="machineStartBtn" disabled={lightBusy} onClick={() => void startHold("all")}>
          Video + Sound starten
        </button>
        <button type="button" disabled={lightBusy} onClick={() => void startHold(["visual"])}>Nur Video</button>
        <button type="button" disabled={lightBusy} onClick={() => void startHold(["sound"])}>Nur Sound</button>
        <button type="button" className="oscTestStopBtn" disabled={lightBusy} onClick={() => void stopHold("all")}>
          Video/Sound stoppen
        </button>
      </div>

      <hr style={{ width: "100%", border: "none", borderTop: "1px solid var(--border)", margin: "1rem 0" }} />

      <h3 style={{ margin: "0 0 0.5rem" }}>Licht (2 Schritte)</h3>
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
        <button type="button" className="machineStartBtn" disabled={lightBusy || lightConnected} onClick={() => void connectLight()}>
          1. Verbindung aufbauen
        </button>
        <button type="button" disabled={lightBusy || !lightConnected} onClick={() => void disconnectLight()}>
          Verbindung trennen
        </button>
      </div>

      <label className="oscTestChannel" style={{ marginTop: "0.75rem" }}>
        <span>2. Licht-Szene</span>
        <select
          value={lightId}
          onChange={(e) => setLightId(e.target.value)}
          disabled={lightBusy || !lightConnected}
        >
          {(catalog?.lights ?? []).filter((l) => l.id !== "blackout").map((l) => (
            <option key={l.id} value={l.id}>{formatLightChannelLabel(l)}</option>
          ))}
        </select>
      </label>

      <div className="row oscTestActions">
        <button type="button" disabled={lightBusy || !lightConnected} onClick={() => void sendLight()}>
          Signal senden
        </button>
        <button type="button" disabled={lightBusy || !lightConnected} onClick={() => void holdLight()}>
          Signal halten
        </button>
        <button type="button" className="oscTestStopBtn" disabled={lightBusy || !lightConnected} onClick={() => void stopLight()}>
          Signal aus (/eos/key/out)
        </button>
      </div>

      {error ? <div className="textError" role="alert">{error}</div> : null}
    </section>
  );
}
