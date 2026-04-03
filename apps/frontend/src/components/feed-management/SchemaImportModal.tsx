"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Upload, CheckCircle2, AlertCircle, X } from "lucide-react";
import { apiRequest } from "@/lib/api";

type ImportResult = {
  status: string;
  channel_slug: string;
  catalog_type: string;
  summary: {
    fields_added: number;
    fields_updated: number;
    fields_deprecated: number;
    total_fields_in_superset: number;
  };
  s3_path: string | null;
  import_id: string;
};

type Props = {
  open: boolean;
  onClose: () => void;
  catalogType: string;
  channelSlug: string | null;
  onImportSuccess: () => void;
};

export function SchemaImportModal({
  open,
  onClose,
  catalogType,
  channelSlug,
  onImportSuccess,
}: Props) {
  const [slug, setSlug] = useState(channelSlug ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      setSlug(channelSlug ?? "");
      setFile(null);
      setResult(null);
      setError("");
      setImporting(false);
      setDragOver(false);
    }
  }, [open, channelSlug]);

  // Escape key
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const handleClose = useCallback(() => {
    if (result) onImportSuccess();
    onClose();
  }, [result, onImportSuccess, onClose]);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
  }

  async function handleImport() {
    if (!file || !slug.trim()) return;

    setImporting(true);
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("channel_slug", slug.trim());
      formData.append("catalog_type", catalogType);
      formData.append("file", file);

      const token = typeof window !== "undefined" ? localStorage.getItem("mcc_token") : null;
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
      const resp = await fetch(`${baseUrl}/feed-management/schemas/import`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!resp.ok) {
        const body = await resp.json().catch(() => null);
        throw new Error(body?.detail ?? `Eroare HTTP ${resp.status}`);
      }

      const data: ImportResult = await resp.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare la import.");
    } finally {
      setImporting(false);
    }
  }

  if (!open) return null;

  const isChannelLocked = !!channelSlug;
  const canSubmit = !!file && slug.trim().length > 0 && !importing;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
      role="dialog"
      aria-modal="true"
    >
      <div className="wm-card w-full max-w-lg p-6">
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Import feed schema
          </h2>
          <button type="button" onClick={handleClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Success result */}
        {result ? (
          <div className="space-y-4">
            <div className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-900/20">
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
              <div className="text-sm">
                <p className="font-semibold text-emerald-800 dark:text-emerald-300">Import reusit!</p>
                <ul className="mt-2 space-y-1 text-emerald-700 dark:text-emerald-400">
                  <li>Campuri noi adaugate: <strong>{result.summary.fields_added}</strong></li>
                  <li>Campuri actualizate: <strong>{result.summary.fields_updated}</strong></li>
                  <li>Campuri depreciate: <strong>{result.summary.fields_deprecated}</strong></li>
                  <li>Total campuri in superset: <strong>{result.summary.total_fields_in_superset}</strong></li>
                </ul>
              </div>
            </div>
            <div className="flex justify-end">
              <button type="button" onClick={handleClose} className="wm-btn-primary">
                Inchide
              </button>
            </div>
          </div>
        ) : (
          /* Form */
          <div className="space-y-4">
            {/* Channel slug */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Channel slug
              </label>
              {isChannelLocked ? (
                <input
                  type="text"
                  value={slug}
                  readOnly
                  className="wm-input bg-slate-50 dark:bg-slate-800"
                />
              ) : (
                <input
                  type="text"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  placeholder="ex: tiktok_auto_inventory"
                  className="wm-input"
                />
              )}
            </div>

            {/* Catalog type (readonly) */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Catalog type
              </label>
              <input
                type="text"
                value={catalogType}
                readOnly
                className="wm-input bg-slate-50 dark:bg-slate-800"
              />
            </div>

            {/* File drop zone */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Fisier CSV
              </label>
              <div
                className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 transition-colors ${
                  dragOver
                    ? "border-indigo-400 bg-indigo-50 dark:border-indigo-600 dark:bg-indigo-900/20"
                    : "border-slate-300 bg-slate-50 hover:border-slate-400 dark:border-slate-600 dark:bg-slate-800 dark:hover:border-slate-500"
                }`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="mb-2 h-6 w-6 text-slate-400" />
                {file ? (
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    {file.name} <span className="text-slate-400">({(file.size / 1024).toFixed(1)} KB)</span>
                  </p>
                ) : (
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Trage CSV-ul aici sau click pentru selectare
                  </p>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </div>
            </div>

            {/* CSV format info */}
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Format CSV: coloane minime <code className="font-mono">field_key</code> si <code className="font-mono">display_name</code>.
              Optionale: description, data_type, is_required, allowed_values, format_pattern, example_value, channel_field_name.
            </p>

            {/* Error */}
            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-900/20">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
              </div>
            )}

            {/* Footer buttons */}
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={handleClose} className="wm-btn-secondary">
                Anuleaza
              </button>
              <button
                type="button"
                onClick={() => void handleImport()}
                disabled={!canSubmit}
                className="wm-btn-primary inline-flex items-center gap-2"
              >
                {importing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Se importa...
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4" />
                    Importa
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
