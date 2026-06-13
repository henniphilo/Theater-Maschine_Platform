/** Split prose into speakable sentence chunks for progress highlighting. */
export function splitSentences(text: string): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];

  const parts = trimmed.match(/[^.!?…]+[.!?…]+[\s]*/g);
  if (!parts) return [trimmed];

  const joined = parts.join("");
  const tail = trimmed.slice(joined.length).trim();
  return tail ? [...parts.map((p) => p.trimEnd()), tail] : parts.map((p) => p.trimEnd());
}

export function sentenceIndexForProgress(
  currentTime: number,
  duration: number,
  sentenceCount: number
): number {
  if (sentenceCount <= 1) return 0;
  if (!Number.isFinite(duration) || duration <= 0) return 0;
  const ratio = Math.min(1, Math.max(0, currentTime / duration));
  return Math.min(sentenceCount - 1, Math.floor(ratio * sentenceCount));
}
