import { apiFetch } from "@/lib/api/base";
import { DirectorPayload } from "@/lib/types/director";
import { DebateRequest, DebateStreamEvent } from "@/lib/types/chat";

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
  const res = await apiFetch("/debate/stream", {
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
  const res = await apiFetch("/tts/status");
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
  const res = await apiFetch("/tts/speak", {
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
let playbackRate = 1;
let narratorVolume = 1;
let narratorMuted = false;
/** Settles the in-flight playBlob when stop/seek aborts before onended. */
let activePlaySettle: (() => void) | null = null;

type PlaybackPauseListener = (paused: boolean) => void;
const playbackPauseListeners = new Set<PlaybackPauseListener>();

type PlaybackRateListener = (rate: number) => void;
const playbackRateListeners = new Set<PlaybackRateListener>();

type NarratorVolumeListener = (volume: number, muted: boolean) => void;
const narratorVolumeListeners = new Set<NarratorVolumeListener>();

export function onPlaybackPauseChange(listener: PlaybackPauseListener): () => void {
  playbackPauseListeners.add(listener);
  return () => playbackPauseListeners.delete(listener);
}

export function onPlaybackRateChange(listener: PlaybackRateListener): () => void {
  playbackRateListeners.add(listener);
  return () => playbackRateListeners.delete(listener);
}

export function onNarratorVolumeChange(listener: NarratorVolumeListener): () => void {
  narratorVolumeListeners.add(listener);
  return () => narratorVolumeListeners.delete(listener);
}

function notifyPlaybackPause(paused: boolean): void {
  for (const listener of playbackPauseListeners) listener(paused);
}

function notifyPlaybackRate(rate: number): void {
  for (const listener of playbackRateListeners) listener(rate);
}

function notifyNarratorVolume(): void {
  for (const listener of narratorVolumeListeners) listener(narratorVolume, narratorMuted);
}

function applyNarratorGain(audio: HTMLAudioElement): void {
  audio.muted = narratorMuted;
  audio.volume = Math.max(0, Math.min(1, narratorVolume));
}

export function getPlaybackRate(): number {
  return playbackRate;
}

export function setPlaybackRate(rate: number): void {
  playbackRate = Math.max(0.5, Math.min(2, rate));
  if (currentAudio) currentAudio.playbackRate = playbackRate;
  notifyPlaybackRate(playbackRate);
}

export function getNarratorVolume(): number {
  return narratorVolume;
}

export function isNarratorMuted(): boolean {
  return narratorMuted;
}

export function setNarratorVolume(volume: number): void {
  narratorVolume = Math.max(0, Math.min(1, volume));
  if (currentAudio) applyNarratorGain(currentAudio);
  notifyNarratorVolume();
}

export function setNarratorMuted(muted: boolean): void {
  narratorMuted = muted;
  if (currentAudio) applyNarratorGain(currentAudio);
  notifyNarratorVolume();
}

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
  notifyPlaybackPause(paused);
}

function settleActivePlay(): void {
  const settle = activePlaySettle;
  activePlaySettle = null;
  settle?.();
}

export function stopPlayback(): void {
  playbackPaused = false;
  notifyPlaybackPause(false);
  settleActivePlay();
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
    // Previous playBlob must settle; otherwise stop/seek leaves the old loop hanging on await.
    settleActivePlay();
    stopCurrentAudio();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudio = audio;
    audio.playbackRate = playbackRate;
    applyNarratorGain(audio);

    let settled = false;
    let abortPoll: ReturnType<typeof setInterval> | null = null;
    const finish = (outcome: () => void) => {
      if (settled) return;
      settled = true;
      if (activePlaySettle === onAbortSettle) activePlaySettle = null;
      if (abortPoll != null) clearInterval(abortPoll);
      abortPoll = null;
      audio.onplay = null;
      audio.ontimeupdate = null;
      audio.onended = null;
      audio.onerror = null;
      URL.revokeObjectURL(url);
      if (currentAudio === audio) currentAudio = null;
      outcome();
    };

    const onAbortSettle = () => {
      audio.pause();
      finish(() => resolve());
    };
    activePlaySettle = onAbortSettle;

    abortPoll = setInterval(() => {
      if (hooks?.shouldAbort?.()) {
        onAbortSettle();
      }
    }, 80);

    audio.onplay = () => {
      hooks?.onPlay?.();
    };
    audio.ontimeupdate = () => {
      hooks?.onTimeUpdate?.(audio.currentTime, audio.duration);
    };
    audio.onended = () => {
      finish(() => resolve());
    };
    audio.onerror = () => {
      finish(() => reject(new Error("Audio playback failed")));
    };

    const startPlayback = async () => {
      if (playbackPaused) {
        const ok = await waitWhilePlaybackPaused(hooks?.shouldAbort ?? (() => false));
        if (!ok) {
          finish(() => resolve());
          return;
        }
      }
      if (settled || hooks?.shouldAbort?.()) {
        finish(() => resolve());
        return;
      }
      try {
        await audio.play();
      } catch (err) {
        if (settled) return;
        finish(() =>
          reject(err instanceof Error ? err : new Error("Audio playback failed"))
        );
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

/** Wall-clock sleep that respects pause and playback rate (for OSC timing without TTS). */
export async function sleepWallMs(ms: number, shouldAbort: () => boolean): Promise<boolean> {
  if (ms <= 0) return !shouldAbort();
  let remaining = ms / playbackRate;
  while (remaining > 0 && !shouldAbort()) {
    if (!(await waitWhilePlaybackPaused(shouldAbort))) return false;
    const step = Math.min(50, remaining);
    await sleep(step);
    remaining -= step;
  }
  return !shouldAbort();
}
