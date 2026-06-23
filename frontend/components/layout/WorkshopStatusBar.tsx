"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  subscribeWorkshopRunner,
  setWorkshopTtsAvailable,
  workshopStatusLabel,
  type WorkshopRunnerState
} from "@/features/dramaturgy/workshopRunner";
import {
  bufferStatusLabel,
  subscribeScriptBuffer,
  type ScriptBufferState
} from "@/features/show/performanceBuffer";
import { workshopPhaseLabel, type WorkshopPhase } from "@/lib/types/part1";
import { fetchTTSStatus } from "@/lib/api/client";

export function WorkshopStatusBar() {
  const [workshop, setWorkshop] = useState<WorkshopRunnerState | null>(null);
  const [buffer, setBuffer] = useState<ScriptBufferState | null>(null);

  useEffect(() => subscribeWorkshopRunner(setWorkshop), []);
  useEffect(() => subscribeScriptBuffer(setBuffer), []);
  useEffect(() => {
    fetchTTSStatus()
      .then((status) => setWorkshopTtsAvailable(status.available))
      .catch(() => undefined);
  }, []);

  if (!workshop || workshop.status === "idle") return null;

  const label = workshopStatusLabel(workshop, buffer);
  if (!label) return null;

  const phaseLabel =
    workshop.workshopPhase && workshop.status === "running"
      ? workshopPhaseLabel(workshop.workshopPhase as WorkshopPhase)
      : null;

  const isError = workshop.status === "error";
  const scriptId = workshop.script?.id;

  return (
    <div
      className={isError ? "workshopStatusBar workshopStatusBarError" : "workshopStatusBar"}
      role="status"
      style={{
        fontSize: "0.85rem",
        padding: "0.35rem 0.75rem",
        marginBottom: "0.5rem",
        borderRadius: 6,
        background: isError ? "rgba(200,60,60,0.12)" : "rgba(107,140,255,0.12)",
        border: `1px solid ${isError ? "rgba(200,60,60,0.35)" : "rgba(107,140,255,0.35)"}`
      }}
    >
      {phaseLabel && workshop.status === "running" ? (
        <span>
          <strong>{phaseLabel}</strong>
          {workshop.previewStatus ? ` · ${workshop.previewStatus}` : ""}
          {" · "}
        </span>
      ) : null}
      <span>{label}</span>
      {workshop.status === "running" ? (
        <span className="textMuted"> — du kannst zu anderen Seiten wechseln; der Workshop läuft weiter.</span>
      ) : null}
      {buffer && buffer.status === "buffering" && workshop.status === "done" ? (
        <span className="textMuted"> · {bufferStatusLabel(buffer)}</span>
      ) : null}
      {scriptId ? (
        <>
          {" "}
          <Link href={`/dramaturgie`} style={{ marginLeft: 4 }}>
            Dramaturgie
          </Link>
          {workshop.status === "done" ? (
            <>
              {" · "}
              <Link href={`/auffuehrung?id=${scriptId}`}>Aufführung</Link>
            </>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
