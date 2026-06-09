"use client";

import { useEffect, useRef, useState } from "react";

import { MessageList } from "@/components/chat/MessageList";
import { fetchSpeechBlob, fetchTTSStatus, playBlob, stopPlayback, streamDebate } from "@/lib/api/client";
import { ChatMessage, DebateSpeaker } from "@/lib/types/chat";
import { PROVIDERS } from "@/features/settings/provider-settings";

const OPENAI_MODELS = PROVIDERS.find((p) => p.value === "openai")?.models ?? ["gpt-4o"];
const ANTHROPIC_MODELS = PROVIDERS.find((p) => p.value === "anthropic")?.models ?? ["claude-sonnet-4-6"];
const CONTINUE_ROUNDS = 2;

function speakerLabel(speaker: DebateSpeaker) {
  return speaker === "openai" ? "GPT (OpenAI)" : "Claude (Anthropic)";
}

export default function Page() {
  const [topic, setTopic] = useState("");
  const [rounds, setRounds] = useState(3);
  const [openaiModel, setOpenaiModel] = useState<string>(OPENAI_MODELS[0]);
  const [anthropicModel, setAnthropicModel] = useState<string>(ANTHROPIC_MODELS[0]);
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [thinking, setThinking] = useState<DebateSpeaker | null>(null);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [ttsHint, setTtsHint] = useState("");
  const [ttsAvailable, setTtsAvailable] = useState(false);
  const [ttsProvider, setTtsProvider] = useState("");
  const abortRef = useRef(false);

  useEffect(() => {
    fetchTTSStatus()
      .then((s) => {
        setTtsAvailable(s.available);
        setTtsHint(s.hint);
        setTtsProvider(s.provider);
      })
      .catch(() => setTtsHint("TTS-Status konnte nicht geladen werden."));
  }, []);

  const debateMessages = messages.filter((m) => m.role === "assistant" && m.speaker);

  async function runDebate(continueDebate: boolean) {
    if (loading) return;
    if (!continueDebate && !topic.trim()) return;
    setError("");
    setLoading(true);
    abortRef.current = false;
    setThinking(null);

    if (!continueDebate) {
      setMessages([
        {
          id: crypto.randomUUID(),
          role: "user",
          content: topic.trim(),
          label: "Thema"
        }
      ]);
    }

    try {
      await streamDebate(
        {
          topic: topic.trim(),
          rounds: continueDebate ? CONTINUE_ROUNDS : rounds,
          openai_model: openaiModel,
          anthropic_model: anthropicModel,
          conversation_id: conversationId,
          continue_debate: continueDebate
        },
        {
          onThinking: (speaker) => setThinking(speaker),
          onTurn: (turn) => {
            setThinking(null);
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "assistant",
                speaker: turn.speaker,
                label: speakerLabel(turn.speaker),
                content: turn.content
              }
            ]);
          },
          onDone: ({ conversation_id }) => {
            setConversationId(conversation_id);
            setThinking(null);
          },
          onError: (detail) => setError(detail)
        }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Debate failed");
    } finally {
      setLoading(false);
      setThinking(null);
    }
  }

  async function handlePlayMessage(msg: ChatMessage) {
    if (!msg.speaker || !ttsAvailable) return;
    stopPlayback();
    setError("");
    setPlayingMessageId(msg.id);
    try {
      const blob = await fetchSpeechBlob(msg.content, msg.speaker);
      await playBlob(blob);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Vertonung fehlgeschlagen");
    } finally {
      setPlayingMessageId(null);
    }
  }

  async function handlePlayDebate() {
    if (playing || debateMessages.length === 0) return;
    stopPlayback();
    setError("");
    setPlaying(true);
    try {
      let nextBlob = fetchSpeechBlob(debateMessages[0].content, debateMessages[0].speaker!);
      for (let i = 0; i < debateMessages.length; i++) {
        if (abortRef.current) break;
        const msg = debateMessages[i];
        const blobPromise = nextBlob;
        if (i + 1 < debateMessages.length) {
          const next = debateMessages[i + 1];
          nextBlob = fetchSpeechBlob(next.content, next.speaker!);
        }
        setPlayingMessageId(msg.id);
        const blob = await blobPromise;
        await playBlob(blob);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Vertonung fehlgeschlagen");
    } finally {
      setPlaying(false);
      setPlayingMessageId(null);
    }
  }

  function handleClear() {
    abortRef.current = true;
    stopPlayback();
    setMessages([]);
    setConversationId(undefined);
    setThinking(null);
  }

  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>AI Debate</h1>
        <a href="/director">Live-Regie →</a>
      </div>
      <p style={{ margin: 0, color: "#6b5e4a" }}>
        GPT und Claude diskutieren live miteinander — kurze Beiträge, sichtbarer Denkstatus.
      </p>

      <section className="card col">
        <h2>Diskussion</h2>
        <label htmlFor="topic">Thema</label>
        <textarea
          id="topic"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          rows={3}
          placeholder="z. B. Soll KI in Schulen eingesetzt werden?"
          disabled={loading}
        />

        <div className="row">
          <div className="col" style={{ flex: 1 }}>
            <label htmlFor="rounds">Start-Runden (je KI pro Runde)</label>
            <select id="rounds" value={rounds} onChange={(e) => setRounds(Number(e.target.value))} disabled={loading}>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n} ({n * 2} Beiträge)
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="row">
          <div className="col" style={{ flex: 1 }}>
            <label htmlFor="openai-model">GPT-Modell</label>
            <select
              id="openai-model"
              value={openaiModel}
              onChange={(e) => setOpenaiModel(e.target.value)}
              disabled={loading}
            >
              {OPENAI_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div className="col" style={{ flex: 1 }}>
            <label htmlFor="anthropic-model">Claude-Modell</label>
            <select
              id="anthropic-model"
              value={anthropicModel}
              onChange={(e) => setAnthropicModel(e.target.value)}
              disabled={loading}
            >
              {ANTHROPIC_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="row">
          <button type="button" onClick={() => runDebate(false)} disabled={loading || !topic.trim()}>
            {loading && !conversationId ? "Diskussion läuft …" : "Diskussion starten"}
          </button>
          <button
            type="button"
            onClick={() => runDebate(true)}
            disabled={loading || !conversationId || debateMessages.length === 0}
          >
            {loading && conversationId ? "Weiter …" : `Weiter diskutieren (+${CONTINUE_ROUNDS} Runden)`}
          </button>
          <button type="button" onClick={handleClear} disabled={loading}>
            Neu
          </button>
        </div>

        <div className="row">
          <button
            type="button"
            onClick={handlePlayDebate}
            disabled={playing || debateMessages.length === 0 || !ttsAvailable}
          >
            {playing
              ? "Spielt ab …"
              : ttsProvider === "say"
                ? "Gespräch vertone (Siri)"
                : "Gespräch vertone"}
          </button>
        </div>

        {ttsHint ? (
          <p style={{ margin: 0, color: "#6b5e4a", fontSize: "0.9rem" }}>{ttsHint}</p>
        ) : null}

        {error ? (
          <div role="alert" style={{ color: "#8b2020" }}>
            {error}
          </div>
        ) : null}
      </section>

      <section className="card col">
        <h2>Debatte</h2>
        {messages.length === 0 && !thinking ? (
          <p style={{ color: "#9c8e78", margin: 0 }}>Thema eingeben und starten.</p>
        ) : (
          <MessageList
            messages={messages}
            thinking={thinking}
            ttsAvailable={ttsAvailable}
            playingMessageId={playingMessageId}
            onPlayMessage={handlePlayMessage}
          />
        )}
      </section>
    </main>
  );
}
