import { ChatMessage, DebateSpeaker } from "@/lib/types/chat";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ThinkingBubble } from "@/components/chat/ThinkingBubble";

export function MessageList({
  messages,
  thinking,
  ttsAvailable = false,
  playingMessageId,
  onPlayMessage
}: {
  messages: ChatMessage[];
  thinking?: DebateSpeaker | null;
  ttsAvailable?: boolean;
  playingMessageId?: string | null;
  onPlayMessage?: (message: ChatMessage) => void;
}) {
  return (
    <div className="chatList" aria-live="polite">
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          playable={ttsAvailable && msg.role === "assistant" && !!msg.speaker}
          playing={playingMessageId === msg.id}
          onPlay={onPlayMessage ? () => onPlayMessage(msg) : undefined}
        />
      ))}
      {thinking ? <ThinkingBubble speaker={thinking} /> : null}
    </div>
  );
}
