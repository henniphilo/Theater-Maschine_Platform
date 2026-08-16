import { avatarSegmentKey } from "@/features/inszenierung/avatarCuePlayback";
import type { AvatarTextSegment } from "@/lib/types/inszenierung";

export function avatarSegmentLabel(segment: AvatarTextSegment): string {
  const names = segment.avatar_layers.map((layer) => layer.video_clip_id || layer.avatar);
  return names.length > 0 ? names.join(" · ") : segment.csv_cue_ids.join(", ");
}

/** Index of the segment currently playing in the CSV avatar chain (preferred for live UI). */
export function indexOfAvatarSegment(
  segments: AvatarTextSegment[],
  segment: AvatarTextSegment | null | undefined
): number {
  if (!segment) return -1;
  const key = avatarSegmentKey(segment);
  return segments.findIndex((candidate) => avatarSegmentKey(candidate) === key);
}

/**
 * Fallback when the CSV chain has not reported an active segment yet:
 * map TTS sentence index onto avatar sentence spans.
 */
export function activeAvatarSegmentIndex(
  segments: AvatarTextSegment[],
  sentenceIndex: number
): number {
  if (sentenceIndex < 0) return -1;
  return segments.findIndex(
    (segment) =>
      sentenceIndex >= segment.start_sentence_index && sentenceIndex <= segment.end_sentence_index
  );
}
