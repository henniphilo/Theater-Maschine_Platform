"use client";

import type { Route } from "next";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { deleteRule, fetchRule, updateRule } from "@/lib/api/rules";
import { fetchProduction } from "@/lib/api/productions";
import type { Production } from "@/lib/types/production";
import type {
  Rule,
  RuleAction,
  RuleActionType,
  RuleCondition,
  RuleConditionType
} from "@/lib/types/rule";
import {
  RULE_ACTION_LABELS,
  RULE_ACTION_TYPES,
  RULE_CONDITION_LABELS,
  RULE_CONDITION_TYPES,
  emptyAction,
  emptyCondition
} from "@/lib/types/rule";

export default function RuleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productionId = typeof params.id === "string" ? params.id : "";
  const ruleId = typeof params.ruleId === "string" ? params.ruleId : "";

  const [production, setProduction] = useState<Production | null>(null);
  const [rule, setRule] = useState<Rule | null>(null);
  const [name, setName] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [priority, setPriority] = useState(0);
  const [cooldown, setCooldown] = useState("");
  const [condition, setCondition] = useState<RuleCondition>(emptyCondition());
  const [action, setAction] = useState<RuleAction>(emptyAction());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    if (!productionId || !ruleId) return;
    setError(null);
    try {
      const [prod, row] = await Promise.all([
        fetchProduction(productionId),
        fetchRule(ruleId, productionId)
      ]);
      setProduction(prod);
      setRule(row);
      setName(row.name);
      setEnabled(row.enabled);
      setPriority(row.priority);
      setCooldown(row.cooldown_seconds != null ? String(row.cooldown_seconds) : "");
      setCondition(row.conditions[0] ?? emptyCondition());
      setAction(row.actions[0] ?? emptyAction());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
      setRule(null);
      setProduction(null);
    } finally {
      setLoading(false);
    }
  }, [productionId, ruleId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!rule || saving) return;
    setSaving(true);
    setError(null);
    try {
      const clearCooldown = cooldown.trim() === "";
      const updated = await updateRule(rule.id, {
        name: name.trim(),
        enabled,
        priority,
        conditions: [condition],
        actions: [action],
        cooldown_seconds: clearCooldown ? null : Number(cooldown),
        clear_cooldown_seconds: clearCooldown
      });
      setRule(updated);
      setName(updated.name);
      setEnabled(updated.enabled);
      setPriority(updated.priority);
      setCooldown(updated.cooldown_seconds != null ? String(updated.cooldown_seconds) : "");
      setCondition(updated.conditions[0] ?? emptyCondition());
      setAction(updated.actions[0] ?? emptyAction());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete() {
    if (!rule || !window.confirm(`Regel „${rule.name}“ löschen?`)) return;
    try {
      await deleteRule(rule.id, productionId);
      router.push(`/productions/${productionId}/rules` as Route);
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

  if (!production || !rule) {
    return (
      <main className="container col">
        <p className="textError">{error ?? "Regel nicht gefunden"}</p>
        <Link href={`/productions/${productionId}/rules` as Route}>Zurück</Link>
      </main>
    );
  }

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Regel bearbeiten</h1>
      </div>
      <p>
        <Link href={`/productions/${production.id}/rules` as Route}>← Regeln</Link>
        {" · "}
        <Link href={`/productions/${production.id}`}> {production.name}</Link>
      </p>

      {error ? <p className="textError">{error}</p> : null}

      <form
        className="col"
        style={{ gap: "var(--space-3)", maxWidth: 560 }}
        onSubmit={(e) => void onSave(e)}
      >
        <label className="col" style={{ gap: 4 }}>
          <span>Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          <span>Aktiv</span>
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
          <span>Cooldown (Sekunden, leer = keiner)</span>
          <input
            type="number"
            min={0}
            step={0.1}
            value={cooldown}
            onChange={(e) => setCooldown(e.target.value)}
          />
        </label>

        <fieldset className="col" style={{ gap: "var(--space-2)", border: "1px solid var(--color-border)", padding: "var(--space-3)" }}>
          <legend>Bedingung</legend>
          <label className="col" style={{ gap: 4 }}>
            <span>Typ</span>
            <select
              value={condition.type}
              onChange={(e) => setCondition(emptyCondition(e.target.value as RuleConditionType))}
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
                onChange={(e) => setCondition({ ...condition, term: e.target.value })}
                required
              />
            </label>
          ) : null}
          {condition.type === "tag" ? (
            <label className="col" style={{ gap: 4 }}>
              <span>Tag</span>
              <input
                value={condition.tag ?? ""}
                onChange={(e) => setCondition({ ...condition, tag: e.target.value })}
                required
              />
            </label>
          ) : null}
          {condition.type === "mood" ? (
            <label className="col" style={{ gap: 4 }}>
              <span>Stimmung</span>
              <input
                value={condition.mood ?? ""}
                onChange={(e) => setCondition({ ...condition, mood: e.target.value })}
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
                onChange={(e) => setCondition({ ...condition, value: Number(e.target.value) })}
                required
              />
            </label>
          ) : null}
          {condition.type === "previous_cue" ? (
            <label className="col" style={{ gap: 4 }}>
              <span>Cue-ID</span>
              <input
                value={condition.cue_id ?? ""}
                onChange={(e) => setCondition({ ...condition, cue_id: e.target.value })}
                required
              />
            </label>
          ) : null}
          {condition.type === "manual" ? (
            <label className="col" style={{ gap: 4 }}>
              <span>Aktivierungsschlüssel</span>
              <input
                value={condition.activation_key ?? ""}
                onChange={(e) =>
                  setCondition({ ...condition, activation_key: e.target.value })
                }
                required
              />
            </label>
          ) : null}
        </fieldset>

        <fieldset className="col" style={{ gap: "var(--space-2)", border: "1px solid var(--color-border)", padding: "var(--space-3)" }}>
          <legend>Aktion</legend>
          <label className="col" style={{ gap: 4 }}>
            <span>Typ</span>
            <select
              value={action.type}
              onChange={(e) => setAction(emptyAction(e.target.value as RuleActionType))}
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
                onChange={(e) => setAction({ ...action, cue_id: e.target.value })}
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
                onChange={(e) => setAction({ ...action, delay_seconds: Number(e.target.value) })}
                required
              />
            </label>
          ) : null}
          {action.type === "select_from_group" ? (
            <label className="col" style={{ gap: 4 }}>
              <span>Gruppe</span>
              <input
                value={action.group ?? ""}
                onChange={(e) => setAction({ ...action, group: e.target.value })}
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
                  setAction({
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
        </fieldset>

        <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
          <button type="submit" disabled={saving || !name.trim()}>
            {saving ? "Speichern…" : "Speichern"}
          </button>
          <button type="button" onClick={() => void onDelete()}>
            Löschen
          </button>
        </div>
      </form>
    </main>
  );
}
