export type ShowRunFindingView = {
  severity: "critical" | "warn" | "info" | string;
  kind: string;
  title: string;
  interpretation: string;
  action_steps: string[];
  detail: string;
  ts_wall?: string | null;
  count?: number | null;
  duration_ms?: number | null;
  cues: string[];
};

export type ShowRunInterpretationView = {
  verdict: "ok" | "issues" | "critical" | string;
  headline: string;
  summary: string;
  priority_actions: string[];
  findings: ShowRunFindingView[];
};

export type ShowRunAnalysisResponse = {
  run_id: string;
  frontend_run_id?: string | null;
  ts_start?: string | null;
  ts_end?: string | null;
  duration_sec: number;
  executes: number;
  commands_built: number;
  send_completed: number;
  send_failed: number;
  category_counts: Record<string, number>;
  drop_report_count: number;
  interpretation: ShowRunInterpretationView;
};

export type ShowRunListItem = {
  run_id: string;
  ts_start?: string | null;
  event_count: number;
};

export type ShowRunListResponse = {
  runs: ShowRunListItem[];
  trace_path: string;
};
