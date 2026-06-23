import type {
  AnalyseStreamEvent,
  KompositionStreamEvent,
  SceneCorpus
} from "@/lib/types/inszenierung";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

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

export async function addScene(
  corpusId: string,
  scene: { animal: string; title?: string; source_text: string; play_reference?: string }
): Promise<SceneCorpus> {
  const res = await fetch(`${API_BASE}/inszenierung/${corpusId}/scenes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(scene)
  });
  if (!res.ok) throw new Error("Szene konnte nicht hinzugefügt werden");
  return res.json();
}

export async function addScenesBatch(
  corpusId: string,
  scenes: { animal: string; title?: string; source_text: string; play_reference?: string }[]
): Promise<SceneCorpus> {
  const res = await fetch(`${API_BASE}/inszenierung/${corpusId}/scenes/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenes })
  });
  if (!res.ok) throw new Error("Szenen-Batch fehlgeschlagen");
  return res.json();
}

export async function uploadSceneFiles(corpusId: string, files: File[]): Promise<SceneCorpus> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  const res = await fetch(`${API_BASE}/inszenierung/${corpusId}/scenes/upload`, {
    method: "POST",
    body: form
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload fehlgeschlagen" }));
    throw new Error(typeof err.detail === "string" ? err.detail : "Upload fehlgeschlagen");
  }
  return res.json();
}

export async function deleteScene(corpusId: string, sceneId: string): Promise<SceneCorpus> {
  const res = await fetch(`${API_BASE}/inszenierung/${corpusId}/scenes/${sceneId}`, {
    method: "DELETE"
  });
  if (!res.ok) throw new Error("Szene konnte nicht gelöscht werden");
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
