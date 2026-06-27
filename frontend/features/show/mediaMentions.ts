import type { DramaturgyDecision } from "@/lib/types/director";
import type { MediaCatalog, MediaSound } from "@/lib/types/media";
import type { MediaMention, DiscussionTurn } from "@/lib/types/script";

type MediaMentionMedium = MediaMention["medium"];

export type MediaAllowlist = {
  sounds: Set<string>;
  music: Set<string>;
  videos: Set<string>;
  lights: Set<string>;
};

const DASH_SEP = String.raw`(?:[:\u2014\u2013\-]|\s+)`;
const MENTION_LINE = new RegExp(
  String.raw`^[\s]*[-*•]\s*([a-z][a-z0-9_]*)\s*${DASH_SEP}\s*(.+?)\s*$`,
  "gim"
);
const BACKTICK_BULLET = new RegExp(
  String.raw`^[\s]*[-*•]\s*\`([a-z][a-z0-9_]*)\`(?:\s*[:\u2014\u2013\-]\s*(.*))?\s*$`,
  "gim"
);
const BACKTICK_INLINE = /`([a-z][a-z0-9_]*)`/g;
const QUOTE_RE = /«([^»]{2,80})»/;
const THEMA_RE = /Thema:\s*([^/\n«]{2,80})/i;

export type MediaAliasIndex = Map<string, { mediaId: string; medium: MediaMentionMedium }>;

function classifyId(id: string, allowlist: MediaAllowlist): MediaMentionMedium | null {
  if (allowlist.music.has(id)) return "music";
  if (allowlist.sounds.has(id)) return "sound";
  if (allowlist.videos.has(id)) return "video";
  if (allowlist.lights.has(id)) return "light";
  return null;
}

export function buildMediaAliasIndex(catalog: MediaCatalog): MediaAliasIndex {
  const index: MediaAliasIndex = new Map();
  const musicTags = new Set(["musik", "music"]);

  for (const item of catalog.sounds) {
    const soundId = item.id;
    const medium: MediaMentionMedium = item.tags.some((tag) => musicTags.has(tag.toLowerCase()))
      ? "music"
      : "sound";
    index.set(soundId, { mediaId: soundId, medium });
    for (const tag of item.tags) {
      index.set(tag.toLowerCase(), { mediaId: soundId, medium });
    }
    for (const part of soundId.split("_")) {
      if (part.length >= 4 && !index.has(part)) {
        index.set(part, { mediaId: soundId, medium });
      }
    }
  }

  for (const item of [...catalog.videos, ...(catalog.recordings ?? [])]) {
    index.set(item.id, { mediaId: item.id, medium: "video" });
    for (const tag of item.tags) {
      index.set(tag.toLowerCase(), { mediaId: item.id, medium: "video" });
    }
  }

  for (const item of catalog.lights) {
    index.set(item.id, { mediaId: item.id, medium: "light" });
    for (const mood of item.moods) {
      index.set(mood.toLowerCase(), { mediaId: item.id, medium: "light" });
    }
  }

  return index;
}

export function resolveMediaId(
  candidate: string,
  allowlist: MediaAllowlist,
  aliasIndex: MediaAliasIndex,
  options?: {
    context?: string;
    mediumHint?: MediaMentionMedium;
    catalog?: MediaCatalog | null;
  }
): { mediaId: string; medium: MediaMentionMedium } | null {
  const normalized = candidate.toLowerCase().trim();
  const direct = classifyId(normalized, allowlist);
  if (direct) return { mediaId: normalized, medium: direct };

  if (
    aliasIndex.has(normalized) &&
    (allowlist.sounds.has(normalized) ||
      allowlist.music.has(normalized) ||
      allowlist.videos.has(normalized) ||
      allowlist.lights.has(normalized))
  ) {
    return aliasIndex.get(normalized)!;
  }

  if (options?.catalog) {
    const invented = resolveInventedFromCatalog(
      normalized,
      options.context ?? "",
      options.catalog,
      options.mediumHint
    );
    if (invented && classifyId(invented.mediaId, allowlist)) {
      return invented;
    }
  }
  return null;
}

const MUSIC_TAGS = new Set(["musik", "music"]);
const BED_TAGS = new Set(["drone", "grundton", "dauer", "ambient", "atmo", "pad"]);

function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss");
}

