import {
  clearDramaturgySession,
  saveDramaturgySession,
  type DramaturgyChatLine
} from "@/features/dramaturgy/session";
import {
  isPlaybackBuffered,
  startScriptBuffer,
  type ScriptBufferState
} from "@/features/show/performanceBuffer";
import type { PlaybackAudioOptions } from "@/features/show/scriptPlayback";
import { createScript, streamDramaturgyWorkshop } from "@/lib/api/script";
import type { DirectorPayload } from "@/lib/types/director";
import type { Part1BaerenklauSelection, WorkshopPhase } from "@/lib/types/part1";
import type { ProductionScript, WorkshopStreamEvent } from "@/lib/types/script";
import { dramaturgSpeakerLabel } from "@/lib/types/script";

export type WorkshopRunnerStatus = "idle" | "running" | "done" | "error";

export type WorkshopRunnerState = {
  status: WorkshopRunnerStatus;
  script: ProductionScript | null;
  title: string;
  sourceText: string;
  openaiModel: string;
  anthropicModel: string;
  chat: DramaturgyChatLine[];
  thinking: string | null;
  workshopPhase?: WorkshopPhase;
  previewStatus: string | null;
  finalSelection: Part1BaerenklauSelection | null;
  error: string;
  ttsAvailable: boolean;
};

type Listener = (state: WorkshopRunnerState) => void;

const INITIAL: WorkshopRunnerState = {
  status: "idle",
  script: null,
  title: "Stück",
  sourceText: "",
  openaiModel: "gpt-4o",
  anthropicModel: "claude-sonnet-4-6",
  chat: [],
  thinking: null,
  previewStatus: null,
  finalSelection: null,
  error: "",
  ttsAvailable: false
};

let state: WorkshopRunnerState = INITIAL;
let runGeneration = 0;
const listeners = new Set<Listener>();

function stripMediaJson(text: string): string {
  return text
    .replace(/```(?:json)?\s*\{[\s\S]*?\}\s*```/g, "")
    .replace(/\{[^{}]*"sounds"[\s\S]*?\}/g, "")
    .trim();
}

function emit(patch: Partial<WorkshopRunnerState>): void {
  state = { ...state, ...patch };
  persistSession();
  for (const listener of listeners) listener(state);
}

function persistSession(): void {
  if (!state.sourceText && state.status === "idle") return;
  saveDramaturgySession({
    title: state.title,
    sourceText: state.sourceText,
    scriptId: state.script?.id ?? null,
    chat: state.chat,
    openaiModel: state.openaiModel,
    anthropicModel: state.anthropicModel
  });
}

function playbackOptions(): PlaybackAudioOptions {
  return {
    ttsAvailable: state.ttsAvailable,
    scriptId: state.script?.id,
    hasRenderedAudio: Boolean(state.script?.has_rendered_audio)
  };
}

function maybeStartBuffer(script: ProductionScript): void {
  if (script.status !== "ready" && !script.has_rendered_audio) return;
  if (!state.ttsAvailable) return;
  startScriptBuffer(script, playbackOptions());
}

function handleEvent(event: WorkshopStreamEvent): void {
  const patch: Partial<WorkshopRunnerState> = {};

  if (event.workshop_phase) {
    patch.workshopPhase = event.workshop_phase;
  }

  if (event.type === "preview_start" && event.preview) {
    patch.previewStatus = `Preview: ${event.preview.medium} · ${event.preview.medium_id}`;
    emit(patch);
    return;
  }

  if (event.type === "preview_end") {
    patch.previewStatus = null;
    emit(patch);
    return;
  }

  if (event.type === "agreement_saved" && event.part1_selection) {
    patch.finalSelection = event.part1_selection;
  }

  if (event.type === "thinking" && event.speaker) {
    patch.thinking = `${dramaturgSpeakerLabel(event.speaker)} denkt …`;
    emit(patch);
    return;
  }

  if (event.type === "discussion_turn" && event.content && event.speaker) {
    const line: DramaturgyChatLine = {
      id: crypto.randomUUID(),
      speaker: dramaturgSpeakerLabel(event.speaker),
      content: stripMediaJson(event.content),
      beatOrder: event.beat_order
    };
    patch.chat = [...state.chat, line];
    patch.thinking = null;
    emit(patch);
    return;
  }

  if (event.type === "dramaturgy_decision" && event.dramaturgy) {
    const line: DramaturgyChatLine = {
      id: crypto.randomUUID(),
      speaker: `Regie · Gesamttext`,
      content: event.dramaturgy.reason,
      beatOrder: event.beat_order,
      director: {
        event: {},
        decision: event.dramaturgy,
        executed: false,
        blocked_reason: null,
        planned_commands: event.planned_commands ?? [],
        osc_commands: []
      } as DirectorPayload
    };
    patch.chat = [...state.chat, line];
    emit(patch);
    return;
  }

  if (event.type === "script_updated" && event.script) {
    patch.script = event.script;
    patch.finalSelection = event.script.part1_selection ?? state.finalSelection;
    sessionStorage.setItem("currentScriptId", event.script.id);
    maybeStartBuffer(event.script);
    emit(patch);
    return;
  }

  if (event.type === "done") {
    patch.status = "done";
    patch.thinking = null;
    patch.previewStatus = null;
    emit(patch);
    if (state.script) {
      console.info(
        "%c[Theatermaschine] Dramaturgen-Workshop abgeschlossen",
        "color:#6b8cff;font-weight:bold",
        {
          scriptId: state.script.id,
          title: state.script.title,
          beats: state.script.beats.length,
          part1Selection: state.script.part1_selection ?? state.finalSelection
        }
      );
      maybeStartBuffer(state.script);
    }
    return;
  }

  if (Object.keys(patch).length > 0) emit(patch);
}

