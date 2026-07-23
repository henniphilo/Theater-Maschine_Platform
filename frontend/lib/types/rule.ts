export type RuleConditionType =
  | "text_contains"
  | "tag"
  | "mood"
  | "intensity_min"
  | "intensity_max"
  | "previous_cue"
  | "manual";

export type RuleActionType =
  | "execute_cue"
  | "select_from_group"
  | "select_random_by_tags"
  | "execute_delayed";

export const RULE_CONDITION_TYPES: RuleConditionType[] = [
  "text_contains",
  "tag",
  "mood",
  "intensity_min",
  "intensity_max",
  "previous_cue",
  "manual"
];

export const RULE_ACTION_TYPES: RuleActionType[] = [
  "execute_cue",
  "select_from_group",
  "select_random_by_tags",
  "execute_delayed"
];

export const RULE_CONDITION_LABELS: Record<RuleConditionType, string> = {
  text_contains: "Text enthält Begriff",
  tag: "Erkannter Tag",
  mood: "Stimmung",
  intensity_min: "Mindestintensität",
  intensity_max: "Höchstintensität",
  previous_cue: "Vorheriger Cue",
  manual: "Manuelle Aktivierung"
};

export const RULE_ACTION_LABELS: Record<RuleActionType, string> = {
  execute_cue: "Bestimmten Cue ausführen",
  select_from_group: "Cue aus Gruppe auswählen",
  select_random_by_tags: "Zufälligen Cue mit Tags auswählen",
  execute_delayed: "Cue verzögert ausführen"
};

export type RuleCondition = {
  type: RuleConditionType;
  term?: string;
  tag?: string;
  mood?: string;
  value?: number;
  cue_id?: string;
  activation_key?: string;
};

export type RuleAction = {
  type: RuleActionType;
  cue_id?: string;
  group?: string;
  tags?: string[];
  delay_seconds?: number;
};

export type Rule = {
  id: string;
  production_id: string;
  name: string;
  enabled: boolean;
  priority: number;
  conditions: RuleCondition[];
  actions: RuleAction[];
  cooldown_seconds: number | null;
  created_at: string;
  updated_at: string;
};

export type RuleCreateInput = {
  production_id: string;
  name: string;
  enabled?: boolean;
  priority?: number;
  conditions: RuleCondition[];
  actions: RuleAction[];
  cooldown_seconds?: number | null;
};

export type RuleUpdateInput = {
  name?: string;
  enabled?: boolean;
  priority?: number;
  conditions?: RuleCondition[];
  actions?: RuleAction[];
  cooldown_seconds?: number | null;
  clear_cooldown_seconds?: boolean;
};

export type LegacyRuleSummary = {
  id: string;
  name: string;
  enabled: boolean;
  priority: number;
  conditions: RuleCondition[];
  actions: RuleAction[];
  cooldown_seconds: number | null;
  source: string;
  meta: Record<string, string>;
};

export type RuleEvaluateResult = {
  production_id: string;
  matches: Array<{
    rule_id: string;
    rule_name: string;
    priority: number;
    source: string;
    planned_actions: Array<{
      action_type: string;
      cue_id?: string | null;
      delay_seconds?: number | null;
      group?: string | null;
      tags?: string[] | null;
      detail: string;
    }>;
  }>;
  skipped_cooldown: string[];
  skipped_disabled: string[];
  skipped_conditions: string[];
};

export function emptyCondition(type: RuleConditionType = "text_contains"): RuleCondition {
  switch (type) {
    case "text_contains":
      return { type, term: "" };
    case "tag":
      return { type, tag: "" };
    case "mood":
      return { type, mood: "" };
    case "intensity_min":
      return { type, value: 0.5 };
    case "intensity_max":
      return { type, value: 1 };
    case "previous_cue":
      return { type, cue_id: "" };
    case "manual":
      return { type, activation_key: "" };
    default:
      return { type: "text_contains", term: "" };
  }
}

export function emptyAction(type: RuleActionType = "execute_cue"): RuleAction {
  switch (type) {
    case "execute_cue":
      return { type, cue_id: "" };
    case "select_from_group":
      return { type, group: "" };
    case "select_random_by_tags":
      return { type, tags: [] };
    case "execute_delayed":
      return { type, cue_id: "", delay_seconds: 1 };
    default:
      return { type: "execute_cue", cue_id: "" };
  }
}

export function summarizeCondition(c: RuleCondition): string {
  switch (c.type) {
    case "text_contains":
      return `Text enthält „${c.term ?? ""}“`;
    case "tag":
      return `Tag ${c.tag ?? ""}`;
    case "mood":
      return `Stimmung ${c.mood ?? ""}`;
    case "intensity_min":
      return `Intensität ≥ ${c.value ?? ""}`;
    case "intensity_max":
      return `Intensität ≤ ${c.value ?? ""}`;
    case "previous_cue":
      return `Vorheriger Cue ${c.cue_id ?? ""}`;
    case "manual":
      return `Manuell „${c.activation_key ?? ""}“`;
    default:
      return c.type;
  }
}

export function summarizeAction(a: RuleAction): string {
  switch (a.type) {
    case "execute_cue":
      return `Cue ${a.cue_id ?? ""}`;
    case "select_from_group":
      return `Gruppe ${a.group ?? ""}`;
    case "select_random_by_tags":
      return `Tags ${(a.tags ?? []).join(", ")}`;
    case "execute_delayed":
      return `Cue ${a.cue_id ?? ""} +${a.delay_seconds ?? 0}s`;
    default:
      return a.type;
  }
}
