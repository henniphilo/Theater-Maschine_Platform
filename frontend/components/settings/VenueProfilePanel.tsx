"use client";

import { useCallback, useEffect, useState } from "react";

import {
  activateVenueProfile,
  fetchVenueProfiles,
  type VenueProfile,
  type VenueProfiles
} from "@/lib/api/director";

type Props = {
  onActivated?: () => void;
};

export function VenueProfilePanel({ onActivated }: Props) {
  const [data, setData] = useState<VenueProfiles | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    const profiles = await fetchVenueProfiles();
    setData(profiles);
  }, []);

  useEffect(() => {
    void refresh().catch((err) => {
      setError(err instanceof Error ? err.message : "Venue-Profile nicht ladbar");
    });
  }, [refresh]);

  const activate = useCallback(
    async (profileId: string) => {
      setError("");
      setLoading(true);
      try {
        const profiles = await activateVenueProfile(profileId);
        setData(profiles);
        onActivated?.();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Umschalten fehlgeschlagen");
      } finally {
        setLoading(false);
      }
    },
    [onActivated]
  );

  const active: VenueProfile | null =
    data?.profiles.find((p) => p.id === data.active_id) ?? null;

  return (
    <section className="panel col" style={{ gap: "0.75rem" }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
        <h2 style={{ margin: 0 }}>Bühne / Venue</h2>
        {active ? (
          <span className="textMuted" style={{ fontSize: "0.9rem" }}>
            Aktiv: <strong>{active.label}</strong>
          </span>
        ) : null}
      </div>
      <p className="textMuted" style={{ margin: 0 }}>
        Speichert Pixera- und Licht-Ziele pro Spielstätte. Umschalten setzt die Netzwerkziele sofort.
      </p>
      <div className="row" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
        {(data?.profiles ?? []).map((profile) => {
          const isActive = profile.id === data?.active_id;
          return (
            <button
              key={profile.id}
              type="button"
              className={isActive ? "primary" : undefined}
              disabled={loading || isActive}
              onClick={() => void activate(profile.id)}
            >
              {profile.label}
            </button>
          );
        })}
      </div>
      {active ? (
        <div className="textMuted" style={{ fontSize: "0.9rem", lineHeight: 1.45 }}>
          <div>
            Video:{" "}
            <code>
              {active.video_hosts.join(", ")}:{active.video_port}
            </code>
            {active.video_hosts.length > 1 ? " (Fan-out an alle)" : null}
          </div>
          <div>
            Licht:{" "}
            {active.light_configured ? (
              <code>
                {active.light_host}:{active.light_port}
              </code>
            ) : (
              <em>noch nicht gesetzt</em>
            )}
          </div>
          {active.self_host ? (
            <div>
              Show-Mac (erwartet): <code>{active.self_host}</code>
            </div>
          ) : null}
          {active.notes ? <div>{active.notes}</div> : null}
        </div>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  );
}
