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

/** Client cap so a stuck macOS `say` cannot freeze Teil-2 forever (backend allow up to 180s). */
export const TTS_SPEAK_TIMEOUT_MS = 45_000;
/** If audio never reaches onended (stall / missing ended), force-resolve after duration + grace. */
export const PLAY_BLOB_END_GRACE_MS = 4_000;
/** Wall-clock stall while playing with frozen currentTime. */
export const PLAY_BLOB_STALL_MS = 8_000;
/** Absolute ceiling when duration is unknown. */
export const PLAY_BLOB_MAX_WALL_MS = 180_000;

export async function fetchSpeechBlob(
  text: string,
  speaker: TtsSpeaker,
  options?: { profile?: TtsProfile; timeoutMs?: number }
): Promise<Blob> {
  const timeoutMs = options?.timeoutMs ?? TTS_SPEAK_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await apiFetch("/tts/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, speaker, profile: options?.profile ?? null }),
      signal: controller.signal
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: "TTS failed" }));
      throw new Error(body.detail ?? "TTS failed");
    }
    return await res.blob();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`TTS timeout after ${timeoutMs}ms`);
    }
    if (err instanceof Error && /aborted|AbortError/i.test(err.message)) {
      throw new Error(`TTS timeout after ${timeoutMs}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
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
    /** Test override for absolute wall-clock ceiling (active play time excludes pause). */
    maxWallMs?: number;
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
    let activePlayMs = 0;
    let lastPollAt = Date.now();
    let lastProgressAt = Date.now();
    let lastCurrentTime = 0;
    const maxWallMs = hooks?.maxWallMs ?? PLAY_BLOB_MAX_WALL_MS;

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

    const forceEnd = (reason: string) => {
      console.warn(`[playBlob] ${reason} — continuing playback loop`);
      audio.pause();
      finish(() => resolve());
    };

    abortPoll = setInterval(() => {
      if (hooks?.shouldAbort?.()) {
        onAbortSettle();
        return;
      }
      const now = Date.now();
      const dt = now - lastPollAt;
      lastPollAt = now;
      if (playbackPaused || audio.paused) {
        lastProgressAt = now;
        return;
      }
      activePlayMs += dt;
      const t = audio.currentTime;
      if (Number.isFinite(t) && Math.abs(t - lastCurrentTime) > 0.01) {
        lastCurrentTime = t;
        lastProgressAt = now;
      } else if (now - lastProgressAt >= PLAY_BLOB_STALL_MS) {
        forceEnd(`audio stalled (${PLAY_BLOB_STALL_MS}ms without progress)`);
        return;
      }
      const duration = audio.duration;
      if (Number.isFinite(duration) && duration > 0) {
        const budgetMs = (duration * 1000) / Math.max(0.5, audio.playbackRate || playbackRate) + PLAY_BLOB_END_GRACE_MS;
        if (activePlayMs >= budgetMs) {
          forceEnd(`past expected end (${Math.round(budgetMs)}ms)`);
          return;
        }
      } else if (activePlayMs >= maxWallMs) {
        forceEnd(`max wall time (${maxWallMs}ms)`);
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
        lastPollAt = Date.now();
        lastProgressAt = lastPollAt;
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