function tokens(text: string): Set<string> {
  const base = new Set(
    (text.match(/[a-zäöüß]{3,}/gi) ?? []).map((token) => normalizeText(token))
  );
  return base;
}

function scoreCatalogItem(
  query: string,
  item: { id: string; tags?: string[]; moods?: string[]; description?: string; label?: string }
): number {
  const queryTokens = tokens(query);
  const normalizedQuery = normalizeText(query);
  let score = 0;
  if (normalizedQuery.includes(item.id.replace(/_/g, " "))) score += 8;
  for (const tag of item.tags ?? []) {
    const tagNorm = normalizeText(tag);
    if (normalizedQuery.includes(tagNorm)) score += 4;
    if (queryTokens.has(tagNorm)) score += 3;
  }
  for (const mood of item.moods ?? []) {
    const moodNorm = normalizeText(mood);
    if (normalizedQuery.includes(moodNorm)) score += 3;
    if (queryTokens.has(moodNorm)) score += 2;
  }
  for (const field of [item.description ?? "", item.label ?? "", item.id.replace(/_/g, " ")]) {
    for (const token of tokens(field)) {
      if (queryTokens.has(token)) score += 1.25;
    }
  }
  return score;
}

function resolveInventedFromCatalog(
  candidate: string,
  context: string,
  catalog: MediaCatalog,
  mediumHint?: MediaMentionMedium
): { mediaId: string; medium: MediaMentionMedium } | null {
  const query = `${candidate} ${context}`.trim();
  const soundItems = catalog.sounds.filter((s) => s.action === "play" || !s.action);
  const scoreSounds = (items: MediaSound[], medium: MediaMentionMedium) => {
    let best: { mediaId: string; medium: MediaMentionMedium } | null = null;
    let bestScore = 0;
    for (const item of items) {
      const score = scoreCatalogItem(query, {
        id: item.id,
        tags: item.tags,
        moods: item.moods,
        description: item.description,
        label: item.soundname ?? item.label
      });
      if (score > bestScore) {
        bestScore = score;
        best = { mediaId: item.id, medium };
      }
    }
    return bestScore >= 2 ? best : null;
  };

  if (mediumHint === "sound") {
    return scoreSounds(
      soundItems.filter(
        (s) =>
          !s.tags.some((t) => MUSIC_TAGS.has(t.toLowerCase())) ||
          s.tags.some((t) => BED_TAGS.has(t.toLowerCase()))
      ),
      "sound"
    );
  }
  if (mediumHint === "music") {
    return scoreSounds(
      soundItems.filter((s) => s.tags.some((t) => MUSIC_TAGS.has(t.toLowerCase()))),
      "music"
    );
  }
  if (mediumHint === "video") {
    return scorePool(query, [...catalog.videos, ...(catalog.recordings ?? [])], "video");
  }
  if (mediumHint === "light") {
    return scorePool(query, catalog.lights.filter((l) => l.id !== "blackout"), "light");
  }

  return (
    scoreSounds(soundItems, "sound") ??
    scorePool(query, [...catalog.videos, ...(catalog.recordings ?? [])], "video") ??
    scorePool(query, catalog.lights.filter((l) => l.id !== "blackout"), "light")
  );
}

function scorePool(
  query: string,
  items: Array<{ id: string; tags?: string[]; moods?: string[]; description?: string; label?: string }>,
  medium: MediaMentionMedium
): { mediaId: string; medium: MediaMentionMedium } | null {
  let best: { mediaId: string; medium: MediaMentionMedium } | null = null;
  let bestScore = 0;
  for (const item of items) {
    const score = scoreCatalogItem(query, item);
    if (score > bestScore) {
      bestScore = score;
      best = { mediaId: item.id, medium };
    }
  }
  return bestScore >= 2 ? best : null;
}

const MOOD_KEYWORD_RE = /«([^»]{2,80})»/g;
const MEDIUM_IN_PARENS_RE = /\((Sounds?|Musik|Videos?|Licht(?:stimmungen)?)\)/gi;
const MEDIUM_LABEL_RE = /(Sounds?|Musik|Videos?|Licht(?:stimmungen)?)\s*:\s*([^;«]+)/gi;
const ID_BULLET_RE = /^[\s]*[-*•]\s*(?:`([a-z][a-z0-9_]*)`|([a-z][a-z0-9_]*))\s*(?:[:\u2014\u2013\-]|\s+)/i;

