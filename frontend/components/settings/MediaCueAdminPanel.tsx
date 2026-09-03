"use client";

import { useCallback, useEffect, useState } from "react";

import {
  createExtraLight,
  createExtraSound,
  createExtraVideo,
  deleteExtraCue,
  fetchCueAdmin,
  patchCueAdmin,
  type CueAdminLightRow,
  type CueAdminResponse,
  type CueAdminSoundRow,
  type CueAdminVideoRow,
  type CueKind
} from "@/lib/api/media";

type Tab = "video" | "sound" | "light";

function StatusBadge({ active, removed }: { active: boolean; removed: boolean }) {
  if (removed) return <span className="textMuted">OSC entfernt</span>;
  if (!active) return <span className="textMuted">LLM gesperrt</span>;
  return <span>aktiv</span>;
}

export function MediaCueAdminPanel() {
  const [data, setData] = useState<CueAdminResponse | null>(null);
  const [tab, setTab] = useState<Tab>("video");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [pixeraName, setPixeraName] = useState("");
  const [allProjectors, setAllProjectors] = useState(true);
  const [selectedProjectors, setSelectedProjectors] = useState<string[]>([]);

  const [soundName, setSoundName] = useState("");
  const [midiNote, setMidiNote] = useState(60);

  const [lightId, setLightId] = useState("");
  const [lightDesc, setLightDesc] = useState("");
  const [lightChannels, setLightChannels] = useState("");
  const [lightGroups, setLightGroups] = useState("");

  const reload = useCallback(async () => {
    const next = await fetchCueAdmin();
    setData(next);
  }, []);

  useEffect(() => {
    void reload().catch((err) => {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
    });
  }, [reload]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Aktion fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  function toggleProjector(id: string) {
    setSelectedProjectors((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  async function onAddVideo() {
    const name = pixeraName.trim();
    if (!name) throw new Error("Pixera-Dateiname fehlt");
    await createExtraVideo({
      pixera_name: name,
      projectors: allProjectors ? ["*"] : selectedProjectors
    });
    setPixeraName("");
  }

  async function onAddSound() {
    const name = soundName.trim();
    if (!name) throw new Error("Soundname fehlt");
    if (midiNote < 0 || midiNote > 127) throw new Error("MIDI-Note 0–127");
    await createExtraSound({ soundname: name, midi_note: midiNote });
    setSoundName("");
  }

  async function onAddLight() {
    const channels = lightChannels
      .split(/[,;\s]+/)
      .map((c) => c.trim())
      .filter(Boolean);
    const groups = lightGroups
      .split(/[,;\s]+/)
      .map((c) => c.trim())
      .filter(Boolean);
    if (!channels.length && !groups.length) {
      throw new Error("Mindestens einen EOS-Channel oder eine EOS-Gruppe angeben");
    }
    await createExtraLight({
      id: lightId.trim() || undefined,
      description: lightDesc.trim() || lightId.trim(),
      channels,
      groups
    });
    setLightId("");
    setLightDesc("");
    setLightChannels("");
    setLightGroups("");
  }

  function rowActions(kind: CueKind, row: { id: string; source: string; dramaturgy_active: boolean; removed: boolean }) {
    return (
      <div className="row" style={{ gap: "0.35rem", flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn secondary"
          disabled={busy || row.removed}
          onClick={() =>
            void run(() =>
              patchCueAdmin(kind, row.id, { dramaturgy_active: !row.dramaturgy_active })
            )
          }
        >
          {row.dramaturgy_active ? "LLM sperren" : "LLM freigeben"}
        </button>
        <button
          type="button"
          className="btn secondary"
          disabled={busy}
          onClick={() => void run(() => patchCueAdmin(kind, row.id, { removed: !row.removed }))}
        >
          {row.removed ? "OSC wiederherstellen" : "Aus OSC entfernen"}
        </button>
        {row.source === "extra" ? (
          <button
            type="button"
            className="btn secondary"
            disabled={busy}
            onClick={() => {
              if (!window.confirm(`Extra „${row.id}“ endgültig löschen?`)) return;
              void run(() => deleteExtraCue(kind, row.id));
            }}
          >
            Extra löschen
          </button>
        ) : null}
      </div>
    );
  }

  if (!data) {
    return (
      <section className="card col">
        <h2>Medien-Cues</h2>
        <p className="textMuted">{error || "Laden …"}</p>
      </section>
    );
  }

  return (
    <section className="card col mediaCueAdmin">
      <div className="pageHeader" style={{ marginBottom: 0 }}>
        <h2>Medien-Cues</h2>
      </div>
      <p className="textMuted">
        Zusätzliche Video-/Sound-/Licht-Namen für OSC (gespeichert in data/extra_media_overrides.json). LLM
        sperren lässt den Cue manuell nutzbar; Aus OSC entfernen nimmt ihn aus Allowlist und Technik-Picker.
        Avatare sind hier nicht gelistet.
      </p>
      {error ? (
        <p className="textError" role="alert">
          {error}
        </p>
      ) : null}

      <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
        {(
          [
            ["video", "Video"],
            ["sound", "Sound"],
            ["light", "Licht"]
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? "btn" : "btn secondary"}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "video" ? (
        <>
          <form
            className="col"
            style={{ gap: "0.5rem" }}
            onSubmit={(e) => {
              e.preventDefault();
              void run(onAddVideo);
            }}
          >
            <h3>Video hinzufügen</h3>
            <label className="col">
              Pixera-Dateiname
              <input
                value={pixeraName}
                onChange={(e) => setPixeraName(e.target.value)}
                placeholder="z. B. MeinClip"
                disabled={busy}
              />
            </label>
            <label className="row" style={{ gap: "0.5rem", alignItems: "center" }}>
              <input
                type="checkbox"
                checked={allProjectors}
                onChange={(e) => setAllProjectors(e.target.checked)}
                disabled={busy}
              />
              Alle Projektoren
            </label>
            {!allProjectors ? (
              <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap" }}>
                {data.projectors.map((p) => (
                  <label key={p.id} className="row" style={{ gap: "0.35rem", alignItems: "center" }}>
                    <input
                      type="checkbox"
                      checked={selectedProjectors.includes(p.id)}
                      onChange={() => toggleProjector(p.id)}
                      disabled={busy}
                    />
                    {p.name || p.id}
                  </label>
                ))}
              </div>
            ) : null}
            <button type="submit" className="btn" disabled={busy}>
              Video-Cue anlegen
            </button>
          </form>

          <div className="cueAdminTableWrap">
            <table className="cueAdminTable">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Projektoren</th>
                  <th>Quelle</th>
                  <th>Status</th>
                  <th>Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {data.videos.map((row: CueAdminVideoRow) => (
                  <tr key={row.id} className={row.removed ? "isRemoved" : undefined}>
                    <td>
                      <strong>{row.label || row.pixera_name}</strong>
                      <div className="textMuted">{row.id}</div>
                    </td>
                    <td>{row.projectors.join(", ") || "—"}</td>
                    <td>{row.source}</td>
                    <td>
                      <StatusBadge active={row.dramaturgy_active} removed={row.removed} />
                    </td>
                    <td>{rowActions("video", row)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {tab === "sound" ? (
        <>
          <form
            className="col"
            style={{ gap: "0.5rem" }}
            onSubmit={(e) => {
              e.preventDefault();
              void run(onAddSound);
            }}
          >
            <h3>Sound hinzufügen</h3>
            <p className="textMuted">
              MIDI-Note am Sounddesk (Ableton) zuweisen — dieselbe Note wie hier eintragen, sonst trifft der Cue
              keinen Clip.
            </p>
            <label className="col">
              Soundname
              <input
                value={soundName}
                onChange={(e) => setSoundName(e.target.value)}
                placeholder="z. B. Regen-Loop"
                disabled={busy}
              />
            </label>
            <label className="col">
              MIDI-Note (0–127)
              <input
                type="number"
                min={0}
                max={127}
                value={midiNote}
                onChange={(e) => setMidiNote(Number(e.target.value))}
                disabled={busy}
              />
            </label>
            <button type="submit" className="btn" disabled={busy}>
              Sound-Cue anlegen
            </button>
          </form>

          <div className="cueAdminTableWrap">
            <table className="cueAdminTable">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>MIDI</th>
                  <th>Quelle</th>
                  <th>Status</th>
                  <th>Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {data.sounds.map((row: CueAdminSoundRow) => (
                  <tr key={row.id} className={row.removed ? "isRemoved" : undefined}>
                    <td>
                      <strong>{row.soundname || row.label || row.id}</strong>
                      <div className="textMuted">{row.ableton_hint || row.id}</div>
                    </td>
                    <td>{row.midi_note ?? "—"}</td>
                    <td>{row.source}</td>
                    <td>
                      <StatusBadge active={row.dramaturgy_active} removed={row.removed} />
                    </td>
                    <td>{rowActions("sound", row)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {tab === "light" ? (
        <>
          <form
            className="col"
            style={{ gap: "0.5rem" }}
            onSubmit={(e) => {
              e.preventDefault();
              void run(onAddLight);
            }}
          >
            <h3>Licht-Cue hinzufügen</h3>
            <p className="textMuted">
              Licht-Szenen mit EOS-Channels und/oder EOS-Gruppen — die Maschine greift beim Verteilen
              auf aktive (nicht entfernte) Cues zu.
            </p>
            <label className="col">
              ID (optional)
              <input
                value={lightId}
                onChange={(e) => setLightId(e.target.value)}
                placeholder="z. B. warm_special"
                disabled={busy}
              />
            </label>
            <label className="col">
              Beschreibung
              <input
                value={lightDesc}
                onChange={(e) => setLightDesc(e.target.value)}
                placeholder="Kurze Beschreibung"
                disabled={busy}
              />
            </label>
            <label className="col">
              EOS-Channels (Komma getrennt)
              <input
                value={lightChannels}
                onChange={(e) => setLightChannels(e.target.value)}
                placeholder="z. B. 71-74, 91"
                disabled={busy}
              />
            </label>
            <label className="col">
              EOS-Gruppen (Komma getrennt)
              <input
                value={lightGroups}
                onChange={(e) => setLightGroups(e.target.value)}
                placeholder="z. B. 2, 13"
                disabled={busy}
              />
            </label>
            <button type="submit" className="btn" disabled={busy}>
              Licht-Cue anlegen
            </button>
          </form>

          <div className="cueAdminTableWrap">
            <table className="cueAdminTable">
              <thead>
                <tr>
                  <th>Szene</th>
                  <th>Kanäle</th>
                  <th>Gruppen</th>
                  <th>Quelle</th>
                  <th>Status</th>
                  <th>Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {data.lights.map((row: CueAdminLightRow) => (
                  <tr key={row.id} className={row.removed ? "isRemoved" : undefined}>
                    <td>
                      <strong>{row.id}</strong>
                      <div className="textMuted">{row.description}</div>
                    </td>
                    <td>{row.channels.join(", ") || "—"}</td>
                    <td>{row.groups.length ? `Gr. ${row.groups.join(", ")}` : "—"}</td>
                    <td>{row.source}</td>
                    <td>
                      <StatusBadge active={row.dramaturgy_active} removed={row.removed} />
                    </td>
                    <td>{rowActions("light", row)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  );
}
