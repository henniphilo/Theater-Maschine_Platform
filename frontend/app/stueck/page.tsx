"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { AppNav } from "@/components/layout/AppNav";
import { ScriptBeatBlock } from "@/components/script/ScriptBeatBlock";
import { fetchMediaCatalog } from "@/lib/api/media";
import { fetchScript, patchScriptBeat } from "@/lib/api/script";
import { buildMediaLookup, type MediaLookup } from "@/lib/types/media";
import { isBaerenklauBeat, isPart1Beat } from "@/lib/show/baerenklauBeat";
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
            <p className="textMuted">
              Status: {script.status} ·{" "}
              {script.beats.length === 1 ? "Gesamttext" : `${script.beats.length} Abschnitte`}
            </p>
            {script.part1_selection ? (
              <p className="textMuted" style={{ fontSize: "0.9rem" }}>
                Finale Medien: {script.part1_selection.final_sounds.length} Sounds,{" "}
                {script.part1_selection.final_music.length} Musik, {script.part1_selection.final_videos.length}{" "}
                Videos, {script.part1_selection.final_lights.length} Licht
              </p>
            ) : null}
            {ready ? (
              <Link href={`/auffuehrung?id=${script.id}`} className="machineStartBtn" style={{ display: "inline-block", textAlign: "center", textDecoration: "none" }}>
                Zur Aufführung →
              </Link>
            ) : (
              <p className="textFaint">Zur Aufführung erst nach vollständiger Dramaturgie (status: ready).</p>
            )}
          </section>

          <section className="card col scriptDocument">
            {script.beats.map((beat) => {
              const teil1 = isPart1Beat(beat, script.beats);
              const baerenklau = isBaerenklauBeat(beat);
              return (
              <div
                key={beat.id}
                style={
                  teil1
                    ? { outline: "2px solid var(--accent, #6b8cff)", borderRadius: 8, padding: 4 }
                    : { opacity: 0.72 }
                }
              >
                {!teil1 ? (
                  <p className="textMuted" style={{ fontSize: "0.85rem", margin: "0 0 0.5rem" }}>
                    Teil 2 / später
                  </p>
                ) : (
                  <p className="textMuted" style={{ fontSize: "0.85rem", margin: "0 0 0.5rem" }}>
                    {baerenklau ? "Teil 1 — Bärenklau" : "Teil 1 — Workshop"}
                  </p>
                )}
                <ScriptBeatBlock
                  beat={beat}
                  editable
                  media={media}
                  onSpeakerChange={(speaker) => void handleSpeakerChange(beat.id, speaker)}
                />
              </div>
            );
            })}
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
