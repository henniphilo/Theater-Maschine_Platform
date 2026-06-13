import { fetchSpeechBlob, playBlob, stopPlayback } from "@/lib/api/client";
import { postDirectorDialogueEvent, postDirectorExecute } from "@/lib/api/director";
import { sentenceIndexForProgress, splitSentences } from "@/lib/text/splitSentences";
import type { DirectorPayload, OscCommand, ShowPhase } from "@/lib/types/director";
import type { ChatMessage } from "@/lib/types/chat";

const OSC_HIGHLIGHT_MS = 150;

export type MachineBeatState = "future" | "current" | "past";

export type MachineRuntimeState = {
  running: boolean;
  beatIndex: number;
  beatTotal: number;
  currentMessageId: string | null;
  beatStates: Record<string, MachineBeatState>;
  sentenceIndex: number;
  showPhase?: ShowPhase;
  activeOscBridge: string | null;
  activeOscCommand: OscCommand | null;
};

export const INITIAL_MACHINE_STATE: MachineRuntimeState = {
  running: false,
  beatIndex: 0,
  beatTotal: 0,
  currentMessageId: null,
  beatStates: {},
  sentenceIndex: 0,
  activeOscBridge: null,
  activeOscCommand: null
};

export type MachineCallbacks = {
  onState: (state: Partial<MachineRuntimeState>) => void;
  onMessage: (messageId: string, update: Partial<ChatMessage>) => void;
  shouldAbort: () => boolean;
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function ensureDirector(
  message: ChatMessage,
  topic: string
): Promise<DirectorPayload | undefined> {
  if (message.director) return message.director;
  if (!message.speaker) return undefined;

  try {
    const planned = await postDirectorDialogueEvent({
      speaker: message.speaker === "anthropic" ? "AI_B" : "AI_A",
      text: message.content,
      topic
    });
    return {
      event: planned.event as Record<string, unknown>,
      decision: planned.decision,
      executed: planned.executed,
      blocked_reason: planned.blocked_reason,
      planned_commands: planned.planned_commands,
      osc_commands: planned.osc_commands
    };
  } catch {
    return undefined;
  }
}

async function highlightOscSequence(
  commands: OscCommand[],
  onHighlight: (cmd: OscCommand | null, bridge: string | null) => void,
  shouldAbort: () => boolean
) {
  for (const cmd of commands) {
    if (shouldAbort()) break;
    onHighlight(cmd, cmd.bridge);
    await sleep(OSC_HIGHLIGHT_MS);
  }
  onHighlight(null, null);
}

export async function runMachinePlayback(
  beats: ChatMessage[],
  topic: string,
  ttsAvailable: boolean,
  callbacks: MachineCallbacks
): Promise<void> {
  const beatStates: Record<string, MachineBeatState> = {};
  for (const beat of beats) beatStates[beat.id] = "future";

  callbacks.onState({
    running: true,
    beatIndex: 0,
    beatTotal: beats.length,
    currentMessageId: null,
    beatStates: { ...beatStates },
    sentenceIndex: 0,
    activeOscBridge: null,
    activeOscCommand: null
  });

  for (let index = 0; index < beats.length; index++) {
    if (callbacks.shouldAbort()) break;

    const message = beats[index];
    for (let j = 0; j < beats.length; j++) {
      const beat = beats[j];
      if (j < index) beatStates[beat.id] = "past";
      else if (j === index) beatStates[beat.id] = "current";
      else beatStates[beat.id] = "future";
    }

    callbacks.onState({
      beatIndex: index,
      currentMessageId: message.id,
      beatStates: { ...beatStates },
      sentenceIndex: 0,
      showPhase: "planned",
      activeOscBridge: null,
      activeOscCommand: null
    });

    callbacks.onMessage(message.id, {
      showPhase: "planned",
      osc_commands: undefined,
      director: message.director
        ? { ...message.director, executed: false, osc_commands: [], blocked_reason: null }
        : undefined
    });

    const director = await ensureDirector(message, topic);
    if (director) {
      callbacks.onMessage(message.id, { director });
    }

    if (callbacks.shouldAbort()) break;

    if (!ttsAvailable) {
      callbacks.onState({ showPhase: "cues_active" });
      callbacks.onMessage(message.id, { showPhase: "cues_active" });
      if (director) {
        try {
          const result = await postDirectorExecute(director.decision, { force: true, stagger: true });
          void highlightOscSequence(
            result.osc_commands,
            (cmd, bridge) => callbacks.onState({ activeOscCommand: cmd, activeOscBridge: bridge }),
            callbacks.shouldAbort
          );
          callbacks.onMessage(message.id, {
            showPhase: result.executed ? "sent" : "blocked",
            osc_commands: result.osc_commands,
            director: {
              ...director,
              executed: result.executed,
              blocked_reason: result.blocked_reason,
              osc_commands: result.osc_commands
            }
          });
        } catch {
          callbacks.onMessage(message.id, { showPhase: "blocked" });
        }
      }
      beatStates[message.id] = "past";
      continue;
    }

    callbacks.onState({ showPhase: "speaking", sentenceIndex: 0 });
    callbacks.onMessage(message.id, { showPhase: "speaking" });

    const sentences = splitSentences(message.content);
    let cuesTriggered = false;

    try {
      const blob = await fetchSpeechBlob(message.content, message.speaker!);
      if (callbacks.shouldAbort()) break;

      await playBlob(blob, {
        onPlay: () => {
          if (cuesTriggered || !director) return;
          cuesTriggered = true;
          callbacks.onState({ showPhase: "cues_active" });
          callbacks.onMessage(message.id, { showPhase: "cues_active" });
          void postDirectorExecute(director.decision, { force: true, stagger: true })
            .then(async (result) => {
              await highlightOscSequence(
                result.osc_commands,
                (cmd, bridge) => callbacks.onState({ activeOscCommand: cmd, activeOscBridge: bridge }),
                callbacks.shouldAbort
              );
              callbacks.onMessage(message.id, {
                showPhase: result.executed ? "sent" : "blocked",
                osc_commands: result.osc_commands,
                director: {
                  ...director,
                  executed: result.executed,
                  blocked_reason: result.blocked_reason,
                  osc_commands: result.osc_commands
                }
              });
            })
            .catch(() => {
              callbacks.onMessage(message.id, { showPhase: "blocked" });
            });
        },
        onTimeUpdate: (current, duration) => {
          const sentenceIndex = sentenceIndexForProgress(current, duration, sentences.length);
          callbacks.onState({ sentenceIndex });
        }
      });

      if (!cuesTriggered && director) {
        callbacks.onState({ showPhase: "cues_active" });
        callbacks.onMessage(message.id, { showPhase: "cues_active" });
        const result = await postDirectorExecute(director.decision, { force: true, stagger: true });
        await highlightOscSequence(
          result.osc_commands,
          (cmd, bridge) => callbacks.onState({ activeOscCommand: cmd, activeOscBridge: bridge }),
          callbacks.shouldAbort
        );
        callbacks.onMessage(message.id, {
          showPhase: result.executed ? "sent" : "blocked",
          osc_commands: result.osc_commands,
          director: {
            ...director,
            executed: result.executed,
            blocked_reason: result.blocked_reason,
            osc_commands: result.osc_commands
          }
        });
      }
    } catch {
      if (!callbacks.shouldAbort()) {
        callbacks.onMessage(message.id, { showPhase: "blocked" });
      }
    }

    beatStates[message.id] = "past";
    callbacks.onState({
      beatStates: { ...beatStates },
      activeOscBridge: null,
      activeOscCommand: null
    });
  }

  callbacks.onState({
    running: false,
    currentMessageId: null,
    activeOscBridge: null,
    activeOscCommand: null,
    showPhase: undefined
  });
}

export function stopMachinePlayback() {
  stopPlayback();
}
