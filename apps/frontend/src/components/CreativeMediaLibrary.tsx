"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Upload, Image as ImageIcon, Video as VideoIcon, AlertCircle } from "lucide-react";

import { apiRequest } from "@/lib/api";
import { completeDirectUpload, getMediaAccessUrl, initDirectUpload, uploadFileToPresignedUrl, type StorageKind } from "@/lib/storage-client";

export type CreativeMediaItem = {
  media_id: string;
  client_id: number;
  kind: "image" | "video" | "document";
  source: string;
  status: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number | null;
  created_at: string | null;
  uploaded_at: string | null;
};

type StorageMediaListResponse = {
  items: CreativeMediaItem[];
  limit: number;
  offset: number;
  total: number;
};

export function formatBytes(value: number | null | undefined): string {
  if (!Number.isFinite(value ?? NaN) || (value ?? 0) <= 0) return "-";
  const bytes = Number(value);
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let size = bytes / 1024;
  let idx = 0;
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024;
    idx += 1;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[idx]}`;
}

function parseDate(value: string | null): string {
  const raw = String(value ?? "").trim();
  if (!raw) return "-";
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  return parsed.toLocaleString("ro-RO", { dateStyle: "medium", timeStyle: "short" });
}

function mapFileKind(file: File): StorageKind | null {
  const mime = file.type.toLowerCase();
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  return null;
}

export function CreativeMediaLibrary({
  clientId,
  onSelectMedia,
}: {
  clientId: number | null;
  onSelectMedia?: (media: CreativeMediaItem | null) => void;
}) {
  const [kindFilter, setKindFilter] = useState<"all" | "image" | "video">("all");
  const [items, setItems] = useState<CreativeMediaItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const [selectedMediaId, setSelectedMediaId] = useState<string>("");
  const selectedMedia = useMemo(() => items.find((item) => item.media_id === selectedMediaId) ?? null, [items, selectedMediaId]);

  const [previewUrl, setPreviewUrl] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const loadMedia = useCallback(async (): Promise<CreativeMediaItem[]> => {
    if (!clientId || clientId <= 0) {
      setItems([]);
      setSelectedMediaId("");
      setErrorMessage("");
      return [];
    }

    setLoading(true);
    setErrorMessage("");
    try {
      const query = new URLSearchParams({
        client_id: String(clientId),
        limit: "50",
        offset: "0",
      });
      if (kindFilter !== "all") query.set("kind", kindFilter);
      const payload = await apiRequest<StorageMediaListResponse>(`/storage/media?${query.toString()}`);
      const nextItems = Array.isArray(payload.items) ? payload.items : [];
      setItems(nextItems);
      setSelectedMediaId((prev) => (prev && nextItems.some((item) => item.media_id === prev) ? prev : ""));
      return nextItems;
    } catch (err) {
      setItems([]);
      setSelectedMediaId("");
      setErrorMessage(err instanceof Error ? err.message : "Nu am putut încărca media din storage.");
      return [];
    } finally {
      setLoading(false);
    }
  }, [clientId, kindFilter]);

  useEffect(() => {
    void loadMedia();
  }, [loadMedia]);

  useEffect(() => {
    if (!selectedMedia) {
      setPreviewUrl("");
      setPreviewError("");
      setPreviewLoading(false);
      onSelectMedia?.(null);
      return;
    }

    onSelectMedia?.(selectedMedia);

    if (!clientId || selectedMedia.status !== "ready") {
      setPreviewUrl("");
      setPreviewError("Media nu este gata pentru preview.");
      setPreviewLoading(false);
      return;
    }

    const validClientId = clientId;
    const mediaId = selectedMedia.media_id;
    let ignore = false;
    setPreviewLoading(true);
    setPreviewError("");

    async function loadPreview() {
      try {
        const access = await getMediaAccessUrl({ clientId: validClientId, mediaId, disposition: "inline" });
        if (!ignore) setPreviewUrl(String(access.url || "").trim());
      } catch (err) {
        if (!ignore) {
          setPreviewUrl("");
          setPreviewError(err instanceof Error ? err.message : "Nu am putut genera preview-ul media.");
        }
      } finally {
        if (!ignore) setPreviewLoading(false);
      }
    }

    void loadPreview();
    return () => {
      ignore = true;
    };
  }, [clientId, onSelectMedia, selectedMedia]);

  async function onUploadPick(file: File) {
    if (!clientId || clientId <= 0) {
      setUploadError("Selectează mai întâi un client.");
      return;
    }

    const kind = mapFileKind(file);
    if (!kind) {
      setUploadError("Fișier invalid. Acceptăm doar imagini sau video.");
      return;
    }

    if (file.size > 120 * 1024 * 1024) {
      setUploadError("Fișierul depășește limita de 120 MB.");
      return;
    }

    setUploadError("");
    setUploading(true);
    try {
      const initPayload = await initDirectUpload({
        clientId,
        kind,
        fileName: file.name,
        mimeType: file.type || "application/octet-stream",
        sizeBytes: file.size,
        metadata: { source: "creative_media_library" },
      });

      await uploadFileToPresignedUrl({
        url: initPayload.upload.url,
        method: initPayload.upload.method,
        headers: initPayload.upload.headers,
        file,
      });

      await completeDirectUpload({ clientId, mediaId: initPayload.media_id });

      const refreshed = await loadMedia();
      const uploaded = refreshed.find((item) => item.media_id === initPayload.media_id);
      if (uploaded) setSelectedMediaId(uploaded.media_id);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload media eșuat.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="mcc-card space-y-4 p-4" data-testid="creative-media-library">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-foreground">Media Library</h2>
          <p className="text-sm text-muted-foreground">Browse, upload, preview și selectează media pentru pasul următor.</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="mcc-input h-9 text-sm"
            value={kindFilter}
            onChange={(event) => setKindFilter(event.target.value as "all" | "image" | "video")}
            data-testid="media-kind-filter"
          >
            <option value="all">Image + Video</option>
            <option value="image">Doar imagini</option>
            <option value="video">Doar video</option>
          </select>
          <label className="mcc-btn-primary inline-flex cursor-pointer items-center gap-2">
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Upload media
            <input
              type="file"
              className="hidden"
              data-testid="creative-media-upload-input"
              accept="image/*,video/*"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void onUploadPick(file);
                event.currentTarget.value = "";
              }}
            />
          </label>
        </div>
      </div>

      {uploadError ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{uploadError}</div> : null}
      {errorMessage ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage}</div> : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-2">
          {loading ? (
            <div className="flex items-center gap-2 rounded-md border border-border px-3 py-5 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Se încarcă media...
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-md border border-border px-3 py-5 text-sm text-muted-foreground">Nu există media pentru filtrul curent.</div>
          ) : (
            <ul className="space-y-2" data-testid="creative-media-items">
              {items.map((item) => {
                const isSelected = item.media_id === selectedMediaId;
                return (
                  <li key={item.media_id}>
                    <button
                      type="button"
                      onClick={() => setSelectedMediaId(item.media_id)}
                      aria-pressed={isSelected}
                      className={`w-full rounded-md border px-3 py-2 text-left transition ${
                        isSelected ? "border-indigo-500 bg-indigo-50" : "border-border hover:bg-muted/40"
                      }`}
                      data-testid={`media-item-${item.media_id}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-foreground">{item.original_filename || item.media_id}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {item.kind.toUpperCase()} · {item.status} · {formatBytes(item.size_bytes)}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">Creat: {parseDate(item.created_at)}</p>
                        </div>
                        {item.kind === "video" ? <VideoIcon className="h-4 w-4 text-muted-foreground" /> : <ImageIcon className="h-4 w-4 text-muted-foreground" />}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <aside className="rounded-md border border-border bg-muted/20 p-3" data-testid="creative-media-preview">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Preview</p>
          {!selectedMedia ? (
            <p className="mt-3 text-sm text-muted-foreground">Selectează o media pentru preview.</p>
          ) : (
            <>
              <p className="mt-2 text-sm font-medium text-foreground">Selectat: {selectedMedia.original_filename || selectedMedia.media_id}</p>
              <p className="mt-1 text-xs text-muted-foreground">Media ID pentru pasul următor: {selectedMedia.media_id}</p>

              <div className="mt-3 rounded-md border border-border bg-background p-2">
                {previewLoading ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" /> Se încarcă preview...
                  </div>
                ) : previewError ? (
                  <div className="flex items-start gap-2 text-sm text-amber-700">
                    <AlertCircle className="mt-0.5 h-4 w-4" />
                    <span>{previewError}</span>
                  </div>
                ) : previewUrl === "" ? (
                  <p className="text-sm text-muted-foreground">Preview indisponibil.</p>
                ) : selectedMedia.kind === "video" ? (
                  <video controls className="max-h-60 w-full rounded" src={previewUrl} data-testid="creative-media-preview-video" />
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={previewUrl} alt={selectedMedia.original_filename || "media preview"} className="max-h-60 w-full rounded object-contain" data-testid="creative-media-preview-image" />
                )}
              </div>
            </>
          )}
        </aside>
      </div>
    </section>
  );
}
