import type { Tag } from "@/lib/types/tag";

export type AssetType =
  | "video"
  | "audio"
  | "image"
  | "text"
  | "document"
  | "data"
  | "other";

export const ASSET_TYPES: AssetType[] = [
  "video",
  "audio",
  "image",
  "text",
  "document",
  "data",
  "other"
];

export type Asset = {
  id: string;
  production_id: string;
  name: string;
  type: AssetType;
  original_filename: string;
  storage_key: string;
  mime_type: string;
  size_bytes: number;
  checksum: string;
  description: string | null;
  metadata: Record<string, unknown>;
  tags: Tag[];
  created_at: string;
  updated_at: string;
};

export type AssetPreview = {
  asset_id: string;
  production_id: string;
  mime_type: string;
  kind: "image" | "audio" | "video" | "text" | "json" | "none";
  preview_available: boolean;
  text_excerpt: string | null;
  size_bytes: number;
  original_filename: string;
};

export type AssetUpdateInput = {
  name?: string;
  type?: AssetType;
  description?: string | null;
  metadata?: Record<string, unknown>;
};
