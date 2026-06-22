const activeAudios = new Set<HTMLAudioElement>();

export function stopAllLayeredAudio(): void {
  for (const audio of activeAudios) {
    audio.pause();
    audio.currentTime = 0;
  }
  activeAudios.clear();
}

export function activeLayeredVoiceCount(): number {
  return activeAudios.size;
}

export function playBlobLayered(
  blob: Blob,
  volume: number,
  shouldAbort?: () => boolean
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (shouldAbort?.()) {
      reject(new Error("Playback aborted"));
      return;
    }
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.volume = Math.max(0.05, Math.min(1, volume));
    activeAudios.add(audio);
    audio.onended = () => {
      URL.revokeObjectURL(url);
      activeAudios.delete(audio);
      resolve();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      activeAudios.delete(audio);
      reject(new Error("Layered audio failed"));
    };
    void audio.play().catch((err) => {
      URL.revokeObjectURL(url);
      activeAudios.delete(audio);
      reject(err);
    });
  });
}

export async function waitForVoiceSlot(
  maxConcurrent: number,
  shouldAbort: () => boolean
): Promise<boolean> {
  while (activeLayeredVoiceCount() >= maxConcurrent && !shouldAbort()) {
    await new Promise((r) => setTimeout(r, 80));
  }
  return !shouldAbort();
}
