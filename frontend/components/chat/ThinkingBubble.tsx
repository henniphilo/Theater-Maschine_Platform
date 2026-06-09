import { DebateSpeaker } from "@/lib/types/chat";

const LABELS: Record<DebateSpeaker, string> = {
  openai: "GPT denkt nach …",
  anthropic: "Claude denkt nach …"
};

export function ThinkingBubble({ speaker }: { speaker: DebateSpeaker }) {
  return (
    <div className={`bubble bubbleThinking bubble${speaker === "openai" ? "Openai" : "Anthropic"}`}>
      <strong>{speaker === "openai" ? "GPT" : "Claude"}</strong>
      <div className="thinkingDots">{LABELS[speaker]}</div>
    </div>
  );
}
