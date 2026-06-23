import { fetchSpeechBlob, type TtsProfile, type TtsSpeaker } from "@/lib/api/client";

function cacheKey(text: string, speaker: TtsSpeaker, profile?: TtsProfile): string {
  return `${profile ?? "default"}\0${speaker}\0${text}`;
}

const blobCache = new Map<string, Promise<Blob>>();

export function prefetchSpeech(
  text: string,
  speaker: TtsSpeaker,
  options?: { profile?: TtsProfile }
): Promise<Blob> {
  const key = cacheKey(text, speaker, options?.profile);
  let pending = blobCache.get(key);
  if (!pending) {
    pending = fetchSpeechBlob(text, speaker, options).catch((err) => {
      blobCache.delete(key);
      throw err;
    });
    blobCache.set(key, pending);
  }
  return pending;
}

export function getCachedSpeech(
  text: string,
  speaker: TtsSpeaker,
  options?: { profile?: TtsProfile }
): Promise<Blob> {
  return prefetchSpeech(text, speaker, options);
}

export function clearSpeechCache(): void {
  blobCache.clear();
}
