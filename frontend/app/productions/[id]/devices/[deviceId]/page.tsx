"use client";

import type { Route } from "next";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { fetchDevice, testDeviceConnection } from "@/lib/api/devices";
import { fetchProduction } from "@/lib/api/productions";
import type { Device, DeviceConnectionTestResult } from "@/lib/types/device";
import { ADAPTER_TYPE_LABELS } from "@/lib/types/device";
import type { Production } from "@/lib/types/production";

export default function DeviceDetailPage() {
  const params = useParams();
  const productionId = typeof params.id === "string" ? params.id : "";
  const deviceId = typeof params.deviceId === "string" ? params.deviceId : "";

  const [production, setProduction] = useState<Production | null>(null);
  const [device, setDevice] = useState<Device | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [testResult, setTestResult] = useState<DeviceConnectionTestResult | null>(null);
  const [testing, setTesting] = useState(false);

  const refresh = useCallback(async () => {
    if (!productionId || !deviceId) return;
    setError(null);
    try {
      const [prod, row] = await Promise.all([
        fetchProduction(productionId),
        fetchDevice(deviceId, productionId)
      ]);
      setProduction(prod);
      setDevice(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
      setProduction(null);
      setDevice(null);
    } finally {
      setLoading(false);
    }
  }, [productionId, deviceId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onTest() {
    if (!device) return;
    setTesting(true);
    setError(null);
    setTestResult(null);
    try {
      const result = await testDeviceConnection(device.id, productionId);
      setTestResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verbindungstest fehlgeschlagen");
    } finally {
      setTesting(false);
    }
  }

  if (loading) {
    return (
      <main className="container col">
        <p className="textMuted">Laden…</p>
      </main>
    );
  }

  if (!production || !device) {
    return (
      <main className="container col">
        <p className="textError">{error ?? "Gerät nicht gefunden"}</p>
        <Link href={`/productions/${productionId}/devices` as Route}>Zurück</Link>
      </main>
    );
  }

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>{device.name}</h1>
      </div>
      <p>
        <Link href={`/productions/${production.id}/devices` as Route}>← Geräte</Link>
      </p>
      {error ? <p className="textError">{error}</p> : null}

      <dl className="col" style={{ gap: "var(--space-2)" }}>
        <div>
          <dt className="textMuted">Adapter</dt>
          <dd>{ADAPTER_TYPE_LABELS[device.adapter_type]}</dd>
        </div>
        <div>
          <dt className="textMuted">Status</dt>
          <dd>{device.enabled ? "aktiviert" : "deaktiviert"}</dd>
        </div>
        <div>
          <dt className="textMuted">Öffentliche Konfiguration</dt>
          <dd>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
              {JSON.stringify(device.configuration, null, 2)}
            </pre>
          </dd>
        </div>
        <div>
          <dt className="textMuted">Gespeicherte Keys (Werte ausgeblendet)</dt>
          <dd>{device.configuration_keys.join(", ") || "—"}</dd>
        </div>
      </dl>

      <button type="button" disabled={testing} onClick={() => void onTest()}>
        {testing ? "Teste…" : "Verbindung testen"}
      </button>

      {testResult ? (
        <section className="col" style={{ gap: "var(--space-2)" }}>
          <h2>Ergebnis</h2>
          <p>
            {testResult.ok ? "OK" : "Fehler"}
            {testResult.dry_run ? " (dry-run)" : ""} — {testResult.message}
          </p>
        </section>
      ) : null}
    </main>
  );
}
