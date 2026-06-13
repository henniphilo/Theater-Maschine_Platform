import { useEffect, useRef } from "react";

import { ChatMessage, DebateSpeaker } from "@/lib/types/chat";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ThinkingBubble } from "@/components/chat/ThinkingBubble";
import type { MachineRuntimeState } from "@/features/show/machineRunner";

export function MessageList({
  messages,
  thinking,
  ttsAvailable = false,
  playingMessageId,
  onPlayMessage,
  machine
}: {
  messages: ChatMessage[];
  thinking?: DebateSpeaker | null;
  ttsAvailable?: boolean;
  playingMessageId?: string | null;
  onPlayMessage?: (message: ChatMessage) => void;
  machine?: MachineRuntimeState;
}) {
  const beatRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    const id = machine?.currentMessageId;
    if (!id || !machine?.running) return;
    beatRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [machine?.currentMessageId, machine?.running, machine?.sentenceIndex]);

  return (
    <div className={`chatList${machine?.running ? " chatListMachine" : ""}`} aria-live="polite">
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          playable={ttsAvailable && msg.role === "assistant" && !!msg.speaker}
          playing={playingMessageId === msg.id}
          onPlay={onPlayMessage ? () => onPlayMessage(msg) : undefined}
          beatState={machine?.beatStates[msg.id]}
          sentenceIndex={machine?.currentMessageId === msg.id ? machine.sentenceIndex : undefined}
          activeOscBridge={machine?.currentMessageId === msg.id ? machine.activeOscBridge : null}
          scrollRef={(node) => {
            beatRefs.current[msg.id] = node;
          }}
        />
      ))}
      {thinking ? <ThinkingBubble speaker={thinking} /> : null}
    </div>
  );
}
