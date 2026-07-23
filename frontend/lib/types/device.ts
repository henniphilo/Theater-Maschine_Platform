export type AdapterType = "dry_run" | "osc" | "midi" | "pixera" | "eos_tcp";

export const ADAPTER_TYPES: AdapterType[] = [
  "dry_run",
  "osc",
  "midi",
  "pixera",
  "eos_tcp"
];

export const ADAPTER_TYPE_LABELS: Record<AdapterType, string> = {
  dry_run: "Dry Run (Standard)",
  osc: "OSC (TouchDesigner)",
  midi: "MIDI",
  pixera: "Pixera OSC",
  eos_tcp: "EOS TCP (Licht)"
};

export type Device = {
  id: string;
  production_id: string | null;
  name: string;
  adapter_type: AdapterType;
  enabled: boolean;
  /** Public keys only — hosts/ports/secrets are never returned. */
  configuration: Record<string, unknown>;
  configuration_keys: string[];
  has_sensitive_configuration: boolean;
  created_at: string;
  updated_at: string;
};

export type DeviceCreateInput = {
  production_id?: string | null;
  name: string;
  adapter_type?: AdapterType;
  enabled?: boolean;
  configuration?: Record<string, unknown>;
};

export type DeviceUpdateInput = {
  name?: string;
  adapter_type?: AdapterType;
  enabled?: boolean;
  configuration?: Record<string, unknown>;
  production_id?: string | null;
  clear_production_id?: boolean;
};

export type DeviceConnectionTestResult = {
  device_id: string;
  adapter_type: AdapterType;
  ok: boolean;
  message: string;
  dry_run: boolean;
  details: Record<string, unknown>;
};

/** Default write form for connection params (sent on create/update only). */
export function defaultConfigurationFor(type: AdapterType): Record<string, unknown> {
  switch (type) {
    case "dry_run":
      return { notes: "" };
    case "osc":
      return { host: "127.0.0.1", port: 7000, force_dry_run: true };
    case "midi":
      return { midi_port: "", force_dry_run: true };
    case "pixera":
      return { host: "127.0.0.1", port: 8990, force_dry_run: true };
    case "eos_tcp":
      return { host: "127.0.0.1", port: 3032, force_dry_run: true };
    default:
      return {};
  }
}
