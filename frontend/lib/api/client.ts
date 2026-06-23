import { DirectorPayload } from "@/lib/types/director";
import { DebateRequest, DebateStreamEvent } from "@/lib/types/chat";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type DebateStreamHandlers = {
  onThinking: (speaker: "openai" | "anthropic") => void;
  onTurn: (turn: {
    speaker: "openai" | "anthropic";
    content: string;
    model: string;
    created_at: string;
    director?: DirectorPayload;
  }) => void;
  onDone: (data: { conversation_id: string; topic: string }) => void;
  onError: (detail: string) => void;
};

export async function streamDebate(payload: DebateRequest, handlers: DebateStreamHandlers): Promise<void> {
  const res = await fetch(`${API_BASE}/debate/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({ detail: "Debate failed" }));
    throw new Error(body.detail ?? "Debate failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trim();
      if (!raw) continue;
      const event = JSON.parse(raw) as DebateStreamEvent;
      if (event.type === "thinking" && event.speaker) {
        handlers.onThinking(event.speaker);
      } else if (event.type === "turn" && event.speaker && event.content && event.model && event.created_at) {
        handlers.onTurn({
          speaker: event.speaker,
          content: event.content,
          model: event.model,
          created_at: event.created_at,
          director: event.director
        });
      } else if (event.type === "done" && event.conversation_id && event.topic) {
        handlers.onDone({ conversation_id: event.conversation_id, topic: event.topic });
      } else if (event.type === "error") {
        handlers.onError(event.detail ?? "Debate failed");
      }
    }
  }
}

export async function fetchTTSStatus() {
  const res = await fetch(`${API_BASE}/tts/status`);
  if (!res.ok) throw new Error("TTS status unavailable");
  return (await res.json()) as {
    available: boolean;
    provider: string;
    hint: string;
    openai_voice: string;
    anthropic_voice: string;
  };
}

export type TtsSpeaker = "openai" | "anthropic" | "AI_A" | "AI_B" | "narrator";
export type TtsProfile = "dramaturg" | "performance" | "inszenierung";

export async function fetchSpeechBlob(
  text: string,
  speaker: TtsSpeaker,
  options?: { profile?: TtsProfile }
): Promise<Blob> {
  const res = await fetch(`${API_BASE}/tts/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, speaker, profile: options?.profile ?? null })
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "TTS failed" }));
    throw new Error(body.detail ?? "TTS failed");
  }
  return res.blob();
}

let currentAudio: HTMLAudioElement | null = null;
let playbackPaused = false;

export function isPlaybackPaused(): boolean {
  return playbackPaused;
}

export function setPlaybackPaused(paused: boolean): void {
  playbackPaused = paused;
  if (paused && currentAudio) {
    currentAudio.pause();
  } else if (!paused && currentAudio && currentAudio.paused && !currentAudio.ended) {
    void currentAudio.play();
  }
}

export function stopPlayback(): void {
  playbackPaused = false;
  stopCurrentAudio();
}

function stopCurrentAudio(): void {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
}

export function playBlob(
  blob: Blob,
  hooks?: {
    onPlay?: () => void;
    onTimeUpdate?: (currentTime: number, duration: number) => void;
    shouldAbort?: () => boolean;
  }
): Promise<void> {
  return new Promise((resolve, reject) => {
    stopCurrentAudio();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudio = audio;
    audio.onplay = () => {
      hooks?.onPlay?.();
    };
    audio.ontimeupdate = () => {
      hooks?.onTimeUpdate?.(audio.currentTime, audio.duration);
    };
    audio.onended = () => {
      URL.revokeObjectURL(url);
      if (currentAudio === audio) currentAudio = null;
      resolve();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      if (currentAudio === audio) currentAudio = null;
      reject(new Error("Audio playback failed"));
    };

    const startPlayback = async () => {
      if (playbackPaused) {
        const ok = await waitWhilePlaybackPaused(hooks?.shouldAbort ?? (() => false));
        if (!ok) {
          URL.revokeObjectURL(url);
          if (currentAudio === audio) currentAudio = null;
          reject(new Error("Playback aborted"));
          return;
        }
      }
      try {
        await audio.play();
      } catch (err) {
        URL.revokeObjectURL(url);
        if (currentAudio === audio) currentAudio = null;
        reject(err instanceof Error ? err : new Error("Audio playback failed"));
      }
    };

    void startPlayback();
  });
}

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Block until pause is cleared or playback stops. */
export async function waitWhilePlaybackPaused(shouldAbort: () => boolean): Promise<boolean> {
  while (playbackPaused && !shouldAbort()) {
    await sleep(80);
  }
  return !shouldAbort();
}
