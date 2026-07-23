"use client";

import type { Route } from "next";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { deleteAsset, listAssets, uploadAsset } from "@/lib/api/assets";
import { listTags } from "@/lib/api/tags";
import { fetchProduction } from "@/lib/api/productions";
import type { Asset, AssetType } from "@/lib/types/asset";
import { ASSET_TYPES } from "@/lib/types/asset";
import type { Production } from "@/lib/types/production";
import type { Tag } from "@/lib/types/tag";

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ProductionLibraryPage() {
  const params = useParams();
  const productionId = typeof params.id === "string" ? params.id : "";
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [production, setProduction] = useState<Production | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [typeFilter, setTypeFilter] = useState<AssetType | "">("");
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadLabel, setUploadLabel] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!productionId) return;
    setError(null);
    try {
      const [prod, rows, tags] = await Promise.all([
        fetchProduction(productionId),
        listAssets({
          productionId,
          type: typeFilter || undefined,
          tagIds: selectedTagIds.length > 0 ? selectedTagIds : undefined
        }),
        listTags(productionId)
      ]);
      setProduction(prod);
      setAssets(rows);
      setAvailableTags(tags);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
      setProduction(null);
      setAssets([]);
      setAvailableTags([]);
    } finally {
      setLoading(false);
    }
  }, [productionId, typeFilter, selectedTagIds]);

  useEffect(() => {
    setLoading(true);
    void refresh();
  }, [refresh]);

  async function handleFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    if (!productionId || files.length === 0 || uploading) return;

    setUploading(true);
    setError(null);
    try {
      for (const file of files) {
        setUploadLabel(file.name);
        setUploadProgress(0);
        await uploadAsset({
          productionId,
          file,
          onProgress: setUploadProgress
        });
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload fehlgeschlagen");
    } finally {
      setUploading(false);
      setUploadLabel(null);
      setUploadProgress(0);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function onDeleteAsset(asset: Asset) {
    if (
      !window.confirm(
        `Asset „${asset.name}“ und die zugehörige Datei wirklich löschen?`
      )
    ) {
      return;
    }
    setError(null);
    try {
      await deleteAsset(asset.id, productionId);
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
        <h1>Bibliothek</h1>
      </div>
      <p>
        <Link href={`/productions/${production.id}`}>← {production.name}</Link>
      </p>
      <p className="textMuted">
        Dateien hochladen und als Assets dieser Produktion verwalten.
      </p>

      {error ? <p className="textError">{error}</p> : null}

      <section
        className="col"
        style={{
          gap: "var(--space-3)",
          border: `2px dashed ${dragOver ? "var(--color-accent, #888)" : "var(--color-border)"}`,
          borderRadius: "var(--radius-md)",
          padding: "var(--space-4)",
          background: dragOver ? "rgba(127,127,127,0.08)" : "transparent"
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragOver(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          void handleFiles(e.dataTransfer.files);
        }}
      >
        <h2>Upload</h2>
        <p className="textMuted" style={{ margin: 0 }}>
          Dateien hierher ziehen oder über den Dialog auswählen.
        </p>
        <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", alignItems: "center" }}>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            disabled={uploading}
            onChange={(e) => {
              if (e.target.files) void handleFiles(e.target.files);
            }}
          />
          <button type="button" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
            Datei wählen
          </button>
        </div>
        {uploading ? (
          <div className="col" style={{ gap: 4 }}>
            <span className="textMuted">
              Lade {uploadLabel ?? "Datei"}… {Math.round(uploadProgress * 100)}%
            </span>
            <div
              role="progressbar"
              aria-valuenow={Math.round(uploadProgress * 100)}
              aria-valuemin={0}
              aria-valuemax={100}
              style={{
                height: 8,
                background: "var(--color-border)",
                borderRadius: 4,
                overflow: "hidden"
              }}
            >
              <div
                style={{
                  width: `${Math.round(uploadProgress * 100)}%`,
                  height: "100%",
                  background: "var(--color-fg, currentColor)"
                }}
              />
            </div>
          </div>
        ) : null}
      </section>

      <div
        style={{
          display: "flex",
          gap: "var(--space-3)",
          flexWrap: "wrap",
          alignItems: "flex-start"
        }}
      >
        <label className="col" style={{ gap: 4, maxWidth: 280 }}>
          <span>Typfilter</span>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter((e.target.value || "") as AssetType | "")}
          >
            <option value="">Alle Typen</option>
            {ASSET_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>

        <fieldset className="col" style={{ gap: 4, border: "none", padding: 0, margin: 0 }}>
          <legend>Tagfilter (UND)</legend>
          {availableTags.length === 0 ? (
            <p className="textMuted" style={{ margin: 0 }}>
              Noch keine Tags in dieser Produktion.
            </p>
          ) : (
            <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
              {availableTags.map((tag) => {
                const checked = selectedTagIds.includes(tag.id);
                return (
                  <label
                    key={tag.id}
                    style={{ display: "inline-flex", gap: 6, alignItems: "center" }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        setSelectedTagIds((prev) =>
                          checked ? prev.filter((id) => id !== tag.id) : [...prev, tag.id]
                        );
                      }}
                    />
                    <span>{tag.name}</span>
                  </label>
                );
              })}
            </div>
          )}
        </fieldset>
      </div>

      <section className="col" style={{ gap: "var(--space-3)" }}>
        <h2>Assets</h2>
        {assets.length === 0 ? (
          <p className="textMuted">Noch keine Assets in dieser Bibliothek.</p>
        ) : (
          <ul className="col" style={{ gap: "var(--space-2)", listStyle: "none", padding: 0 }}>
            {assets.map((asset) => (
              <li
                key={asset.id}
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
                  <strong>{asset.name}</strong>
                  <span className="textMuted">
                    {asset.type} · {asset.original_filename} · {formatBytes(asset.size_bytes)}
                  </span>
                  {(asset.tags ?? []).length > 0 ? (
                    <span className="textMuted">
                      Tags: {(asset.tags ?? []).map((t) => t.name).join(", ")}
                    </span>
                  ) : null}
                </div>
                <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                  <Link href={`/productions/${production.id}/library/${asset.id}` as Route}>
                    Details
                  </Link>
                  <button type="button" onClick={() => void onDeleteAsset(asset)}>
                    Löschen
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
