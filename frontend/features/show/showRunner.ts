import { fetchSpeechBlob, playBlob } from "@/lib/api/client";
import { postDirectorExecute } from "@/lib/api/director";
import type { DirectorPayload, OscCommand, ShowPhase } from "@/lib/types/director";
import type { DebateSpeaker } from "@/lib/types/chat";

export type ShowTurnJob = {
  messageId: string;
  speaker: DebateSpeaker;
  content: string;
  director: DirectorPayload;
};

export type ShowMessageUpdate = {
  showPhase?: ShowPhase;
  osc_commands?: OscCommand[];
  director?: DirectorPayload;
};

export async function runShowTurn(
  job: ShowTurnJob,
  ttsAvailable: boolean,
  onUpdate: (messageId: string, update: ShowMessageUpdate) => void
): Promise<void> {
  onUpdate(job.messageId, { showPhase: "planned" });

  if (!ttsAvailable) {
    onUpdate(job.messageId, { showPhase: "cues_active" });
    try {
      const result = await postDirectorExecute(job.director.decision);
      onUpdate(job.messageId, {
        showPhase: result.executed ? "sent" : "blocked",
        osc_commands: result.osc_commands,
        director: {
          ...job.director,
          executed: result.executed,
          blocked_reason: result.blocked_reason,
          osc_commands: result.osc_commands
        }
      });
    } catch {
      onUpdate(job.messageId, { showPhase: "blocked" });
    }
    return;
  }

  onUpdate(job.messageId, { showPhase: "speaking" });
  let cuesTriggered = false;

  try {
    const blob = await fetchSpeechBlob(job.content, job.speaker);
    await playBlob(blob, {
      onPlay: () => {
        if (cuesTriggered) return;
        cuesTriggered = true;
        onUpdate(job.messageId, { showPhase: "cues_active" });
        void postDirectorExecute(job.director.decision)
          .then((result) => {
            onUpdate(job.messageId, {
              showPhase: result.executed ? "sent" : "blocked",
              osc_commands: result.osc_commands,
              director: {
                ...job.director,
                executed: result.executed,
                blocked_reason: result.blocked_reason,
                osc_commands: result.osc_commands
              }
            });
          })
          .catch(() => {
            onUpdate(job.messageId, { showPhase: "blocked" });
          });
      }
    });

    if (!cuesTriggered) {
      onUpdate(job.messageId, { showPhase: "cues_active" });
      const result = await postDirectorExecute(job.director.decision);
      onUpdate(job.messageId, {
        showPhase: result.executed ? "sent" : "blocked",
        osc_commands: result.osc_commands,
        director: {
          ...job.director,
          executed: result.executed,
          blocked_reason: result.blocked_reason,
          osc_commands: result.osc_commands
        }
      });
    }
  } catch {
    onUpdate(job.messageId, { showPhase: "blocked" });
  }
}

export class ShowQueue {
  private queue: ShowTurnJob[] = [];
  private processing = false;

  constructor(
    private getTtsAvailable: () => boolean,
    private onUpdate: (messageId: string, update: ShowMessageUpdate) => void
  ) {}

  enqueue(job: ShowTurnJob) {
    this.queue.push(job);
    void this.drain();
  }

  clear() {
    this.queue = [];
  }

  private async drain() {
    if (this.processing) return;
    this.processing = true;
    while (this.queue.length > 0) {
      const job = this.queue.shift()!;
      await runShowTurn(job, this.getTtsAvailable(), this.onUpdate);
    }
    this.processing = false;
  }
}
