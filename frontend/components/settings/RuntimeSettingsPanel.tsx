"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  fetchRuntimeSettings,
  patchRuntimeSettings,
  type RuntimeSettings
} from "@/lib/api/director";

type FieldKind = "bool" | "select" | "text" | "number";

type FieldDef = {
  key: string;
  label: string;
  info: string;
  kind: FieldKind;
  options?: { value: string; label: string }[];
};

const FIELDS: FieldDef[] = [
  {
    key: "director_dramaturgy_mode",
    label: "Dramaturgie-Modus",
    info:
      "Wie Stichwort-Cues (Licht/Sound) beim Vorbereiten entstehen. „Rules“ arbeitet lokal und schnell. „LLM“ schickt Textabschnitte parallel an OpenAI — genauer, aber deutlich langsamer und abhängig vom API-Key.",
    kind: "select",
    options: [
      { value: "rules", label: "Rules (schnell)" },
      { value: "llm", label: "LLM" }
    ]
  },
  {
    key: "osc_dry_run",
    label: "OSC Dry-Run",
    info:
      "Master-Schalter für Netzwerkausgaben: an = Befehle nur loggen, nichts an Pixera/Licht/OSC senden. Aus = Live-Signale an die konfigurierten Ziele. Probebetrieb am Aufführungs-Tab ist davon getrennt und softet nur Licht.",
    kind: "bool"
  },
  {
    key: "visual_output",
    label: "Video-Ausgabe",
    info:
      "Wohin Avatar- und Atmosphären-Clips gehen. Pixera = Bühne, TouchDesigner = Preview/Entwicklung, Beide = parallel. Host/Port der Ziele stellst du im Technik-Test ein.",
    kind: "select",
    options: [
      { value: "pixera", label: "Pixera" },
      { value: "touchdesigner", label: "TouchDesigner" },
      { value: "both", label: "Beide" }
    ]
  },
  {
    key: "light_output",
    label: "Licht-Ausgabe",
    info:
      "Lichtweg: EOS TCP ans Pult, OSC an den Licht-OSC-Port, Mirror = nur Preview/QLab-Log ohne Desk. Bei Wechsel wird eine offene TCP-Session geschlossen.",
    kind: "select",
    options: [
      { value: "tcp", label: "EOS TCP" },
      { value: "osc", label: "OSC" },
      { value: "mirror", label: "Mirror (QLab/Log)" }
    ]
  },
  {
    key: "sound_output",
    label: "Sound-Ausgabe",
    info:
      "Sound-Cues per MIDI (Ableton, nur native Mac), OSC oder beidem. MIDI funktioniert nicht im Docker-Stack.",
    kind: "select",
    options: [
      { value: "midi", label: "MIDI" },
      { value: "osc", label: "OSC" },
      { value: "both", label: "Beide" }
    ]
  },
  {
    key: "teil2_prepare_model",
    label: "Teil-2 Prepare-Modell",
    info:
      "OpenAI-Modell für Teil-2-Prepare (Dramaturgie-Chunks, optional Analyse/Atmosphäre). Kleinere Modelle sind günstiger und schneller, größere oft treffsicherer.",
    kind: "text"
  },
  {
    key: "teil2_dramaturgy_chunk_size",
    label: "Teil-2 Chunk-Größe",
    info:
      "Wie viele Sätze ein paralleler LLM-Aufruf beim Prepare bekommt (6–40). Kleinere Chunks = mehr API-Calls, feinere Stichworte. Größere = weniger Calls, grobere Abschnitte.",
    kind: "number"
  },
  {
    key: "teil2_atmosphere_use_llm",
    label: "Teil-2 Atmosphäre per LLM",
    info:
      "An = Begleit-/B-Roll-Clips auf freien Beamern plant ein LLM. Aus = regelbasierte Timeline (schneller, vorhersehbarer). Avatare bleiben davon unberührt.",
    kind: "bool"
  },
  {
    key: "teil2_use_analyse_llm",
    label: "Teil-2 Analyse per LLM",
    info:
      "An = kurzes Gesamtkonzept (These, Anarchie-Kurve) per OpenAI beim Prepare. Aus = festes Regel-Fallback — Prepare startet sofort in die Dramaturgie-Phase.",
    kind: "bool"
  },
  {
    key: "avatar_done_gate_enabled",
    label: "Avatar-Done-Gate",
    info:
      "Wartet nach Avatar-Start auf /avatar/done (QLab/Pixera), bevor der nächste Clip kommt. Verhindert Überlappungen, wenn die Timing-Quelle ungenau ist. Braucht laufenden Listener.",
    kind: "bool"
  },
  {
    key: "avatar_done_source",
    label: "Avatar-Done-Quelle",
    info:
      "Wer /avatar/done sendet: QLab (Test-Relay), Pixera (Bühne) oder manuell. Wirkt nur, wenn das Gate aktiv ist.",
    kind: "select",
    options: [
      { value: "qlab", label: "QLab" },
      { value: "pixera", label: "Pixera" },
      { value: "manual", label: "Manuell" }
    ]
  },
  {
    key: "director_execute_mode",
    label: "Execute-Modus",
    info:
      "Sequenced = Cues mit Abständen über die OSC-Queue (weniger Drop-Risiko). Immediate = sofort hintereinander — aggressiver, eher für Debug.",
    kind: "select",
    options: [
      { value: "sequenced", label: "Sequenced" },
      { value: "immediate", label: "Immediate" }
    ]
  },
  {
    key: "light_osc_mirror",
    label: "Licht → OSC-Mirror",
    info:
      "Zusätzlich zum gewählten Lichtweg dieselben Szenen als Preview-OSC (/light/…) spiegeln — nützlich parallel zum Desk.",
    kind: "bool"
  },
  {
    key: "sound_osc_mirror",
    label: "Sound → OSC-Mirror",
    info:
      "Bei MIDI-Ausgabe Sound-Cues zusätzlich als OSC mitschicken (z. B. für Logging oder eine zweite Maschine).",
    kind: "bool"
  },
  {
    key: "part1_workshop_preview_hardware",
    label: "Teil-1 Workshop Hardware-Preview",
    info:
      "Im Dramaturgie-Workshop Cues schon an echte Hardware schicken statt nur zu planen. Fürs Schreiben am Tisch besser aus.",
    kind: "bool"
  },
  {
    key: "signal_trace_enabled",
    label: "Signal-Trace",
    info:
      "Schreibt detaillierte Cue-/OSC-Ereignisse nach logs/signal_trace.jsonl für Signal-Drop-Analyse und Timeline-Visualisierung.",
    kind: "bool"
  }
];

