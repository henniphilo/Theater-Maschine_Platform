"use client";

import { useEffect, useRef } from "react";

import {
  pollRemoteTransport,
  type RemoteTransportAction
} from "@/lib/api/director";

const POLL_MS = 450;

type RemoteTransportHandlers = {
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  enabled?: boolean;
};

/**
 * Stage Aufführung tab: poll backend mailbox and run local transport handlers
 * so TTS stays on this Mac while a phone only posts commands.
 */
export function useRemoteTransportListener({
  onPlay,
  onPause,
  onStop,
  enabled = true
}: RemoteTransportHandlers): void {
  const handlersRef = useRef({ onPlay, onPause, onStop });
  handlersRef.current = { onPlay, onPause, onStop };

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    let cancelled = false;
    let timer: number | undefined;

    const tick = async () => {
      try {
        const status = await pollRemoteTransport({ consume: true, heartbeat: true });
        if (cancelled) return;
        const action = status.pending?.action as RemoteTransportAction | undefined;
        if (action === "play") handlersRef.current.onPlay();
        else if (action === "pause") handlersRef.current.onPause();
        else if (action === "stop") handlersRef.current.onStop();
      } catch {
        /* backend briefly unavailable — keep polling */
      }
      if (!cancelled) {
        timer = window.setTimeout(() => {
          void tick();
        }, POLL_MS);
      }
    };

    void tick();
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [enabled]);
}
