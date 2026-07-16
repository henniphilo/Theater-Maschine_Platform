"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import {
  pollRemoteTransport,
  postRemoteTransport,
  type RemoteTransportAction
} from "@/lib/api/director";

type StatusKind = "idle" | "sending" | "sent" | "error";

export default function RemoteTransportPage() {
  const [listenerConnected, setListenerConnected] = useState(false);
  const [status, setStatus] = useState<StatusKind>("idle");
  const [lastAction, setLastAction] = useState<RemoteTransportAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [origin, setOrigin] = useState("");

  useEffect(() => {
    setOrigin(window.location.origin);
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    const tick = async () => {
      try {
        const snap = await pollRemoteTransport({ consume: false, heartbeat: false });
        if (!cancelled) setListenerConnected(snap.listener_connected);
      } catch {
        if (!cancelled) setListenerConnected(false);
      }
      if (!cancelled) {
        timer = window.setTimeout(() => {
          void tick();
        }, 800);
      }
    };

    void tick();
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);

  const send = useCallback(async (action: RemoteTransportAction) => {
    setStatus("sending");
    setError(null);
    setLastAction(action);
    try {
      const result = await postRemoteTransport(action);
      setListenerConnected(result.listener_connected);
      setStatus("sent");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Senden fehlgeschlagen");
    }
  }, []);

  const statusText =
    status === "sending"
      ? "Sende …"
      : status === "error"
        ? error ?? "Fehler"
        : status === "sent" && lastAction
          ? `${lastAction.toUpperCase()} gesendet`
          : listenerConnected
            ? "Mac verbunden — bereit"
            : "Wartet auf Mac-Aufführungsseite …";

  return (
    <main className="container col remotePage">
      <div className="pageHeader">
        <h1>Remote</h1>
        <span className={listenerConnected ? "liveBadge" : "remoteBadgeOffline"}>
          {listenerConnected ? "Mac live" : "Kein Mac"}
        </span>
      </div>

      <p className="textMuted remoteHint">
        Aufführung auf dem Bühnen-Mac offen lassen. TTS und Cues laufen dort — hier nur Start/Stop.
      </p>

      <div className="remoteStatus" role="status" aria-live="polite">
        {statusText}
      </div>

      <div className="remoteButtons">
        <button
          type="button"
          className="remoteBtn remoteBtnPlay"
          disabled={status === "sending"}
          onClick={() => void send("play")}
        >
          ▶ Play
        </button>
        <button
          type="button"
          className="remoteBtn remoteBtnPause"
          disabled={status === "sending"}
          onClick={() => void send("pause")}
        >
          ⏸ Pause
        </button>
        <button
          type="button"
          className="remoteBtn remoteBtnStop"
          disabled={status === "sending"}
          onClick={() => void send("stop")}
        >
          ⏹ Stop
        </button>
      </div>

      {origin ? (
        <p className="textFaint remoteUrlHint">
          Diese Seite: <code>{origin}/remote</code>
        </p>
      ) : null}

      <p className="textMuted" style={{ fontSize: "0.85rem" }}>
        <Link href="/auffuehrung">Zur Aufführung</Link>
        {" · "}
        <Link href="/director">Director / Not-Aus</Link>
      </p>
    </main>
  );
}
