"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { AppNav } from "@/components/layout/AppNav";
import { ScriptBeatBlock } from "@/components/script/ScriptBeatBlock";
import { fetchMediaCatalog } from "@/lib/api/media";
import { fetchScript, patchScriptBeat } from "@/lib/api/script";
import { buildMediaLookup, type MediaLookup } from "@/lib/types/media";
import type { ProductionScript, ScriptSpeaker } from "@/lib/types/script";

function StueckContent() {
  const searchParams = useSearchParams();
  const scriptId = searchParams.get("id") ?? sessionStorage.getItem("currentScriptId") ?? "";
  const [script, setScript] = useState<ProductionScript | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [media, setMedia] = useState<MediaLookup | undefined>();

  const load = useCallback(async () => {
    if (!scriptId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await fetchScript(scriptId);
      setScript(data);
      sessionStorage.setItem("currentScriptId", data.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stück nicht gefunden");
    } finally {
      setLoading(false);
    }
  }, [scriptId]);

  useEffect(() => {
    void load();
    fetchMediaCatalog()
      .then((c) => setMedia(buildMediaLookup(c)))
      .catch(() => undefined);
  }, [load]);

  async function handleSpeakerChange(beatId: string, speaker: ScriptSpeaker) {
    if (!script) return;
    try {
      const updated = await patchScriptBeat(script.id, beatId, { speaker });
      setScript(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update fehlgeschlagen");
    }
  }

  const ready = script?.status === "ready";

  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Stücktext</h1>
        <AppNav />
      </div>
      <p className="textMuted">Gesamter Text mit eingezeichneten Regieentscheidungen — ohne Wiedergabe.</p>

      {loading ? <p className="textFaint">Lade Stück …</p> : null}
      {error ? <div className="textError" role="alert">{error}</div> : null}
      {!scriptId && !loading ? (
        <p className="textFaint">
          Kein Stück geladen. <Link href="/dramaturgie">Dramaturgie starten</Link>
        </p>
      ) : null}

      {script ? (
        <>
          <section className="card col">
            <h2>{script.title}</h2>
            <p className="textMuted">Status: {script.status} · {script.beats.length} Abschnitte</p>
            {ready ? (
              <Link href={`/auffuehrung?id=${script.id}`} className="machineStartBtn" style={{ display: "inline-block", textAlign: "center", textDecoration: "none" }}>
                Zur Aufführung →
              </Link>
            ) : (
              <p className="textFaint">Zur Aufführung erst nach vollständiger Dramaturgie (status: ready).</p>
            )}
          </section>

          <section className="card col scriptDocument">
            {script.beats.map((beat) => (
              <ScriptBeatBlock
                key={beat.id}
                beat={beat}
                editable
                media={media}
                onSpeakerChange={(speaker) => void handleSpeakerChange(beat.id, speaker)}
              />
            ))}
          </section>
        </>
      ) : null}
    </main>
  );
}

export default function StueckPage() {
  return (
    <Suspense fallback={<main className="container"><p className="textFaint">Lade …</p></main>}>
      <StueckContent />
    </Suspense>
  );
}
