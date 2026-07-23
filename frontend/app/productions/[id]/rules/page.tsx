"use client";

import type { Route } from "next";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { createRule, deleteRule, evaluateRules, listLegacyRules, listRules } from "@/lib/api/rules";
import { fetchProduction } from "@/lib/api/productions";
import type { Production } from "@/lib/types/production";
import type {
  LegacyRuleSummary,
  Rule,
  RuleAction,
  RuleCondition,
  RuleConditionType,
  RuleActionType
} from "@/lib/types/rule";
import {
  RULE_ACTION_LABELS,
  RULE_ACTION_TYPES,
  RULE_CONDITION_LABELS,
  RULE_CONDITION_TYPES,
  emptyAction,
  emptyCondition,
  summarizeAction,
  summarizeCondition
} from "@/lib/types/rule";

function ConditionFields({
  condition,
  onChange
}: {
  condition: RuleCondition;
  onChange: (next: RuleCondition) => void;
}) {
  return (
    <div className="col" style={{ gap: "var(--space-2)" }}>
      <label className="col" style={{ gap: 4 }}>
        <span>Bedingung</span>
        <select
          value={condition.type}
          onChange={(e) => onChange(emptyCondition(e.target.value as RuleConditionType))}
        >
          {RULE_CONDITION_TYPES.map((t) => (
            <option key={t} value={t}>
              {RULE_CONDITION_LABELS[t]}
            </option>
          ))}
        </select>
      </label>
      {condition.type === "text_contains" ? (
        <label className="col" style={{ gap: 4 }}>
          <span>Begriff</span>
          <input
            value={condition.term ?? ""}
            onChange={(e) => onChange({ ...condition, term: e.target.value })}
            required
          />
        </label>
      ) : null}
      {condition.type === "tag" ? (
        <label className="col" style={{ gap: 4 }}>
          <span>Tag</span>
          <input
            value={condition.tag ?? ""}
            onChange={(e) => onChange({ ...condition, tag: e.target.value })}
            required
          />
        </label>
      ) : null}
      {condition.type === "mood" ? (
        <label className="col" style={{ gap: 4 }}>
          <span>Stimmung</span>
          <input
            value={condition.mood ?? ""}
            onChange={(e) => onChange({ ...condition, mood: e.target.value })}
            required
          />
        </label>
      ) : null}
      {condition.type === "intensity_min" || condition.type === "intensity_max" ? (
        <label className="col" style={{ gap: 4 }}>
          <span>Wert (0–1)</span>
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={condition.value ?? 0}
            onChange={(e) => onChange({ ...condition, value: Number(e.target.value) })}
            required
          />
        </label>
      ) : null}
      {condition.type === "previous_cue" ? (
        <label className="col" style={{ gap: 4 }}>
          <span>Cue-ID</span>
          <input
            value={condition.cue_id ?? ""}
            onChange={(e) => onChange({ ...condition, cue_id: e.target.value })}
            required
          />
        </label>
      ) : null}
      {condition.type === "manual" ? (
        <label className="col" style={{ gap: 4 }}>
          <span>Aktivierungsschlüssel</span>
          <input
            value={condition.activation_key ?? ""}
            onChange={(e) => onChange({ ...condition, activation_key: e.target.value })}
            required
          />
        </label>
      ) : null}
    </div>
  );
}

function ActionFields({
  action,
  onChange
}: {
  action: RuleAction;
  onChange: (next: RuleAction) => void;
}) {
  return (
    <div className="col" style={{ gap: "var(--space-2)" }}>
      <label className="col" style={{ gap: 4 }}>
        <span>Aktion</span>
        <select
          value={action.type}
          onChange={(e) => onChange(emptyAction(e.target.value as RuleActionType))}
        >
          {RULE_ACTION_TYPES.map((t) => (
            <option key={t} value={t}>
              {RULE_ACTION_LABELS[t]}
            </option>
          ))}
        </select>
      </label>
      {action.type === "execute_cue" || action.type === "execute_delayed" ? (
        <label className="col" style={{ gap: 4 }}>
          <span>Cue-ID</span>
          <input
            value={action.cue_id ?? ""}
            onChange={(e) => onChange({ ...action, cue_id: e.target.value })}
            required
          />
        </label>
      ) : null}
      {action.type === "execute_delayed" ? (
        <label className="col" style={{ gap: 4 }}>
          <span>Verzögerung (Sekunden)</span>
          <input
            type="number"
            min={0}
            step={0.1}
            value={action.delay_seconds ?? 0}
            onChange={(e) => onChange({ ...action, delay_seconds: Number(e.target.value) })}
            required
          />
        </label>
      ) : null}
      {action.type === "select_from_group" ? (
        <label className="col" style={{ gap: 4 }}>
          <span>Gruppe</span>
          <input
            value={action.group ?? ""}
            onChange={(e) => onChange({ ...action, group: e.target.value })}
            required
          />
        </label>
      ) : null}
      {action.type === "select_random_by_tags" ? (
        <label className="col" style={{ gap: 4 }}>
          <span>Tags (kommagetrennt)</span>
          <input
            value={(action.tags ?? []).join(", ")}
            onChange={(e) =>
              onChange({
                ...action,
                tags: e.target.value
                  .split(",")
                  .map((t) => t.trim())
                  .filter(Boolean)
              })
            }
            required
          />
        </label>
      ) : null}
    </div>
  );
}

