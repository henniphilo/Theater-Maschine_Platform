"use client";

import type { Route } from "next";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  assetContentUrl,
  attachAssetTag,
  deleteAsset,
  detachAssetTag,
  fetchAsset,
  fetchAssetPreview,
  updateAsset
} from "@/lib/api/assets";
import { listTags } from "@/lib/api/tags";
import { fetchProduction } from "@/lib/api/productions";
import type { Asset, AssetPreview, AssetType } from "@/lib/types/asset";
import { ASSET_TYPES } from "@/lib/types/asset";
import type { Production } from "@/lib/types/production";
import type { Tag } from "@/lib/types/tag";

export default function AssetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productionId = typeof params.id === "string" ? params.id : "";
  const assetId = typeof params.assetId === "string" ? params.assetId : "";

  const [production, setProduction] = useState<Production | null>(null);
  const [asset, setAsset] = useState<Asset | null>(null);
  const [preview, setPreview] = useState<AssetPreview | null>(null);
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState<AssetType>("other");
  const [newTagName, setNewTagName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tagBusy, setTagBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!productionId || !assetId) return;
    setError(null);
    try {
      const [prod, row, previewRow, tags] = await Promise.all([
        fetchProduction(productionId),
        fetchAsset(assetId, productionId),
        fetchAssetPreview(assetId, productionId).catch(() => null),
        listTags(productionId)
      ]);
      setProduction(prod);
      setAsset(row);
      setPreview(previewRow);
      setAvailableTags(tags);
      setName(row.name);
      setDescription(row.description ?? "");
      setType(row.type);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
      setAsset(null);
      setProduction(null);
      setPreview(null);
      setAvailableTags([]);
    } finally {
      setLoading(false);
    }
  }, [productionId, assetId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!asset || saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateAsset(asset.id, {
        name: name.trim(),
        type,
        description: description.trim() || null
      });
      setAsset(updated);
      setName(updated.name);
      setDescription(updated.description ?? "");
      setType(updated.type);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete() {
    if (!asset) return;
    if (
      !window.confirm(
        `Asset „${asset.name}“ und die gespeicherte Datei wirklich löschen?`
      )
    ) {
      return;
    }
    setError(null);
    try {
      await deleteAsset(asset.id, productionId);
      router.push(`/productions/${productionId}/library` as Route);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen");
    }
  }

  async function onAddTagByName(event: FormEvent) {
    event.preventDefault();
    if (!asset || tagBusy || !newTagName.trim()) return;
    setTagBusy(true);
    setError(null);
    try {
      const updated = await attachAssetTag(
        asset.id,
        { name: newTagName.trim() },
        productionId
      );
      setAsset(updated);
      setNewTagName("");
      setAvailableTags(await listTags(productionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tag hinzufügen fehlgeschlagen");
    } finally {
      setTagBusy(false);
    }
  }

  async function onAttachExistingTag(tagId: string) {
    if (!asset || tagBusy) return;
    setTagBusy(true);
    setError(null);
    try {
      const updated = await attachAssetTag(asset.id, { tagId }, productionId);
      setAsset(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tag hinzufügen fehlgeschlagen");
    } finally {
      setTagBusy(false);
    }
  }

  async function onDetachTag(tagId: string) {
    if (!asset || tagBusy) return;
    setTagBusy(true);
    setError(null);
    try {
      const updated = await detachAssetTag(asset.id, tagId, productionId);
      setAsset(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tag entfernen fehlgeschlagen");
    } finally {
      setTagBusy(false);
    }
  }

  if (loading) {
    return (
      <main className="container col">
        <p className="textMuted">Laden…</p>
      </main>
    );
  }

  if (!asset || !production) {
    return (
      <main className="container col">
        <p className="textError">{error ?? "Asset nicht gefunden"}</p>
        <Link href={`/productions/${productionId}/library` as Route}>Zurück zur Bibliothek</Link>
      </main>
    );
  }

  const contentUrl = assetContentUrl(asset.id, productionId);
  const attachedIds = new Set((asset.tags ?? []).map((t) => t.id));
  const unattachedTags = availableTags.filter((t) => !attachedIds.has(t.id));

  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>{asset.name}</h1>
      </div>
      <p>
        <Link href={`/productions/${production.id}/library` as Route}>
          ← Bibliothek · {production.name}
        </Link>
      </p>

      {error ? <p className="textError">{error}</p> : null}

      {preview?.preview_available ? (
        <section className="col" style={{ gap: "var(--space-2)" }}>
          <h2>Vorschau</h2>
          {preview.kind === "image" ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={contentUrl}
              alt={asset.name}
              style={{ maxWidth: "100%", maxHeight: 360, objectFit: "contain" }}
            />
          ) : null}
          {preview.kind === "audio" ? <audio controls src={contentUrl} /> : null}
          {preview.kind === "video" ? (
            <video controls src={contentUrl} style={{ maxWidth: "100%", maxHeight: 360 }} />
          ) : null}
          {(preview.kind === "text" || preview.kind === "json") && preview.text_excerpt ? (
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{preview.text_excerpt}</pre>
          ) : null}
        </section>
      ) : null}

      <p>
        <a href={contentUrl} download={asset.original_filename}>
          Datei herunterladen
        </a>
      </p>

      <section className="col" style={{ gap: "var(--space-3)", maxWidth: 520 }}>
        <h2>Tags</h2>
        {(asset.tags ?? []).length === 0 ? (
          <p className="textMuted" style={{ margin: 0 }}>
            Keine Tags.
          </p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
            {(asset.tags ?? []).map((tag) => (
              <li
                key={tag.id}
                style={{
                  display: "inline-flex",
                  gap: 8,
                  alignItems: "center",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-md)",
                  padding: "4px 8px"
                }}
              >
                <span>{tag.name}</span>
                <button type="button" disabled={tagBusy} onClick={() => void onDetachTag(tag.id)}>
                  Entfernen
                </button>
              </li>
            ))}
          </ul>
        )}
        <form
          className="col"
          style={{ gap: "var(--space-2)" }}
          onSubmit={(e) => void onAddTagByName(e)}
        >
          <label className="col" style={{ gap: 4 }}>
            <span>Neuen Tag anlegen und zuordnen</span>
            <input
              value={newTagName}
              onChange={(e) => setNewTagName(e.target.value)}
              placeholder="z. B. intro"
              maxLength={100}
            />
          </label>
          <button type="submit" disabled={tagBusy || !newTagName.trim()}>
            Tag hinzufügen
          </button>
        </form>
        {unattachedTags.length > 0 ? (
          <label className="col" style={{ gap: 4 }}>
            <span>Vorhandenen Tag zuordnen</span>
            <select
              defaultValue=""
              disabled={tagBusy}
              onChange={(e) => {
                const value = e.target.value;
                e.target.value = "";
                if (value) void onAttachExistingTag(value);
              }}
            >
              <option value="">Tag wählen…</option>
              {unattachedTags.map((tag) => (
                <option key={tag.id} value={tag.id}>
                  {tag.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </section>

      <dl className="col" style={{ gap: "var(--space-2)" }}>
        <div>
          <dt className="textMuted">Originaldatei</dt>
          <dd>{asset.original_filename}</dd>
        </div>
        <div>
          <dt className="textMuted">Storage-Key</dt>
          <dd>
            <code>{asset.storage_key}</code>
          </dd>
        </div>
        <div>
          <dt className="textMuted">MIME</dt>
          <dd>{asset.mime_type}</dd>
        </div>
        <div>
          <dt className="textMuted">Größe</dt>
          <dd>{asset.size_bytes} Bytes</dd>
        </div>
        <div>
          <dt className="textMuted">Checksum</dt>
          <dd>
            <code>{asset.checksum}</code>
          </dd>
        </div>
        <div>
          <dt className="textMuted">Metadata (JSON)</dt>
          <dd>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
              {JSON.stringify(asset.metadata ?? {}, null, 2)}
            </pre>
          </dd>
        </div>
        <div>
          <dt className="textMuted">ID</dt>
          <dd>
            <code>{asset.id}</code>
          </dd>
        </div>
      </dl>

      <section className="col" style={{ gap: "var(--space-3)", maxWidth: 520 }}>
        <h2>Metadaten bearbeiten</h2>
        <form className="col" style={{ gap: "var(--space-3)" }} onSubmit={onSave}>
          <label className="col" style={{ gap: 4 }}>
            <span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Typ</span>
            <select value={type} onChange={(e) => setType(e.target.value as AssetType)}>
              {ASSET_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span>Beschreibung</span>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
          </label>
          <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
            <button type="submit" disabled={saving || !name.trim()}>
              {saving ? "Speichern…" : "Speichern"}
            </button>
            <button type="button" onClick={() => void onDelete()}>
              Datei löschen
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
