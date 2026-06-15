export type VisualOutputAssignment = {
  output_id: string;
  clip_id?: string | null;
  action?: string | null;
};

export type VisualCue = {
  action: string;
  clip_id?: string | null;
  outputs?: VisualOutputAssignment[];
  recording_id?: string | null;
  blend?: string;
  opacity?: number;
  fade_time?: number;
};

export function formatVisualCueLabel(visual?: VisualCue | null): string {
  if (!visual) return "";
  if (visual.outputs?.length) {
    return visual.outputs
      .map((item) => {
        const clip = item.clip_id || visual.clip_id || "—";
        return `${item.output_id}:${clip}`;
      })
      .join(", ");
  }
  return visual.clip_id || "";
}
