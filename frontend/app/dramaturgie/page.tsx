"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { AppNav } from "@/components/layout/AppNav";
import { RegieCard } from "@/components/show/RegieCard";
import {
  clearDramaturgySession,
  loadDramaturgySession,
  saveDramaturgySession,
  type DramaturgyChatLine
} from "@/features/dramaturgy/session";
import { createScript, streamDramaturgyWorkshop } from "@/lib/api/script";
import { fetchTTSStatus } from "@/lib/api/client";
import type { DirectorPayload } from "@/lib/types/director";
import type { ProductionScript, WorkshopStreamEvent } from "@/lib/types/script";
import { PROVIDERS } from "@/features/settings/provider-settings";

const OPENAI_MODELS = PROVIDERS.find((p) => p.value === "openai")?.models ?? ["gpt-4o"];
const ANTHROPIC_MODELS = PROVIDERS.find((p) => p.value === "anthropic")?.models ?? ["claude-sonnet-4-6"];

export default function DramaturgiePage() {
  const [title, setTitle] = useState("Stück");
  const [sourceText, setSourceText] = useState("");
  const [script, setScript] = useState<ProductionScript | null>(null);
  const [chat, setChat] = useState<DramaturgyChatLine[]>([]);
  const [thinking, setThinking] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [openaiModel, setOpenaiModel] = useState<string>(OPENAI_MODELS[0]);
  const [anthropicModel, setAnthropicModel] = useState<string>(ANTHROPIC_MODELS[0]);
  const [ttsHint, setTtsHint] = useState("");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const saved = loadDramaturgySession();
    if (saved) {
      setTitle(saved.title);
      setSourceText(saved.sourceText);
      setChat(saved.chat);
      setOpenaiModel(saved.openaiModel);
      setAnthropicModel(saved.anthropicModel);
      if (saved.scriptId) {
        sessionStorage.setItem("currentScriptId", saved.scriptId);
        void import("@/lib/api/script").then(({ fetchScript }) =>
          fetchScript(saved.scriptId!).then(setScript).catch(() => undefined)
        );
      }
    } else {
      const scriptId = sessionStorage.getItem("currentScriptId");
      if (scriptId) {
        void import("@/lib/api/script").then(({ fetchScript }) =>
          fetchScript(scriptId).then(setScript).catch(() => sessionStorage.removeItem("currentScriptId"))
        );
      }
    }
    setHydrated(true);
    fetchTTSStatus()
      .then((s) => setTtsHint(s.hint))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveDramaturgySession({
      title,
      sourceText,
      scriptId: script?.id ?? null,
      chat,
      openaiModel,
      anthropicModel
    });
  }, [hydrated, title, sourceText, script?.id, chat, openaiModel, anthropicModel]);

  function handleWorkshopEvent(event: WorkshopStreamEvent) {
    if (event.type === "thinking" && event.speaker) {
      setThinking(event.speaker === "openai" ? "Dramaturg A denkt …" : "Dramaturg B denkt …");
      return;
    }
    if (event.type === "discussion_turn" && event.content && event.speaker) {
      const content = event.content;
      const speaker = event.speaker;
      setThinking(null);
      setChat((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          speaker: speaker === "openai" ? "Dramaturg A (GPT)" : "Dramaturg B (Claude)",
          content,
          beatOrder: event.beat_order
        }
      ]);
      return;
    }
    if (event.type === "dramaturgy_decision" && event.dramaturgy) {
      const dramaturgy = event.dramaturgy;
      setChat((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          speaker: `Regie · Abschnitt ${(event.beat_order ?? 0) + 1}`,
          content: dramaturgy.reason,
          beatOrder: event.beat_order,
          director: {
            event: {},
            decision: dramaturgy,
            executed: false,
            blocked_reason: null,
            planned_commands: event.planned_commands ?? [],
            osc_commands: []
          } as DirectorPayload
        }
      ]);
      return;
    }
    if (event.type === "script_updated" && event.script) {
      setScript(event.script);
      sessionStorage.setItem("currentScriptId", event.script.id);
    }
    if (event.type === "done") {
      setThinking(null);
      setLoading(false);
    }
  }

  async function startWorkshop() {
    if (!sourceText.trim() || loading) return;
    setError("");
    setLoading(true);
    setChat([]);
    clearDramaturgySession();
    setThinking(null);
    try {
      const created = await createScript(title, sourceText);
      setScript(created);
      sessionStorage.setItem("currentScriptId", created.id);
      await streamDramaturgyWorkshop(
        created.id,
        { openai_model: openaiModel, anthropic_model: anthropicModel, discussion_rounds: 3 },
        {
          onEvent: handleWorkshopEvent,
          onError: (detail) => setError(detail)
        }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Workshop fehlgeschlagen");
    } finally {
      setLoading(false);
      setThinking(null);
    }
  }

  const canOpenScript = script && script.beats.length > 0;

  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Dramaturgie</h1>
        <AppNav />
      </div>
      <p className="textMuted">
        Stücktext einfügen — zwei KIs diskutieren die Regie (Video, Sound, Licht) für jeden Abschnitt.
      </p>

      <section className="card col">
        <label htmlFor="title">Titel</label>
        <input id="title" value={title} onChange={(e) => setTitle(e.target.value)} disabled={loading} />

        <label htmlFor="source">Stücktext</label>
        <textarea
          id="source"
          rows={10}
          value={sourceText}
          onChange={(e) => setSourceText(e.target.value)}
          placeholder={"Abschnitte mit Leerzeile oder --- trennen.\n\nVielleicht ist Erinnerung nur eine technische Störung."}
          disabled={loading}
        />

        <div className="row">
          <div className="col" style={{ flex: 1 }}>
            <label htmlFor="openai-model">GPT-Modell</label>
            <select id="openai-model" value={openaiModel} onChange={(e) => setOpenaiModel(e.target.value)} disabled={loading}>
              {OPENAI_MODELS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <div className="col" style={{ flex: 1 }}>
            <label htmlFor="anthropic-model">Claude-Modell</label>
            <select id="anthropic-model" value={anthropicModel} onChange={(e) => setAnthropicModel(e.target.value)} disabled={loading}>
              {ANTHROPIC_MODELS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        </div>

        <button type="button" onClick={() => void startWorkshop()} disabled={loading || !sourceText.trim()}>
          {loading ? "Dramaturgie läuft …" : "Dramaturgie starten"}
        </button>

        {canOpenScript ? (
          <Link className="machineStartBtn" href={`/stueck?id=${script!.id}`} style={{ display: "inline-block", textAlign: "center", textDecoration: "none" }}>
            Stücktext ansehen →
          </Link>
        ) : null}

        {ttsHint ? <p className="textMuted" style={{ fontSize: "0.9rem" }}>{ttsHint}</p> : null}
        {error ? <div className="textError" role="alert">{error}</div> : null}
      </section>

      <section className="card col">
        <h2>Dramaturgie-Diskussion</h2>
        {chat.length === 0 && !thinking ? (
          <p className="textFaint">Noch keine Diskussion — Stücktext eingeben und starten.</p>
        ) : (
          <div className="chatList">
            {chat.map((line) => (
              <div key={line.id} className="bubble bubbleAi">
                <strong>{line.speaker}</strong>
                <div className="bubbleContent">{line.content}</div>
                {line.director ? (
                  <RegieCard director={line.director} showPhase="planned" />
                ) : null}
              </div>
            ))}
            {thinking ? <p className="textMuted">{thinking}</p> : null}
          </div>
        )}
      </section>
    </main>
  );
}
