import { RegieCard } from "@/components/show/RegieCard";
import { ScriptContent } from "@/components/show/ScriptContent";
import type { MachineBeatState } from "@/features/show/machineRunner";
import { ChatMessage } from "@/lib/types/chat";

function bubbleClass(message: ChatMessage): string {
  if (message.role === "user") return "bubbleUser";
  if (message.speaker === "openai") return "bubbleOpenai";
  if (message.speaker === "anthropic") return "bubbleAnthropic";
  return "bubbleAi";
}

export function MessageBubble({
  message,
  playable = false,
  playing = false,
  onPlay,
  beatState,
  sentenceIndex,
  activeOscBridge,
  scrollRef
}: {
  message: ChatMessage;
  playable?: boolean;
  playing?: boolean;
  onPlay?: () => void;
  beatState?: MachineBeatState;
  sentenceIndex?: number;
  activeOscBridge?: string | null;
  scrollRef?: (node: HTMLDivElement | null) => void;
}) {
  const title = message.label ?? (message.role === "user" ? "Du" : "Assistent");
  const canPlay = playable && message.speaker && onPlay;
  const beatClass =
    beatState === "current"
      ? " bubbleBeatCurrent"
      : beatState === "past"
        ? " bubbleBeatPast"
        : beatState === "future"
          ? " bubbleBeatFuture"
          : "";
  const isCurrentBeat = beatState === "current";

  return (
    <div
      ref={scrollRef}
      className={`bubble ${bubbleClass(message)}${playing || isCurrentBeat ? " bubblePlaying" : ""}${beatClass}`}
    >
      <strong>{title}</strong>
      {canPlay ? (
        <button
          type="button"
          className="bubbleContent bubbleContentPlayable"
          onClick={onPlay}
          aria-label={`${title} abspielen`}
        >
          {playing ? "▶ " : ""}
          {message.content}
        </button>
      ) : isCurrentBeat ? (
        <ScriptContent text={message.content} activeSentenceIndex={sentenceIndex} />
      ) : (
        <div className="bubbleContent">{message.content}</div>
      )}
      {message.director ? (
        <RegieCard
          director={message.director}
          showPhase={message.showPhase}
          oscCommands={message.osc_commands}
          activeOscBridge={isCurrentBeat ? activeOscBridge : null}
        />
      ) : null}
    </div>
  );
}
