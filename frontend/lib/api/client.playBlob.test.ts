import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { playBlob, stopPlayback } from "@/lib/api/client";

class FakeAudio {
  static instances: FakeAudio[] = [];
  paused = true;
  ended = false;
  currentTime = 0;
  playbackRate = 1;
  volume = 1;
  muted = false;
  onplay: ((this: FakeAudio, ev: Event) => void) | null = null;
  onended: ((this: FakeAudio, ev: Event) => void) | null = null;
  onerror: ((this: FakeAudio, ev: Event) => void) | null = null;
  ontimeupdate: ((this: FakeAudio, ev: Event) => void) | null = null;

  constructor(_src?: string) {
    FakeAudio.instances.push(this);
  }

  play(): Promise<void> {
    this.paused = false;
    this.onplay?.(new Event("play"));
    return Promise.resolve();
  }

  pause(): void {
    this.paused = true;
  }
}

describe("playBlob abort settle", () => {
  const originalAudio = globalThis.Audio;
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;

  beforeEach(() => {
    FakeAudio.instances = [];
    // @ts-expect-error test stub
    globalThis.Audio = FakeAudio;
    URL.createObjectURL = vi.fn(() => "blob:test");
    URL.revokeObjectURL = vi.fn();
    stopPlayback();
  });

  afterEach(() => {
    stopPlayback();
    globalThis.Audio = originalAudio;
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
  });

  it("resolves when stopPlayback aborts before onended", async () => {
    const pending = playBlob(new Blob(["x"]));
    await vi.waitFor(() => expect(FakeAudio.instances.length).toBe(1));
    stopPlayback();
    await expect(pending).resolves.toBeUndefined();
  });

  it("resolves when a newer playBlob supersedes the previous one", async () => {
    const first = playBlob(new Blob(["a"]));
    await vi.waitFor(() => expect(FakeAudio.instances.length).toBe(1));
    const second = playBlob(new Blob(["b"]));
    await expect(first).resolves.toBeUndefined();
    FakeAudio.instances[1]?.onended?.(new Event("ended"));
    await expect(second).resolves.toBeUndefined();
  });
});
