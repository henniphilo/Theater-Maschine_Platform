import { afterEach, describe, expect, it, vi } from "vitest";

import {
  clearReliableTimeout,
  resetReliableTimeoutForTests,
  scheduleReliableTimeout
} from "@/lib/timing/reliableTimeout";

describe("reliableTimeout", () => {
  afterEach(() => {
    resetReliableTimeoutForTests();
    vi.useRealTimers();
  });

  it("fires on the main thread under Vitest fake timers", async () => {
    vi.useFakeTimers();
    const spy = vi.fn();
    scheduleReliableTimeout(spy, 250);
    expect(spy).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(249);
    expect(spy).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("clear cancels a pending callback", async () => {
    vi.useFakeTimers();
    const spy = vi.fn();
    const handle = scheduleReliableTimeout(spy, 100);
    clearReliableTimeout(handle);
    await vi.advanceTimersByTimeAsync(500);
    expect(spy).not.toHaveBeenCalled();
  });
});
