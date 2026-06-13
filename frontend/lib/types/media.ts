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
  path: string;
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
  data_dir: string;
};

export type MediaLookup = {
  videoById: Record<string, MediaVideo>;
  soundById: Record<string, MediaSound>;
  lightById: Record<string, MediaLight>;
};

export function buildMediaLookup(catalog: MediaCatalog): MediaLookup {
  const allVideos = [...catalog.videos, ...(catalog.recordings ?? [])];
  return {
    videoById: Object.fromEntries(allVideos.map((v) => [v.id, v])),
    soundById: Object.fromEntries(catalog.sounds.map((s) => [s.id, s])),
    lightById: Object.fromEntries(catalog.lights.map((l) => [l.id, l]))
  };
}