function mediumFromLabel(label: string): MediaMentionMedium {
  const lowered = label.toLowerCase();
  if (lowered.startsWith("sound")) return "sound";
  if (lowered === "musik") return "music";
  if (lowered.startsWith("video")) return "video";
  return "light";
}

function isIdBulletLine(line: string): boolean {
  return ID_BULLET_RE.test(line.trim());
}

function parseMoodSegments(line: string): Array<{ medium: MediaMentionMedium; mood: string }> {
  const segments: Array<{ medium: MediaMentionMedium; mood: string }> = [];
  for (const match of line.matchAll(MEDIUM_LABEL_RE)) {
    segments.push({ medium: mediumFromLabel(match[1]), mood: match[2].trim() });
  }
  for (const match of line.matchAll(MEDIUM_IN_PARENS_RE)) {
    const medium = mediumFromLabel(match[1]);
    let before = line.slice(0, match.index ?? 0);
    if (before.includes("»")) {
      before = before.split("»").slice(1).join("»");
    }
    const mood = before.trim().replace(/^[- \u2013\u2014:;,.]+|[- \u2013\u2014:;,.]+$/g, "");
    if (mood) segments.push({ medium, mood });
  }
  if (segments.length > 0) return segments;

  const quoteEnd = line.indexOf("»");
  if (quoteEnd >= 0) {
    const fallback = line.slice(quoteEnd + 1).trim().replace(/^[- \u2013\u2014:;,.]+|[- \u2013\u2014:;,.]+$/g, "");
    if (fallback) segments.push({ medium: "sound", mood: fallback });
  }
  return segments;
}

function resolveMoodToMedia(
  moodText: string,
  medium: MediaMentionMedium,
  allowlist: MediaAllowlist,
  catalog?: MediaCatalog | null
): { mediaId: string; medium: MediaMentionMedium } | null {
  const query = moodText.trim();
  if (!query) return null;
  return resolveInventedFromCatalog(query, query, catalog ?? null, medium);
}

