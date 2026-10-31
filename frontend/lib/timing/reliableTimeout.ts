/**
 * Optional dual-arm timers (Worker + main thread) for when a tab may be backgrounded.
 *
 * The Teil-2 avatar CSV chain uses plain `setTimeout` again (Aufführung tab stays
 * foreground during shows). Keep this helper if another path needs background-safe
 * delays.
 *
 * Chrome/Safari throttle main-thread setTimeout to ~1/min in background tabs;
 * Worker timers are not. Production schedules **both**; the first callback wins.
 *
 * In Vitest (`process.env.VITEST`) we stay on the main thread so
 * `vi.useFakeTimers()` keeps working.
 */

export type ReliableTimeoutHandle = { readonly id: number };

type WorkerMsg = { type: "set"; id: number; delayMs: number } | { type: "clear"; id: number };

const callbacks = new Map<number, () => void>();
const mainThreadHandles = new Map<number, ReturnType<typeof setTimeout>>();
/** Ids that still have an armed Worker timer (may also have a main-thread arm). */
const workerArmed = new Set<number>();

let nextId = 1;
let worker: Worker | null = null;
let workerUnavailable = false;

function preferMainThreadTimers(): boolean {
  try {
    // Vitest sets VITEST; Next.js has no import.meta.env types.
    if (typeof process !== "undefined" && Boolean(process.env?.VITEST)) return true;
  } catch {
    /* ignore */
  }
  return false;
}

function ensureWorker(): Worker | null {
  if (workerUnavailable || preferMainThreadTimers()) return null;
  if (worker) return worker;
  if (typeof Worker === "undefined") {
    workerUnavailable = true;
    return null;
  }
  try {
    const code = `
      const timers = new Map();
      self.onmessage = (e) => {
        const data = e.data || {};
        if (data.type === "set") {
          const handle = setTimeout(() => {
            timers.delete(data.id);
            self.postMessage({ id: data.id });
          }, Math.max(0, Number(data.delayMs) || 0));
          timers.set(data.id, handle);
        } else if (data.type === "clear") {
          const handle = timers.get(data.id);
          if (handle != null) clearTimeout(handle);
          timers.delete(data.id);
        }
      };
    `;
    const blob = new Blob([code], { type: "application/javascript" });
    const url = URL.createObjectURL(blob);
    const w = new Worker(url);
    URL.revokeObjectURL(url);
    w.onmessage = (event: MessageEvent<{ id?: number }>) => {
      const id = event.data?.id;
      if (typeof id !== "number") return;
      workerArmed.delete(id);
      const cb = callbacks.get(id);
      // Main-thread arm may still be pending — clear it so we only fire once.
      const main = mainThreadHandles.get(id);
      if (main != null) {
        clearTimeout(main);
        mainThreadHandles.delete(id);
      }
      callbacks.delete(id);
      cb?.();
    };
    w.onerror = () => {
      workerUnavailable = true;
      worker = null;
      workerArmed.clear();
    };
    worker = w;
    return w;
  } catch {
    workerUnavailable = true;
    return null;
  }
}

function armMainThread(id: number, delay: number): void {
  const handle = setTimeout(() => {
    mainThreadHandles.delete(id);
    const cb = callbacks.get(id);
    callbacks.delete(id);
    // Cancel Worker arm if it has not fired yet.
    if (workerArmed.has(id) && worker && !workerUnavailable) {
      const msg: WorkerMsg = { type: "clear", id };
      worker.postMessage(msg);
      workerArmed.delete(id);
    }
    cb?.();
  }, delay);
  mainThreadHandles.set(id, handle);
}

/** Schedule `fn` after `delayMs` without background-tab throttling when possible. */
export function scheduleReliableTimeout(fn: () => void, delayMs: number): ReliableTimeoutHandle {
  const id = nextId++;
  callbacks.set(id, fn);
  const delay = Math.max(0, delayMs);
  const w = ensureWorker();
  if (w) {
    const msg: WorkerMsg = { type: "set", id, delayMs: delay };
    w.postMessage(msg);
    workerArmed.add(id);
    // Parallel main-thread backup: first arm to fire wins (see handlers above).
    armMainThread(id, delay);
  } else {
    armMainThread(id, delay);
  }
  return { id };
}

export function clearReliableTimeout(handle: ReliableTimeoutHandle | null | undefined): void {
  if (!handle) return;
  callbacks.delete(handle.id);
  if (workerArmed.has(handle.id) && worker && !workerUnavailable) {
    const msg: WorkerMsg = { type: "clear", id: handle.id };
    worker.postMessage(msg);
    workerArmed.delete(handle.id);
  }
  const main = mainThreadHandles.get(handle.id);
  if (main != null) {
    clearTimeout(main);
    mainThreadHandles.delete(handle.id);
  }
}

/** Test helper — drop shared worker state between suites. */
export function resetReliableTimeoutForTests(): void {
  for (const handle of mainThreadHandles.values()) clearTimeout(handle);
  mainThreadHandles.clear();
  callbacks.clear();
  workerArmed.clear();
  if (worker) {
    worker.terminate();
    worker = null;
  }
  workerUnavailable = false;
  nextId = 1;
}