function SettingInfoTip({ text, label }: { text: string; label: string }) {
  return (
    <span className="settingInfoTip">
      <button
        type="button"
        className="settingInfoTipTrigger"
        aria-label={`Info: ${label}`}
      >
        i
      </button>
      <span className="settingInfoTipBubble" role="tooltip">
        {text}
      </span>
    </span>
  );
}

type Props = {
  /** Compact: only dramaturgy + Teil-2 prepare knobs */
  compact?: boolean;
};

export function RuntimeSettingsPanel({ compact = false }: Props) {
  const [data, setData] = useState<RuntimeSettings | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const fields = compact
    ? FIELDS.filter((f) =>
        [
          "director_dramaturgy_mode",
          "teil2_prepare_model",
          "teil2_atmosphere_use_llm",
          "teil2_use_analyse_llm",
          "teil2_dramaturgy_chunk_size"
        ].includes(f.key)
      )
    : FIELDS;

  const refresh = useCallback(() => {
    fetchRuntimeSettings()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Settings laden fehlgeschlagen"));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function setValue(key: string, value: unknown) {
    setSaving(true);
    setError("");
    try {
      const next = await patchRuntimeSettings({ values: { [key]: value } });
      setData(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  async function clearKey(key: string) {
    setSaving(true);
    setError("");
    try {
      const next = await patchRuntimeSettings({ clear_keys: [key] });
      setData(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Zurücksetzen fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  async function resetAll() {
    setSaving(true);
    setError("");
    try {
      const next = await patchRuntimeSettings({ reset: true });
      setData(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  if (!data) {
    return (
      <section className="card col">
        <h2>Betriebs-Einstellungen</h2>
        <p className="textMuted">{error || "Laden …"}</p>
      </section>
    );
  }

  return (
    <section className="card col runtimeSettings">
      <div className="pageHeader" style={{ marginBottom: 0 }}>
        <h2>{compact ? "Prepare-Einstellungen" : "Betriebs-Einstellungen"}</h2>
      </div>
      <p className="textMuted">
        Überschreibt .env-Werte zur Laufzeit (gespeichert in data/runtime_settings.json). Secrets bleiben nur in
        .env. Infos: Hover auf das i neben dem Namen.
        {compact ? (
          <>
            {" "}
            Alle Optionen: <Link href="/einstellungen">Einstellungen →</Link>
          </>
        ) : null}
      </p>
      {error ? (
        <p className="textError" role="alert">
          {error}
        </p>
      ) : null}
      <div className="col" style={{ gap: "0.75rem" }}>
        {fields.map((field) => {
          const effective = data.effective[field.key];
          const isOverridden = field.key in data.overrides;
          const defaultVal = data.defaults[field.key];
          return (
            <div key={field.key} className="runtimeSettingsRow">
              <div className="runtimeSettingsLabel">
                <div className="runtimeSettingsLabelRow">
                  <label htmlFor={`rs-${field.key}`}>{field.label}</label>
                  <SettingInfoTip text={field.info} label={field.label} />
                </div>
                {isOverridden ? (
                  <span className="textMuted">
                    Override · .env-Default: {String(defaultVal)}
                  </span>
                ) : null}
              </div>
              <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                {field.kind === "bool" ? (
                  <input
                    id={`rs-${field.key}`}
                    type="checkbox"
                    checked={Boolean(effective)}
                    disabled={saving}
                    onChange={(e) => void setValue(field.key, e.target.checked)}
                  />
                ) : null}
                {field.kind === "select" ? (
                  <select
                    id={`rs-${field.key}`}
                    value={String(effective ?? "")}
                    disabled={saving}
                    onChange={(e) => void setValue(field.key, e.target.value)}
                  >
                    {(field.options ?? []).map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                ) : null}
                {field.kind === "text" ? (
                  <input
                    id={`rs-${field.key}`}
                    type="text"
                    value={String(effective ?? "")}
                    disabled={saving}
                    onBlur={(e) => {
                      if (e.target.value !== String(effective ?? "")) {
                        void setValue(field.key, e.target.value);
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const target = e.target as HTMLInputElement;
                        void setValue(field.key, target.value);
                      }
                    }}
                  />
                ) : null}
                {field.kind === "number" ? (
                  <input
                    id={`rs-${field.key}`}
                    type="number"
                    min={6}
                    max={40}
                    value={Number(effective ?? 12)}
                    disabled={saving}
                    onChange={(e) => void setValue(field.key, Number(e.target.value))}
                  />
                ) : null}
                {isOverridden ? (
                  <button type="button" disabled={saving} onClick={() => void clearKey(field.key)}>
                    .env
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
      {!compact ? (
        <button type="button" disabled={saving} onClick={() => void resetAll()}>
          Alle Overrides zurücksetzen
        </button>
      ) : null}
    </section>
  );
}
