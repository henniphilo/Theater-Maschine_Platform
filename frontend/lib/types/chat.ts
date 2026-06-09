export type ChatRole = "user" | "assistant";
export type DebateSpeaker = "openai" | "anthropic";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  speaker?: DebateSpeaker;
  label?: string;
}

export interface DebateRequest {
  topic?: string;
  rounds: number;
  openai_model: string;
  anthropic_model: string;
  conversation_id?: string;
  continue_debate?: boolean;
}

export interface DebateStreamEvent {
  type: "thinking" | "turn" | "done" | "error";
  speaker?: DebateSpeaker;
  content?: string;
  model?: string;
  created_at?: string;
  conversation_id?: string;
  topic?: string;
  detail?: string;
}

export interface DebateTurn {
  speaker: DebateSpeaker;
  content: string;
  model: string;
  created_at: string;
}
