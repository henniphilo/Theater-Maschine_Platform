import type { CompositionMoment, SceneCorpus } from "@/lib/types/inszenierung";
import { fetchSpeechBlob } from "@/lib/api/client";
import { getCachedSpeech, prefetchSpeech } from "@/lib/tts/prefetch";

export type InszenierungBufferState = {
  corpusId: string | null;
  status: "idle" | "buffering" | "ready" | "error";
  loaded: number;
  total: number;
  error?: string;
};

const INITIAL: InszenierungBufferState = {
  corpusId: null,
  status: "idle",
  loaded: 0,
  total: 0
};

type Listener = (state: InszenierungBufferState) => void;

let state: InszenierungBufferState = INITIAL;
let generation = 0;
const listeners = new Set<Listener>();

function emit(patch: Partial<InszenierungBufferState>): void {
  state = { ...state, ...patch };
  for (const listener of listeners) listeners(state);
}

export function subscribeInszenierungBuffer(listener: Listener): () => void {
  listeners.add(listener);
  listener(state);
  return () => listeners.delete(listener);
}

export function isInszenierungBuffered(corpusId: string, ttsAvailable: boolean): boolean {
  if (!ttsAvailable) return false;
  return state.corpusId === corpusId && state.status === "ready";
}

export function startInszenierungBuffer(corpus: SceneCorpus, ttsAvailable: boolean): void {
  if (!ttsAvailable) {
    emit({
      corpusId: corpus.id,
      status: "error",
      loaded: 0,
      total: 0,
      error: "Keine Stimmen verfügbar"
    });
    return;
  }
  const moments = corpus.composition?.moments ?? [];
  if (moments.length === 0) {
    emit({ corpusId: corpus.id, status: "idle", loaded: 0, total: 0 });
    return;
  }
  if (state.corpusId === corpus.id && (state.status === "buffering" || state.status === "ready")) {
    return;
  }
  const gen = ++generation;
  emit({ corpusId: corpus.id, status: "buffering", loaded: 0, total: moments.length, error: undefined });

  void warmMoments(corpus.id, moments, (loaded, total) => {
    if (gen !== generation) return;
    emit({
      loaded,
      total,
      status: loaded >= total && total > 0 ? "ready" : "buffering"
    });
  })
    .then(() => {
      if (gen !== generation) return;
      emit({ status: "ready" });
    })
    .catch((err: unknown) => {
      if (gen !== generation) return;
      emit({
        status: "error",
        error: err instanceof Error ? err.message : "Puffer fehlgeschlagen"
      });
    });
}

async function warmMoments(
  corpusId: string,
  moments: CompositionMoment[],
  onProgress: (loaded: number, total: number) => void
): Promise<void> {
  const total = moments.length;
  let loaded = 0;
  onProgress(loaded, total);
  await Promise.all(
    moments.map((moment, index) =>
      resolveMomentSpeech(corpusId, moment, index)
        .catch((err) => console.warn("Moment buffer failed:", err))
        .finally(() => {
          loaded += 1;
          onProgress(loaded, total);
        })
    )
  );
}

function cacheKey(corpusId: string, momentId: string): string {
  return `inszenierung:${corpusId}:${momentId}`;
}

export async function resolveMomentSpeech(
  corpusId: string,
  moment: CompositionMoment,
  index: number
): Promise<Blob> {
  const key = cacheKey(corpusId, moment.id);
  const cached = getCachedSpeech(key);
  if (cached) return cached;
  const blob = await fetchSpeechBlob(moment.text_excerpt, moment.speaker);
  prefetchSpeech(key, Promise.resolve(blob));
  return blob;
}

export function prefetchMoment(corpusId: string, moment: CompositionMoment, index: number): void {
  const key = cacheKey(corpusId, moment.id);
  prefetchSpeech(key, fetchSpeechBlob(moment.text_excerpt, moment.speaker));
}

export function bufferStatusLabel(s: InszenierungBufferState): string {
  if (s.status === "buffering") {
    return s.total > 0 ? `Stimmen laden … ${s.loaded}/${s.total}` : "Stimmen laden …";
  }
  if (s.status === "ready") return "Stimmen bereit";
  if (s.status === "error") return s.error ?? "Puffer fehlgeschlagen";
  return "";
}