function spokenPhraseForMood(
  keyword: string,
  medium: MediaMentionMedium,
  moodText: string
): string {
  const label = MEDIUM_LABEL[medium];
  const cleanMood = moodText.replace(/[*_`]/g, "").trim().replace(/[.,;]+$/, "");
  return `Beim Stichwort «${keyword}»: ${cleanMood} (${label}).`;
}

function keywordFromRest(rest: string): string | null {
  const quote = rest.match(QUOTE_RE);
  if (quote?.[1]) return quote[1].trim().slice(0, 80);
  const thema = rest.match(THEMA_RE);
  if (thema?.[1]) return thema[1].trim().slice(0, 80);
  return null;
}

function appendMention(
  mentions: MediaMention[],
  seen: Set<string>,
  mention: MediaMention
): void {
  const key = `${mention.media_id}:${mention.char_offset}`;
  if (seen.has(key)) return;
  seen.add(key);
  mentions.push(mention);
}

export function extractMediaMentions(
  text: string,
  allowlist: MediaAllowlist,
  aliasIndex?: MediaAliasIndex,
  catalog?: MediaCatalog | null
): MediaMention[] {
  const index = aliasIndex ?? new Map();
  const mentions: MediaMention[] = [];
  const seen = new Set<string>();
  const resolveOpts = (context: string, mediumHint?: MediaMentionMedium) => ({
    context,
    mediumHint,
    catalog
  });

  for (const match of text.matchAll(BACKTICK_BULLET)) {
    const resolved = resolveMediaId(match[1], allowlist, index, resolveOpts(match[2] ?? ""));
    if (!resolved) continue;
    appendMention(mentions, seen, {
      medium: resolved.medium,
      media_id: resolved.mediaId,
      keyword: keywordFromRest(match[2] ?? ""),
      char_offset: match.index ?? 0
    });
  }

  for (const match of text.matchAll(MENTION_LINE)) {
    const resolved = resolveMediaId(match[1], allowlist, index, resolveOpts(match[2] ?? ""));
    if (!resolved) continue;
    appendMention(mentions, seen, {
      medium: resolved.medium,
      media_id: resolved.mediaId,
      keyword: keywordFromRest(match[2] ?? ""),
      char_offset: match.index ?? 0
    });
  }

  for (const match of text.matchAll(BACKTICK_INLINE)) {
    const resolved = resolveMediaId(match[1], allowlist, index, resolveOpts(text));
    if (!resolved) continue;
    const offset = match.index ?? 0;
    if (mentions.some((m) => m.media_id === resolved.mediaId && Math.abs(m.char_offset - offset) < 40)) {
      continue;
    }
    appendMention(mentions, seen, {
      medium: resolved.medium,
      media_id: resolved.mediaId,
      keyword: null,
      char_offset: offset
    });
  }

  return mentions.sort((a, b) => a.char_offset - b.char_offset);
}

export function decisionForMediaMention(mention: MediaMention): DramaturgyDecision {
  if (mention.medium === "sound" || mention.medium === "music") {
    return {
      sound: { action: "trigger_cue", cue_id: mention.media_id, volume: 0.65 },
      reason: `Dramaturgen nennen ${mention.media_id}`,
      tags: [],
      mood: "neutral",
      intensity: 0.5,
      timestamp: Date.now()
    };
  }
  if (mention.medium === "video") {
    return {
      visual: {
        action: "play_clip",
        clip_id: mention.media_id
      },
      reason: `Dramaturgen nennen ${mention.media_id}`,
      tags: [],
      mood: "neutral",
      intensity: 0.5,
      timestamp: Date.now()
    };
  }
  return {
    light: { action: "set_scene", scene_id: mention.media_id, intensity: 0.55 },
    reason: `Dramaturgen nennen ${mention.media_id}`,
    tags: [],
    mood: "neutral",
    intensity: 0.5,
    timestamp: Date.now()
  };
}

export function mentionKey(mention: MediaMention): string {
  return `${mention.media_id}:${mention.char_offset}`;
}

export function textPositionForPlayback(
  currentTime: number,
  duration: number,
  textLength: number
): number {
  if (!Number.isFinite(duration) || duration <= 0) return 0;
  return Math.min(textLength, Math.max(0, (currentTime / duration) * textLength));
}

export function mentionsDueAtPosition(
  mentions: MediaMention[],
  textPosition: number,
  fired: Set<string>
): MediaMention[] {
  return mentions.filter((mention) => {
    const key = mentionKey(mention);
    return !fired.has(key) && textPosition >= mention.char_offset;
  });
}

export function allowlistFromPart1Selection(selection: {
  final_sounds: string[];
  final_music: string[];
  final_videos: string[];
  final_lights: string[];
}): MediaAllowlist {
  return {
    sounds: new Set(selection.final_sounds),
    music: new Set(selection.final_music),
    videos: new Set(selection.final_videos),
    lights: new Set(selection.final_lights)
  };
}

export function allowlistFromCatalog(catalog: MediaCatalog): MediaAllowlist {
  const musicTags = new Set(["musik", "music"]);
  const sounds = new Set<string>();
  const music = new Set<string>();
  for (const item of catalog.sounds) {
    if (item.tags.some((tag) => musicTags.has(tag.toLowerCase()))) {
      music.add(item.id);
    } else {
      sounds.add(item.id);
    }
  }
  return {
    sounds,
    music,
    videos: new Set([...catalog.videos, ...(catalog.recordings ?? [])].map((v) => v.id)),
    lights: new Set(catalog.lights.map((l) => l.id))
  };
}

const MEDIUM_LABEL: Record<MediaMentionMedium, string> = {
  sound: "Sound",
  music: "Musik",
  video: "Video",
  light: "Licht"
};

function mediumFromSection(line: string): MediaMentionMedium | undefined {
  const match = line.match(/\*\*(Sounds?|Musik|Videos?|Licht(?:stimmungen)?)\*\*/i);
  if (!match) return undefined;
  const label = match[1].toLowerCase();
  if (label.startsWith("sound")) return "sound";
  if (label === "musik") return "music";
  if (label.startsWith("video")) return "video";
  return "light";
}

export function buildSpokenPlaybackWithMentions(
  raw: string,
  allowlist: MediaAllowlist,
  aliasIndex?: MediaAliasIndex,
  catalog?: MediaCatalog | null
): { spoken: string; mentions: MediaMention[] } {
  const index = aliasIndex ?? new Map();
  const spokenLines: string[] = [];
  const mentions: MediaMention[] = [];
  const seen = new Set<string>();
  let offset = 0;
  let sectionHint: MediaMentionMedium | undefined;

  for (const line of raw.split(/\r?\n/)) {
    const stripped = line.trim();
    if (!stripped || stripped.startsWith("```") || /^\s*\{[^{}]*"sounds"/.test(stripped)) {
      continue;
    }

    sectionHint = mediumFromSection(line) ?? sectionHint;

    const keywordMatch = line.match(/«([^»]{2,80})»/);
    const moodSegments = keywordMatch ? parseMoodSegments(line) : [];
    if (keywordMatch && moodSegments.length > 0 && !isIdBulletLine(stripped)) {
      const keyword = keywordMatch[1].trim();
      const lineStart = offset;
      for (const { medium, mood } of moodSegments) {
        const resolved = resolveMoodToMedia(mood, medium, allowlist, catalog);
        if (!resolved) continue;
        const phrase = spokenPhraseForMood(keyword, resolved.medium, mood);
        appendMention(mentions, seen, {
          medium: resolved.medium,
          media_id: resolved.mediaId,
          keyword,
          char_offset: lineStart
        });
        spokenLines.push(phrase);
        offset += phrase.length + 1;
      }
      continue;
    }

    const bullet = line.match(/^[\s]*[-*•]\s*`([a-z][a-z0-9_]*)`(?:\s*[:\u2014\u2013\-]\s*(.*))?\s*$/i)
      ?? line.match(new RegExp(String.raw`^[\s]*[-*•]\s*([a-z][a-z0-9_]*)\s*${DASH_SEP}\s*(.+?)\s*$`, "i"));

    if (bullet) {
      const rest = bullet[2] ?? "";
      const resolved = resolveMediaId(bullet[1], allowlist, index, {
        context: rest,
        mediumHint: sectionHint,
        catalog
      });
      if (resolved) {
        let phrase = `${MEDIUM_LABEL[resolved.medium]} ${resolved.mediaId.replace(/_/g, " ")}.`;
        const keyword = keywordFromRest(rest);
        if (rest.trim()) {
          const short = rest.replace(/[*_`]/g, "").trim().slice(0, 90).replace(/[.,;]+$/, "");
          if (short) phrase += ` ${short}.`;
        }
        appendMention(mentions, seen, {
          medium: resolved.medium,
          media_id: resolved.mediaId,
          keyword,
          char_offset: offset
        });
        spokenLines.push(phrase);
        offset += phrase.length + 1;
        continue;
      }
    }

    const inlineIds = [...line.matchAll(BACKTICK_INLINE)];
    if (inlineIds.length > 0 && (line.includes(":") || line.includes("**"))) {
      for (const match of inlineIds) {
        const resolved = resolveMediaId(match[1], allowlist, index, {
          context: line,
          mediumHint: sectionHint,
          catalog
        });
        if (!resolved) continue;
        const phrase = `${MEDIUM_LABEL[resolved.medium]} ${resolved.mediaId.replace(/_/g, " ")}.`;
        appendMention(mentions, seen, {
          medium: resolved.medium,
          media_id: resolved.mediaId,
          keyword: null,
          char_offset: offset
        });
        spokenLines.push(phrase);
        offset += phrase.length + 1;
      }
      continue;
    }

    if (/^\s*\*\*[^*]+\*\*\s*$/.test(line)) {
      const header = stripped.replace(/\*\*([^*]+)\*\*/g, "$1") + ".";
      spokenLines.push(header);
      offset += header.length + 1;
      continue;
    }

    const clean = line.replace(/\*\*([^*]+)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1").trim();
    if (clean) {
      spokenLines.push(clean);
      offset += clean.length + 1;
    }
  }

  const spoken = spokenLines.join("\n").trim();
  if (!spoken) {
    return { spoken: raw, mentions: extractMediaMentions(raw, allowlist, index, catalog) };
  }
  return { spoken, mentions };
}

export function resolveTurnPlayback(
  turn: DiscussionTurn,
  allowlist: MediaAllowlist | null,
  aliasIndex?: MediaAliasIndex,
  catalog?: MediaCatalog | null
): { spoken: string; mentions: MediaMention[] } {
  if (!allowlist) {
    return { spoken: turn.content, mentions: turn.media_mentions ?? [] };
  }

  const stored = turn.media_mentions ?? [];
  if (stored.length > 0) {
    const maxOffset = Math.max(...stored.map((m) => m.char_offset));
    if (maxOffset <= turn.content.length) {
      return { spoken: turn.content, mentions: stored };
    }
  }

  return buildSpokenPlaybackWithMentions(turn.content, allowlist, aliasIndex, catalog);
}
