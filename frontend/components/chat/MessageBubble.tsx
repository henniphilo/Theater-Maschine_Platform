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
  onPlay
}: {
  message: ChatMessage;
  playable?: boolean;
  playing?: boolean;
  onPlay?: () => void;
}) {
  const title = message.label ?? (message.role === "user" ? "Du" : "Assistent");
  const canPlay = playable && message.speaker && onPlay;

  return (
    <div className={`bubble ${bubbleClass(message)}${playing ? " bubblePlaying" : ""}`}>
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
      ) : (
        <div className="bubbleContent">{message.content}</div>
      )}
    </div>
  );
}
