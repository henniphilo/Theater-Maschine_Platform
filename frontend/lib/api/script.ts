import type { DramaturgyDecision } from "@/lib/types/director";
import type { ProductionScript, ScriptSpeaker, WorkshopStreamEvent } from "@/lib/types/script";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function createScript(title: string, sourceText: string): Promise<ProductionScript> {
  const res = await fetch(`${API_BASE}/scripts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, source_text: sourceText })
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Script create failed" }));
    throw new Error(body.detail ?? "Script create failed");
  }
  return res.json();
}

export async function fetchScript(scriptId: string): Promise<ProductionScript> {
  const res = await fetch(`${API_BASE}/scripts/${scriptId}`);
  if (!res.ok) throw new Error("Script not found");
  return res.json();
}

export async function patchScriptBeat(
  scriptId: string,
  beatId: string,
  update: { speaker?: ScriptSpeaker; dramaturgy?: DramaturgyDecision }
): Promise<ProductionScript> {
  const res = await fetch(`${API_BASE}/scripts/${scriptId}/beats/${beatId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update)
  });
  if (!res.ok) throw new Error("Beat update failed");
  return res.json();
}

export type WorkshopHandlers = {
  onEvent: (event: WorkshopStreamEvent) => void;
  onError: (detail: string) => void;
};

export async function streamDramaturgyWorkshop(
  scriptId: string,
  options: { openai_model?: string; anthropic_model?: string; discussion_rounds?: number },
  handlers: WorkshopHandlers
): Promise<void> {
  const res = await fetch(`${API_BASE}/scripts/${scriptId}/dramaturgy/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      openai_model: options.openai_model ?? "gpt-4o",
      anthropic_model: options.anthropic_model ?? "claude-sonnet-4-6",
      discussion_rounds: options.discussion_rounds ?? 3
    })
  });
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({ detail: "Workshop failed" }));
    throw new Error(body.detail ?? "Workshop failed");
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
      const event = JSON.parse(raw) as WorkshopStreamEvent;
      if (event.type === "error") {
        handlers.onError(event.detail ?? "Workshop failed");
      } else {
        handlers.onEvent(event);
      }
    }
  }
}
