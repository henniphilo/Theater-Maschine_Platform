export type MediaVideo = {
  id: string;
  type: string;
  path: string;
  tags: string[];
  moods: string[];
  duration: number;
  loopable: boolean;
};

export type MediaSound = {
  id: string;
  type: string;
  label?: string;
  soundname?: string;
  action?: string;
  description?: string;
  path: string;
  midi_note?: number | null;
  channel?: number;
  ableton_hint?: string;
  tags: string[];
  moods: string[];
};

export type MediaLight = {
  id: string;
  description: string;
  location?: string;
  channels?: string[];
  fixtures?: string[];
  moods: string[];
  fade_time: number;
};

export type MediaCatalog = {
  videos: MediaVideo[];
  recordings: MediaVideo[];
  sounds: MediaSound[];
  lights: MediaLight[];
  light_inventory?: { source?: string; venue?: string };
  media_root?: string;
  touchdesigner: {
    osc_host: string;
    osc_port: number;
    osc_dry_run: boolean;
    addresses: Record<string, string>;
    docs: string;
  };
  pixera?: {
    output: string;
    osc_host: string;
    osc_port: number;
    osc_dry_run: boolean;
    address: string;
  };
  lighting?: {
    output: string;
    osc_mirror: boolean;
    tcp_host: string;
    tcp_port: number;
    tcp_protocol: string;
    osc_host: string;
    osc_port: number;
    preview_osc_host?: string | null;
    preview_osc_port?: number | null;
    preview_set_scene?: string;
    preview_blackout?: string;
    qlab_relay_port?: number | null;
  };
  sound?: {
    output: string;
    osc_mirror: boolean;
    osc_host: string;
    osc_port: number;
    midi_port: string | null;
    midi_channel: number;
    midi_map: string;
  };
  data_dir: string;
};

export type MediaLookup = {
  videoById: Record<string, MediaVideo>;
  soundById: Record<string, MediaSound>;
  lightById: Record<string, MediaLight>;
};

export function formatLightChannelLabel(light: MediaLight): string {
  const channels = light.channels?.filter(Boolean) ?? [];
  if (!channels.length) {
    return light.id;
  }
  return `${light.id} · Kanäle ${channels.join(", ")}`;
}

export function buildMediaLookup(catalog: MediaCatalog): MediaLookup {
  const allVideos = [...catalog.videos, ...(catalog.recordings ?? [])];
  return {
    videoById: Object.fromEntries(allVideos.map((v) => [v.id, v])),
    soundById: Object.fromEntries(catalog.sounds.map((s) => [s.id, s])),
    lightById: Object.fromEntries(catalog.lights.map((l) => [l.id, l]))
  };
}
