"use client";

import { useEffect, useState } from "react";
import { FileText, Film, ImageIcon, Loader2, Trash2, X } from "lucide-react";

import {
  deleteMedia,
  getMediaAccessUrl,
  updateMedia,
  type StorageMediaListItem,
  type StorageMediaSource,
} from "@/lib/storage-client";

type MediaPreviewModalProps = {
  clientId: number;
  file: StorageMediaListItem | null;
  onClose: () => void;
  onChanged: () => void;
  onError?: (message: string) => void;
};

const KIND_ICON: Record<string, typeof ImageIcon> = {
  image: ImageIcon,
  video: Film,
  document: FileText,
};

function formatSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function isSystemSource(source: StorageMediaSource | string): boolean {
  return source === "enriched_catalog" || source === "backend_ingest" || source === "platform_sync";
}

function sourceLabel(source: StorageMediaSource | string): string {
  if (source === "user_upload") return "Upload manual";
  if (source === "enriched_catalog") return "Enriched Catalog (automatic)";
  if (source === "backend_ingest") return "Agency (automatic)";
  if (source === "platform_sync") return "Platform sync";
  return source || "-";
}

export function MediaPreviewModal({
  clientId,
  file,
  onClose,
  onChanged,
  onError,
}: MediaPreviewModalProps) {
  const [accessUrl, setAccessUrl] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!file) {
      setAccessUrl(null);
      setDisplayName("");
      setDirty(false);
      setError("");
      return;
    }
    setDisplayName(file.display_name || file.original_filename);
    setDirty(false);
    setError("");

    let cancelled = false;
    (async () => {
      try {
        const response = await getMediaAccessUrl({
          clientId,
          mediaId: file.media_id,
          disposition: "inline",
        });
        if (!cancelled) setAccessUrl(response.url);
      } catch (err) {
        if (!cancelled) setAccessUrl(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [clientId, file]);

  if (!file) return null;

  const isSystem = isSystemSource(file.source);
  const Icon = KIND_ICON[file.kind] ?? FileText;

  async function handleSave() {
    if (!file) return;
    setSaving(true);
    setError("");
    try {
      await updateMedia({
        clientId,
        mediaId: file.media_id,
        displayName: displayName.trim() || undefined,
      });
      setDirty(false);
      onChanged();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Nu am putut salva modificările.";
      setError(message);
      onError?.(message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!file) return;
    if (!window.confirm(`Ștergi fișierul "${displayName || file.original_filename}"?`)) return;
    setDeleting(true);
    setError("");
    try {
      await deleteMedia({ clientId, mediaId: file.media_id });
      onChanged();
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Nu am putut șterge fișierul.";
      setError(message);
      onError?.(message);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 py-6"
      onClick={onClose}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        className="wm-card flex w-full max-w-3xl flex-col overflow-hidden"
      >
        <div className="flex items-start justify-between border-b border-slate-200 p-4 dark:border-slate-700">
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-base font-semibold text-slate-900 dark:text-slate-100">
              {displayName || file.original_filename}
            </h3>
            <p className="mt-1 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              <Icon className="h-3 w-3" />
              <span>{file.kind}</span>
              <span>·</span>
              <span>{file.mime_type}</span>
              <span>·</span>
              <span>{formatSize(file.size_bytes)}</span>
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="ml-3 shrink-0 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
            aria-label="Închide"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-center justify-center bg-slate-50 dark:bg-slate-800/40">
          {file.kind === "image" && accessUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={accessUrl} alt={displayName} className="max-h-[420px] w-auto object-contain" />
          ) : (
            <div className="flex h-64 w-full items-center justify-center text-slate-400">
              <Icon className="h-16 w-16" />
            </div>
          )}
        </div>

        <div className="space-y-4 p-4">
          <div>
            <label className="block text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
              Nume afișat
            </label>
            <input
              className="wm-input mt-1"
              value={displayName}
              onChange={(event) => {
                setDisplayName(event.target.value);
                setDirty(true);
              }}
              disabled={isSystem || saving || deleting}
            />
            {isSystem && (
              <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                Acest fișier este generat automat și nu poate fi redenumit sau șters din UI.
              </p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs text-slate-600 dark:text-slate-400">
            <div>
              <span className="block text-[10px] uppercase text-slate-400">Sursă</span>
              <span>{sourceLabel(file.source)}</span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-400">Fișier original</span>
              <span className="truncate" title={file.original_filename}>
                {file.original_filename}
              </span>
            </div>
          </div>
          {error ? <p className="text-xs text-red-600">{error}</p> : null}
        </div>

        <div className="flex items-center justify-between border-t border-slate-200 p-4 dark:border-slate-700">
          <button
            type="button"
            onClick={handleDelete}
            disabled={isSystem || deleting || saving}
            className="inline-flex items-center gap-1.5 rounded-md border border-rose-200 px-3 py-1.5 text-sm text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            Șterge
          </button>
          <div className="flex items-center gap-2">
            <button type="button" onClick={onClose} className="wm-btn-secondary text-sm">
              Închide
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={isSystem || !dirty || saving}
              className="wm-btn-primary text-sm"
            >
              {saving ? "Se salvează..." : "Salvează"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
