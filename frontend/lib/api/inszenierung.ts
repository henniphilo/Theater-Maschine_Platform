import type {
  AnalyseStreamEvent,
  KompositionStreamEvent,
  SceneCorpus,
  Teil2ScriptResponse
} from "@/lib/types/inszenierung";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function fetchScript(): Promise<Teil2ScriptResponse> {
  const res = await fetch(`${API_BASE}/inszenierung/script`);
  if (!res.ok) throw new Error("Skript konnte nicht geladen werden");
  return res.json();
}

export async function createCorpus(title: string): Promise<SceneCorpus> {
  const res = await fetch(`${API_BASE}/inszenierung`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title })
  });
  if (!res.ok) throw new Error("Korpus konnte nicht angelegt werden");
  return res.json();
}

export async function fetchCorpus(corpusId: string): Promise<SceneCorpus> {
  const res = await fetch(`${API_BASE}/inszenierung/${corpusId}`);
  if (!res.ok) throw new Error("Korpus nicht gefunden");
  return res.json();
}

export async function composeScript(corpusId: string): Promise<SceneCorpus> {
  const res = await fetch(`${API_BASE}/inszenierung/${corpusId}/compose-script`, {
    method: "POST"
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Timeline konnte nicht geladen werden" }));
    throw new Error(typeof err.detail === "string" ? err.detail : "Timeline konnte nicht geladen werden");
  }
  return res.json();
}

export async function exportTeil2(corpusId: string): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${API_BASE}/inszenierung/${corpusId}/export`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Export fehlgeschlagen" }));
    throw new Error(body.detail ?? "Export fehlgeschlagen");
  }
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? "teil2.tmteil2.zip";
  const blob = await res.blob();
  return { blob, filename };
}

export async function importTeil2(file: File): Promise<SceneCorpus> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/inszenierung/import`, {
    method: "POST",
    body: form
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Import fehlgeschlagen" }));
    throw new Error(body.detail ?? "Import fehlgeschlagen");
  }
  return res.json();
}

type StreamHandlers<T> = {
  onEvent: (event: T) => void;
  onError: (detail: string) => void;
};

async function consumeSse<T>(
  url: string,
  body: object,
  handlers: StreamHandlers<T>
): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({ detail: "Stream fehlgeschlagen" }));
    throw new Error(err.detail ?? "Stream fehlgeschlagen");
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
      const event = JSON.parse(raw) as T & { type: string; detail?: string };
      if (event.type === "error") {
        handlers.onError((event as { detail?: string }).detail ?? "Stream fehlgeschlagen");
      } else {
        handlers.onEvent(event);
      }
    }
  }
}

export async function streamAnalyse(
  corpusId: string,
  options: { openai_model?: string; anthropic_model?: string },
  handlers: StreamHandlers<AnalyseStreamEvent>
): Promise<void> {
  await consumeSse(
    `${API_BASE}/inszenierung/${corpusId}/analyse/stream`,
    {
      openai_model: options.openai_model ?? "gpt-4o",
      anthropic_model: options.anthropic_model ?? "claude-sonnet-4-6"
    },
    handlers
  );
}

export async function streamKomposition(
  corpusId: string,
  options: { openai_model?: string; moment_count?: number },
  handlers: StreamHandlers<KompositionStreamEvent>
): Promise<void> {
  await consumeSse(
    `${API_BASE}/inszenierung/${corpusId}/komposition/stream`,
    {
      openai_model: options.openai_model ?? "gpt-4o",
      moment_count: options.moment_count ?? 12
    },
    handlers
  );
}
