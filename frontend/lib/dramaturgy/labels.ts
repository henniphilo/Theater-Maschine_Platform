const FUNCTION_LABELS: Record<string, string> = {
  support: "Unterstützung",
  contrast: "Kontrast",
  intensification: "Intensivierung",
  release: "Reduktion",
  transition: "Übergang",
  recall: "Wiederaufnahme",
  disruption: "Störung",
  foreshadowing: "Andeutung",
  space: "Leerstelle"
};

export function dramaturgicalFunctionLabel(value?: string | null): string {
  if (!value) return "";
  return FUNCTION_LABELS[value] ?? value;
}

export function displayReasonShort(reasonShort?: string | null, reason?: string | null): string {
  const short = reasonShort?.trim();
  if (short) return short;
  return reason?.trim() ?? "";
}

export type CueProposal = {
  proposal_id: string;
  status: string;
  reason_short?: string;
  text_snippet?: string;
  dramaturgical_function?: string | null;
  decision: import("@/lib/types/director").DramaturgyDecision;
  created_at?: string;
};

export type DramaturgyAnalysisEntry = {
  decision_id: string;
  created_at: string;
  text_snippet: string;
  reason_short: string;
  dramaturgical_function: string;
  decision: string;
  decision_status: string;
  cue_id?: string | null;
  executed: boolean;
  blocked_reason?: string | null;
};

export type DramaturgyAnalysisResponse = {
  entries: DramaturgyAnalysisEntry[];
  dramaturgy_state: Record<string, unknown>;
};