export default function ProductionRulesPage() {
  const params = useParams();
  const productionId = typeof params.id === "string" ? params.id : "";

  const [production, setProduction] = useState<Production | null>(null);
  const [rules, setRules] = useState<Rule[]>([]);
  const [legacy, setLegacy] = useState<LegacyRuleSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [evalResult, setEvalResult] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [priority, setPriority] = useState(0);
  const [cooldown, setCooldown] = useState("");
  const [condition, setCondition] = useState<RuleCondition>(emptyCondition("text_contains"));
  const [action, setAction] = useState<RuleAction>(emptyAction("execute_cue"));
  const [creating, setCreating] = useState(false);

  const [evalText, setEvalText] = useState("");
  const [evalTags, setEvalTags] = useState("");
  const [evalMood, setEvalMood] = useState("");
  const [evalIntensity, setEvalIntensity] = useState("0.5");

  const refresh = useCallback(async () => {
    if (!productionId) return;
    setError(null);
    try {
      const [prod, rows, legacyRows] = await Promise.all([
        fetchProduction(productionId),
        listRules({ productionId }),
        listLegacyRules()
      ]);
      setProduction(prod);
      setRules(rows);
      setLegacy(legacyRows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
      setProduction(null);
      setRules([]);
    } finally {
      setLoading(false);
    }
  }, [productionId]);

  useEffect(() => {
    setLoading(true);
    void refresh();
  }, [refresh]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!productionId || creating || !name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const cooldownValue = cooldown.trim() === "" ? null : Number(cooldown);
      await createRule({
        production_id: productionId,
        name: name.trim(),
        priority,
        cooldown_seconds: cooldownValue,
        conditions: [condition],
        actions: [action]
      });
      setName("");
      setPriority(0);
      setCooldown("");
      setCondition(emptyCondition("text_contains"));
      setAction(emptyAction("execute_cue"));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anlegen fehlgeschlagen");
    } finally {
      setCreating(false);
    }
  }

  async function onEvaluate() {
    if (!productionId) return;
    setError(null);
    setEvalResult(null);
    try {
      const result = await evaluateRules(productionId, {
        text: evalText,
        tags: evalTags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        mood: evalMood.trim() || null,
        intensity: Number(evalIntensity) || 0,
        now_seconds: 0,
        include_legacy_json: false
      });
      setEvalResult(JSON.stringify(result, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Auswertung fehlgeschlagen");
    }
  }

  async function onDelete(rule: Rule) {
    if (!window.confirm(`Regel „${rule.name}“ löschen?`)) return;
    setError(null);
    try {
      await deleteRule(rule.id, productionId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen");
    }
  }

  if (loading) {
    return (
      <main className="container col">
        <p className="textMuted">Laden…</p>
      </main>
    );
  }

  if (!production) {
    return (
      <main className="container col">
        <p className="textError">{error ?? "Produktion nicht gefunden"}</p>
        <Link href="/productions">Zurück zur Liste</Link>
      </main>
    );
  }

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Regeln</h1>
      </div>
      <p>
        <Link href={`/productions/${production.id}`}>← {production.name}</Link>
      </p>
      <p className="textMuted">
        Produktionsbezogene Dramaturgie-Regeln. Die bestehende DramaturgyEngine bleibt unverändert —
        Auswertung hier über die gemeinsame Regelrepräsentation.
      </p>

      {error ? <p className="textError">{error}</p> : null}

      <section className="col" style={{ gap: "var(--space-3)", maxWidth: 560 }}>
        <h2>Neue Regel anlegen</h2>
        <form className="col" style={{ gap: "var(--space-3)" }} onSubmit={(e) => void onCreate(e)}>
          <label className="col" style={{ gap: 4 }}>
            <span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Priorität</span>
            <input
              type="number"
              value={priority}
              onChange={(e) => setPriority(Number(e.target.value))}
            />
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Cooldown (Sekunden, optional)</span>
            <input
              type="number"
              min={0}
              step={0.1}
              value={cooldown}
              onChange={(e) => setCooldown(e.target.value)}
              placeholder="leer = keiner"
            />
          </label>
          <ConditionFields condition={condition} onChange={setCondition} />
          <ActionFields action={action} onChange={setAction} />
          <button type="submit" disabled={creating || !name.trim()}>
            {creating ? "Anlegen…" : "Regel anlegen"}
          </button>
        </form>
      </section>

      <section className="col" style={{ gap: "var(--space-3)" }}>
        <h2>Regelliste</h2>
        {rules.length === 0 ? (
          <p className="textMuted">Noch keine DB-Regeln.</p>
        ) : (
          <ul className="col" style={{ gap: "var(--space-2)", listStyle: "none", padding: 0 }}>
            {rules.map((rule) => (
              <li
                key={rule.id}
                style={{
                  border: "1px solid var(--color-border)",
                  padding: "var(--space-3)",
                  borderRadius: "var(--radius-md)",
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "var(--space-3)",
                  alignItems: "center",
                  justifyContent: "space-between"
                }}
              >
                <div className="col" style={{ gap: 2 }}>
                  <strong>{rule.name}</strong>
                  <span className="textMuted">
                    Prio {rule.priority}
                    {rule.enabled ? "" : " · deaktiviert"}
                    {rule.cooldown_seconds != null ? ` · CD ${rule.cooldown_seconds}s` : ""}
                  </span>
                  <span className="textMuted">
                    Wenn: {rule.conditions.map(summarizeCondition).join(" UND ")}
                  </span>
                  <span className="textMuted">
                    Dann: {rule.actions.map(summarizeAction).join(", ")}
                  </span>
                </div>
                <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                  <Link href={`/productions/${production.id}/rules/${rule.id}` as Route}>
                    Bearbeiten
                  </Link>
                  <button type="button" onClick={() => void onDelete(rule)}>
                    Löschen
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="col" style={{ gap: "var(--space-3)", maxWidth: 560 }}>
        <h2>Auswertung testen</h2>
        <label className="col" style={{ gap: 4 }}>
          <span>Text</span>
          <input value={evalText} onChange={(e) => setEvalText(e.target.value)} />
        </label>
        <label className="col" style={{ gap: 4 }}>
          <span>Tags (kommagetrennt)</span>
          <input value={evalTags} onChange={(e) => setEvalTags(e.target.value)} />
        </label>
        <label className="col" style={{ gap: 4 }}>
          <span>Stimmung</span>
          <input value={evalMood} onChange={(e) => setEvalMood(e.target.value)} />
        </label>
        <label className="col" style={{ gap: 4 }}>
          <span>Intensität</span>
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={evalIntensity}
            onChange={(e) => setEvalIntensity(e.target.value)}
          />
        </label>
        <button type="button" onClick={() => void onEvaluate()}>
          Regeln auswerten
        </button>
        {evalResult ? (
          <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{evalResult}</pre>
        ) : null}
      </section>

      <section className="col" style={{ gap: "var(--space-3)" }}>
        <h2>Legacy JSON (nur Anzeige)</h2>
        <p className="textMuted">
          Aus dramaturgy_rules.json in die gemeinsame Repräsentation übersetzt (
          {legacy.length} Regeln). DramaturgyEngine nutzt weiterhin die JSON-Datei direkt.
        </p>
        {legacy.length === 0 ? (
          <p className="textMuted">Keine Legacy-Regeln geladen.</p>
        ) : (
          <ul className="col" style={{ gap: "var(--space-2)", listStyle: "none", padding: 0 }}>
            {legacy.slice(0, 12).map((rule) => (
              <li key={rule.id} className="textMuted">
                <strong>{rule.name}</strong> · Prio {rule.priority}
                {rule.cooldown_seconds != null ? ` · CD ${rule.cooldown_seconds}s` : ""}
              </li>
            ))}
            {legacy.length > 12 ? (
              <li className="textMuted">… und {legacy.length - 12} weitere</li>
            ) : null}
          </ul>
        )}
      </section>
    </main>
  );
}