export function getWorkshopRunnerState(): WorkshopRunnerState {
  return state;
}

export function subscribeWorkshopRunner(listener: Listener): () => void {
  listeners.add(listener);
  listener(state);
  return () => listeners.delete(listener);
}

export function isWorkshopRunning(): boolean {
  return state.status === "running";
}

export function hydrateWorkshopRunner(partial: Partial<WorkshopRunnerState>): void {
  state = { ...state, ...partial };
  for (const listener of listeners) listener(state);
}

export function setWorkshopTtsAvailable(available: boolean): void {
  if (state.ttsAvailable === available) return;
  emit({ ttsAvailable: available });
  if (state.script && (state.status === "done" || state.script.status === "ready")) {
    maybeStartBuffer(state.script);
  }
}

export async function startPart1Workshop(options: {
  title: string;
  sourceText: string;
  openaiModel: string;
  anthropicModel: string;
  ttsAvailable: boolean;
}): Promise<void> {
  if (state.status === "running") return;

  const generation = ++runGeneration;
  clearDramaturgySession();

  emit({
    status: "running",
    title: options.title,
    sourceText: options.sourceText,
    openaiModel: options.openaiModel,
    anthropicModel: options.anthropicModel,
    ttsAvailable: options.ttsAvailable,
    chat: [],
    thinking: null,
    workshopPhase: undefined,
    previewStatus: null,
    finalSelection: null,
    error: "",
    script: null
  });

  console.info("[Theatermaschine] Dramaturgen-Workshop gestartet …");

  try {
    const created = await createScript(options.title, options.sourceText);
    if (generation !== runGeneration) return;

    emit({ script: created });
    sessionStorage.setItem("currentScriptId", created.id);

    await streamDramaturgyWorkshop(
      created.id,
      { openai_model: options.openaiModel, anthropic_model: options.anthropicModel, discussion_rounds: 1 },
      {
        onEvent: (event) => {
          if (generation !== runGeneration) return;
          if (event.type === "error") {
            emit({
              status: "error",
              error: event.detail ?? "Workshop fehlgeschlagen",
              thinking: null
            });
            console.error("[Theatermaschine] Dramaturgen-Workshop Fehler:", event.detail);
            return;
          }
          handleEvent(event);
        },
        onError: (detail) => {
          if (generation !== runGeneration) return;
          emit({ status: "error", error: detail, thinking: null });
          console.error("[Theatermaschine] Dramaturgen-Workshop Fehler:", detail);
        }
      }
    );
  } catch (err) {
    if (generation !== runGeneration) return;
    const message = err instanceof Error ? err.message : "Workshop fehlgeschlagen";
    emit({ status: "error", error: message, thinking: null });
    console.error("[Theatermaschine] Dramaturgen-Workshop Fehler:", message);
  } finally {
    if (generation !== runGeneration) return;
    if (state.status === "running") {
      emit({ status: "done", thinking: null });
    }
  }
}

export function workshopStatusLabel(
  workshop: WorkshopRunnerState,
  buffer: ScriptBufferState | null
): string | null {
  if (workshop.status === "running") {
    const phase = workshop.workshopPhase ? ` · ${workshop.workshopPhase}` : "";
    return `Dramaturgie läuft${phase}${workshop.previewStatus ? ` · ${workshop.previewStatus}` : ""}`;
  }
  if (workshop.status === "error") return workshop.error;
  if (workshop.status === "done" && workshop.script) {
    const opts = playbackOptions();
    if (isPlaybackBuffered(workshop.script.id, opts)) {
      return "Dramaturgen fertig — Stimmen bereit";
    }
    if (buffer?.scriptId === workshop.script.id && buffer.status === "buffering") {
      return `Dramaturgen fertig — ${buffer.loaded}/${buffer.total || "…"} Stimmen`;
    }
    return "Dramaturgen fertig — Aufführung wird vorbereitet";
  }
  return null;
}
