"use client";

import { useCallback, useEffect, useState } from "react";

import {
  createExtraLight,
  createLightInventoryGroup,
  deleteLightInventoryGroup,
  fetchLightInventoryAdmin,
  patchLightChannelPolicy,
  patchLightInventoryGroup,
  type LightInventoryAdminResponse,
  type LightInventoryGroup
} from "@/lib/api/media";

function parseChannelList(raw: string): string[] {
  return raw
    .split(/[,;\s]+/)
    .map((c) => c.trim())
    .filter(Boolean);
}

function parseBlockedChannels(raw: string): number[] {
  const out: number[] = [];
  for (const token of parseChannelList(raw)) {
    const n = Number(token);
    if (!Number.isInteger(n) || n <= 0) {
      throw new Error(`Ungültiger Kanal: ${token}`);
    }
    out.push(n);
  }
  return [...new Set(out)].sort((a, b) => a - b);
}

export function LightInventoryPanel() {
  const [data, setData] = useState<LightInventoryAdminResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [blockedInput, setBlockedInput] = useState("");
  const [groupId, setGroupId] = useState("");
  const [groupChannels, setGroupChannels] = useState("");
  const [groupLocation, setGroupLocation] = useState("");

  const reload = useCallback(async () => {
    const next = await fetchLightInventoryAdmin();
    setData(next);
    setBlockedInput(next.blocked_channels.join(", "));
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

  async function onSaveBlocked() {
    const blocked = parseBlockedChannels(blockedInput);
    await patchLightChannelPolicy({ blocked_channels: blocked });
  }

  async function onAddGroup() {
    const channels = parseChannelList(groupChannels);
    if (!channels.length) throw new Error("Mindestens einen EOS-Channel angeben");
    await createLightInventoryGroup({
      id: groupId.trim() || undefined,
      channels,
      location: groupLocation.trim()
    });
    setGroupId("");
    setGroupChannels("");
    setGroupLocation("");
  }

  async function onPromoteToScene(group: LightInventoryGroup) {
    await createExtraLight({
      id: group.id,
      description: group.location
        ? `${group.location} — ${group.channels.join(", ")}`
        : group.channels.join(", "),
      channels: group.channels,
      dramaturgy_active: true
    });
  }

  if (!data) {
    return (
      <section className="card col">
        <h2>Licht-Kanäle &amp; Gruppen</h2>
        <p className="textMuted">{error || "Laden …"}</p>
      </section>
    );
  }

  return (
    <section className="card col">
      <div className="pageHeader" style={{ marginBottom: 0 }}>
        <h2>Licht-Kanäle &amp; Gruppen</h2>
      </div>
      <p className="textMuted">
        Inventar der EOS-Kanäle/Gruppen ({data.venue || "Venue"}). Deaktivierte Gruppen und gesperrte
        Kanäle werden beim Verteilen und am Pult nicht angesteuert. Über „Als Licht-Cue“ steht eine
        Gruppe der Maschine zur Auswahl.
      </p>
      {data.notes ? <p className="textMuted">{data.notes}</p> : null}
      {error ? (
        <p className="textError" role="alert">
          {error}
        </p>
      ) : null}

      <form
        className="col"
        style={{ gap: "0.5rem" }}
        onSubmit={(e) => {
          e.preventDefault();
          void run(onSaveBlocked);
        }}
      >
        <h3>Gesperrte Kanäle (Burgtheater)</h3>
        <label className="col">
          Nicht ansteuern (Komma getrennt)
          <input
            value={blockedInput}
            onChange={(e) => setBlockedInput(e.target.value)}
            placeholder="z. B. 11, 19, 22"
            disabled={busy}
          />
        </label>
        <button type="submit" className="btn" disabled={busy}>
          Sperrliste speichern
        </button>
      </form>

      <form
        className="col"
        style={{ gap: "0.5rem" }}
        onSubmit={(e) => {
          e.preventDefault();
          void run(onAddGroup);
        }}
      >
        <h3>Gruppe hinzufügen</h3>
        <label className="col">
          ID (optional)
          <input
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
            placeholder="z. B. special_links"
            disabled={busy}
          />
        </label>
        <label className="col">
          EOS-Channels
          <input
            value={groupChannels}
            onChange={(e) => setGroupChannels(e.target.value)}
            placeholder="z. B. 401-404, 410"
            disabled={busy}
          />
        </label>
        <label className="col">
          Ort / Beschreibung
          <input
            value={groupLocation}
            onChange={(e) => setGroupLocation(e.target.value)}
            placeholder="z. B. Vorbühne links"
            disabled={busy}
          />
        </label>
        <button type="submit" className="btn" disabled={busy}>
          Gruppe anlegen
        </button>
      </form>

      <div className="cueAdminTableWrap">
        <table className="cueAdminTable">
          <thead>
            <tr>
              <th>Gruppe</th>
              <th>Kanäle</th>
              <th>Ort</th>
              <th>Status</th>
              <th>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {data.groups.map((group) => (
              <tr key={group.id} className={group.enabled ? undefined : "isRemoved"}>
                <td>
                  <strong>{group.id}</strong>
                  {group.fixtures.length ? (
                    <div className="textMuted">{group.fixtures.join(", ")}</div>
                  ) : null}
                </td>
                <td>{group.channels.join(", ") || "—"}</td>
                <td>{group.location || "—"}</td>
                <td>{group.enabled ? "aktiv" : "deaktiviert"}</td>
                <td>
                  <div className="row" style={{ gap: "0.35rem", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn secondary"
                      disabled={busy}
                      onClick={() =>
                        void run(() => patchLightInventoryGroup(group.id, !group.enabled))
                      }
                    >
                      {group.enabled ? "Deaktivieren" : "Aktivieren"}
                    </button>
                    <button
                      type="button"
                      className="btn secondary"
                      disabled={busy || !group.enabled}
                      onClick={() => void run(() => onPromoteToScene(group))}
                      title="Als verteilbaren Licht-Cue anlegen"
                    >
                      Als Licht-Cue
                    </button>
                    <button
                      type="button"
                      className="btn secondary"
                      disabled={busy}
                      onClick={() => {
                        if (!window.confirm(`Gruppe „${group.id}“ aus dem Inventar löschen?`)) {
                          return;
                        }
                        void run(() => deleteLightInventoryGroup(group.id));
                      }}
                    >
                      Löschen
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
