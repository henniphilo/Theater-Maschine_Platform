export const PROVIDERS = [
  { value: "openai", label: "OpenAI", models: ["gpt-4o", "gpt-4o-mini"] },
  { value: "anthropic", label: "Anthropic", models: ["claude-sonnet-4-6", "claude-opus-4-6"] }
] as const;

export type ProviderValue = (typeof PROVIDERS)[number]["value"];
