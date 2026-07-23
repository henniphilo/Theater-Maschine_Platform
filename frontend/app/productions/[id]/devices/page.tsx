"use client";

import type { Route } from "next";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  createDevice,
  deleteDevice,
  listDevices,
  testDeviceConnection
} from "@/lib/api/devices";
import { fetchProduction } from "@/lib/api/productions";
import type { AdapterType, Device, DeviceConnectionTestResult } from "@/lib/types/device";
import {
  ADAPTER_TYPE_LABELS,
  ADAPTER_TYPES,
  defaultConfigurationFor
} from "@/lib/types/device";
import type { Production } from "@/lib/types/production";

export default function ProductionDevicesPage() {
  const params = useParams();
  const productionId = typeof params.id === "string" ? params.id : "";

  const [production, setProduction] = useState<Production | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [testResult, setTestResult] = useState<DeviceConnectionTestResult | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [adapterType, setAdapterType] = useState<AdapterType>("dry_run");
  const [configurationJson, setConfigurationJson] = useState(
    JSON.stringify(defaultConfigurationFor("dry_run"), null, 2)
  );
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(async () => {
    if (!productionId) return;
    setError(null);
    try {
      const [prod, rows] = await Promise.all([
        fetchProduction(productionId),
        listDevices({ productionId, includeGlobal: true })
      ]);
      setProduction(prod);
      setDevices(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
      setProduction(null);
      setDevices([]);
    } finally {
      setLoading(false);
    }
  }, [productionId]);

  useEffect(() => {
    setLoading(true);
    void refresh();
  }, [refresh]);

  useEffect(() => {
    setConfigurationJson(JSON.stringify(defaultConfigurationFor(adapterType), null, 2));
  }, [adapterType]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!productionId || creating || !name.trim()) return;
    setCreating(true);
    setError(null);
    setTestResult(null);
    try {
      const configuration = JSON.parse(configurationJson) as Record<string, unknown>;
      await createDevice({
        production_id: productionId,
        name: name.trim(),
        adapter_type: adapterType,
        configuration
      });
      setName("");
      setAdapterType("dry_run");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anlegen fehlgeschlagen");
    } finally {
      setCreating(false);
    }
  }

  async function onTest(device: Device) {
    setBusyId(device.id);
    setError(null);
    setTestResult(null);
    try {
      const result = await testDeviceConnection(device.id, productionId);
      setTestResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verbindungstest fehlgeschlagen");
    } finally {
      setBusyId(null);
    }
  }

  async function onDelete(device: Device) {
    if (!window.confirm(`Gerät „${device.name}“ löschen?`)) return;
    setError(null);
    try {
      await deleteDevice(device.id, productionId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen");
    }
  }

  if (loading) {
    return (
      <main className="container col">
        <p className="textMuted">Laden…</p>
      </main>
    );
  }

  if (!production) {
    return (
      <main className="container col">
        <p className="textError">{error ?? "Produktion nicht gefunden"}</p>
        <Link href="/productions">Zurück zur Liste</Link>
      </main>
    );
  }

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Geräte</h1>
      </div>
      <p>
        <Link href={`/productions/${production.id}`}>← {production.name}</Link>
      </p>
      <p className="textMuted">
        Technische Ausgaben hinter Adapter-Schnittstellen. Neue Geräte starten als Dry Run.
        Hosts und Secrets erscheinen nicht in der API-Antwort.
      </p>

      {error ? <p className="textError">{error}</p> : null}

      <section className="col" style={{ gap: "var(--space-3)", maxWidth: 560 }}>
        <h2>Gerät anlegen</h2>
        <form className="col" style={{ gap: "var(--space-3)" }} onSubmit={(e) => void onCreate(e)}>
          <label className="col" style={{ gap: 4 }}>
            <span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Adapter</span>
            <select
              value={adapterType}
              onChange={(e) => setAdapterType(e.target.value as AdapterType)}
            >
              {ADAPTER_TYPES.map((t) => (
                <option key={t} value={t}>
                  {ADAPTER_TYPE_LABELS[t]}
                </option>
              ))}
            </select>
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Konfiguration (JSON — wird gespeichert, sensible Werte nicht zurückgelesen)</span>
            <textarea
              value={configurationJson}
              onChange={(e) => setConfigurationJson(e.target.value)}
              rows={8}
              style={{ fontFamily: "ui-monospace, monospace" }}
            />
          </label>
          <button type="submit" disabled={creating || !name.trim()}>
            {creating ? "Anlegen…" : "Gerät anlegen"}
          </button>
        </form>
      </section>

      <section className="col" style={{ gap: "var(--space-3)" }}>
        <h2>Geräteliste</h2>
        {devices.length === 0 ? (
          <p className="textMuted">Noch keine Geräte.</p>
        ) : (
          <ul className="col" style={{ gap: "var(--space-2)", listStyle: "none", padding: 0 }}>
            {devices.map((device) => (
              <li
                key={device.id}
                style={{
                  border: "1px solid var(--color-border)",
                  padding: "var(--space-3)",
                  borderRadius: "var(--radius-md)",
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "var(--space-3)",
                  alignItems: "center",
                  justifyContent: "space-between"
                }}
              >
                <div className="col" style={{ gap: 2 }}>
                  <strong>{device.name}</strong>
                  <span className="textMuted">
                    {ADAPTER_TYPE_LABELS[device.adapter_type]}
                    {device.enabled ? "" : " · deaktiviert"}
                    {device.has_sensitive_configuration ? " · Config gesetzt" : ""}
                    {device.production_id == null ? " · global" : ""}
                  </span>
                  {device.configuration_keys.length > 0 ? (
                    <span className="textMuted" style={{ fontSize: "0.85em" }}>
                      Keys: {device.configuration_keys.join(", ")}
                    </span>
                  ) : null}
                </div>
                <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                  <Link href={`/productions/${production.id}/devices/${device.id}` as Route}>
                    Details
                  </Link>
                  <button
                    type="button"
                    disabled={busyId === device.id}
                    onClick={() => void onTest(device)}
                  >
                    Verbindung testen
                  </button>
                  <button type="button" onClick={() => void onDelete(device)}>
                    Löschen
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {testResult ? (
        <section className="col" style={{ gap: "var(--space-2)" }}>
          <h2>Verbindungstest</h2>
          <p>
            {testResult.ok ? "OK" : "Fehler"}
            {testResult.dry_run ? " (dry-run)" : ""} — {testResult.message}
          </p>
          <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
            {JSON.stringify(testResult.details, null, 2)}
          </pre>
        </section>
      ) : null}
    </main>
  );
}
