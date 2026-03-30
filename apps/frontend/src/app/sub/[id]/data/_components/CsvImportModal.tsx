"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE_URL, getAuthToken } from "@/lib/api";

export type CsvImportPreviewResponse = {
  total: number;
  valid: number;
  errors: number;
  columns_detected: string[];
  columns_mapping: Array<string | null>;
  rows: Array<{
    row_index: number;
    status: "valid" | "error";
    error_message?: string;
    data: Record<string, unknown>;
  }>;
};

type ImportConfirmResponse = {
  imported: number;
  inserted: number;
  updated: number;
  errors: Array<{ row_index: number; error_message: string }>;
  message: string;
};

type CsvImportModalProps = {
  open: boolean;
  onClose: () => void;
  clientId: number;
  previewData: CsvImportPreviewResponse | null;
  onPreviewLoaded: (data: CsvImportPreviewResponse) => void;
  onPreviewReset: () => void;
  onImportSuccess: () => void;
};

export function CsvImportModal({ open, onClose, clientId, previewData, onPreviewLoaded, onPreviewReset, onImportSuccess }: CsvImportModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [fileError, setFileError] = useState("");
  const [importResult, setImportResult] = useState<ImportConfirmResponse | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  const resetState = useCallback(() => {
    setFile(null);
    setDragOver(false);
    setUploading(false);
    setImporting(false);
    setErrorMessage("");
    setFileError("");
    setImportResult(null);
  }, []);

  const handleClose = useCallback(() => {
    const wasSuccess = importResult !== null;
    resetState();
    onPreviewReset();
    onClose();
    if (wasSuccess) onImportSuccess();
  }, [resetState, onPreviewReset, onClose, onImportSuccess, importResult]);

  const handleSuccessClose = useCallback(() => {
    resetState();
    onPreviewReset();
    onClose();
    onImportSuccess();
  }, [resetState, onPreviewReset, onClose, onImportSuccess]);

  const handleBack = useCallback(() => {
    onPreviewReset();
  }, [onPreviewReset]);

  // Escape key
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, handleClose]);

  // Focus trap
  useEffect(() => {
    if (!open || !modalRef.current) return;
    const modal = modalRef.current;
    const focusable = modal.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (focusable.length > 0) focusable[0].focus();

    const trap = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", trap);
    return () => document.removeEventListener("keydown", trap);
  }, [open, previewData, importResult]);

  const validateFile = (f: File): boolean => {
    setFileError("");
    if (!f.name.toLowerCase().endsWith(".csv")) {
      setFileError("Doar fișiere CSV sunt acceptate");
      return false;
    }
    return true;
  };

  const handleFileSelect = (f: File) => {
    setErrorMessage("");
    if (validateFile(f)) {
      setFile(f);
    } else {
      setFile(null);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFileSelect(f);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFileSelect(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setErrorMessage("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const token = getAuthToken();
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const response = await fetch(`${API_BASE_URL}/clients/${clientId}/data/import-preview`, {
        method: "POST",
        headers,
        body: formData,
      });

      if (!response.ok) {
        const text = await response.text();
        let detail = `Eroare ${response.status}`;
        try {
          const parsed = JSON.parse(text);
          if (typeof parsed.detail === "string") detail = parsed.detail;
        } catch { /* use default */ }
        setErrorMessage(detail);
        return;
      }

      const data: CsvImportPreviewResponse = await response.json();
      console.log(`[CSV-IMPORT] Preview loaded: ${data.total} rows, ${data.valid} valid, ${data.errors} errors`);
      onPreviewLoaded(data);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Eroare la trimiterea fișierului");
    } finally {
      setUploading(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!previewData) return;
    const validRows = previewData.rows.filter((r) => r.status === "valid");
    if (validRows.length === 0) return;

    setImporting(true);
    setErrorMessage("");

    try {
      const token = getAuthToken();
      const headers: HeadersInit = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const response = await fetch(`${API_BASE_URL}/clients/${clientId}/data/import-confirm`, {
        method: "POST",
        headers,
        body: JSON.stringify({ rows: validRows }),
      });

      if (!response.ok) {
        const text = await response.text();
        let detail = `Eroare ${response.status}`;
        try {
          const parsed = JSON.parse(text);
          if (typeof parsed.detail === "string") detail = parsed.detail;
        } catch { /* use default */ }
        setErrorMessage(detail);
        return;
      }

      const data: ImportConfirmResponse = await response.json();
      console.log(`[CSV-IMPORT] Import confirmed: ${data.inserted} inserted, ${data.updated} updated`);
      setImportResult(data);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Eroare la importul datelor");
    } finally {
      setImporting(false);
    }
  };

  if (!open) return null;

  const canUpload = !!file && !fileError && !uploading;
  const showPreview = previewData !== null && importResult === null;
  const showSuccess = importResult !== null;
  const canConfirm = previewData !== null && previewData.valid > 0 && !importing;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
      role="dialog"
      aria-modal="true"
      aria-label="Import CSV"
    >
      <div
        ref={modalRef}
        className={`relative flex max-h-[90vh] flex-col rounded-lg bg-white p-6 shadow-xl ${showPreview ? "w-full max-w-4xl" : "w-full max-w-lg"}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Import CSV</h2>
          <button
            type="button"
            className="rounded p-1 text-slate-400 hover:text-slate-600"
            onClick={handleClose}
            aria-label="Închide"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        {/* Error banner */}
        {errorMessage && (
          <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {errorMessage}
          </div>
        )}

        {showSuccess ? (
          /* ── Success screen ── */
          <div className="mt-6 flex flex-col items-center py-8">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="mt-4 text-center text-base font-medium text-slate-800">
              {importResult.message}
            </p>
            <button
              type="button"
              className="mt-6 rounded-md bg-indigo-600 px-6 py-2 text-sm font-medium text-white hover:bg-indigo-700"
              onClick={handleSuccessClose}
            >
              Închide
            </button>
          </div>
        ) : showPreview ? (
          /* ── Preview table view ── */
          <>
            {/* Summary badges */}
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                Total: {previewData.total} rânduri
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700">
                Valide: {previewData.valid}
              </span>
              {previewData.errors > 0 ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-3 py-1 text-xs font-medium text-rose-700">
                  Erori: {previewData.errors}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-50 px-3 py-1 text-xs font-medium text-slate-400">
                  Erori: 0
                </span>
              )}
            </div>

            {/* Warning for errors */}
            {previewData.errors > 0 && (
              <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                {previewData.errors} {previewData.errors === 1 ? "rând cu erori" : "rânduri cu erori"} nu {previewData.errors === 1 ? "va" : "vor"} fi {previewData.errors === 1 ? "importat" : "importate"}. Doar rândurile valide vor fi salvate.
              </div>
            )}

            {/* Scrollable table */}
            <div className="mt-3 min-h-0 flex-1 overflow-auto rounded-md border border-slate-200">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-slate-50">
                  <tr>
                    <th className="whitespace-nowrap border-b border-slate-200 px-3 py-2 font-medium text-slate-600">#</th>
                    {previewData.columns_detected.map((col) => (
                      <th key={col} className="whitespace-nowrap border-b border-slate-200 px-3 py-2 font-medium text-slate-600">
                        {col}
                      </th>
                    ))}
                    <th className="whitespace-nowrap border-b border-slate-200 px-3 py-2 font-medium text-slate-600">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {previewData.rows.map((row) => {
                    const isError = row.status === "error";
                    return (
                      <tr
                        key={row.row_index}
                        className={isError ? "bg-rose-50" : "hover:bg-emerald-50/40"}
                      >
                        <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-slate-500">
                          {row.row_index}
                        </td>
                        {previewData.columns_detected.map((col, colIdx) => {
                          const dbKey = previewData.columns_mapping[colIdx];
                          const val = dbKey ? row.data[dbKey] : undefined;
                          const display = val === null || val === undefined || val === "" ? "-" : String(val);
                          return (
                            <td key={col} className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-slate-700">
                              {display}
                            </td>
                          );
                        })}
                        <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5">
                          {isError ? (
                            <span className="inline-block max-w-[220px] truncate rounded bg-rose-100 px-2 py-0.5 text-xs text-rose-700" title={row.error_message}>
                              {row.error_message}
                            </span>
                          ) : (
                            <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">
                              ✓ Valid
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Footer buttons – preview view */}
            <div className="mt-4 flex items-center justify-between">
              <button
                type="button"
                className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                onClick={handleBack}
                disabled={importing}
              >
                ← Înapoi
              </button>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={handleClose}
                  disabled={importing}
                >
                  Anulează
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={!canConfirm}
                  onClick={handleConfirmImport}
                  {...(previewData.valid === 0 ? { title: "Nu există rânduri valide de importat" } : {})}
                >
                  {importing && (
                    <svg className="h-4 w-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  )}
                  Confirmă importul
                </button>
              </div>
            </div>
          </>
        ) : (
          /* ── File picker view ── */
          <>
            {/* Drop zone */}
            <div
              className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 transition-colors ${
                dragOver
                  ? "border-indigo-400 bg-indigo-50"
                  : "border-slate-300 bg-slate-50 hover:border-slate-400"
              }`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="mb-2 h-8 w-8 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
              <p className="text-sm text-slate-600">
                {file ? file.name : "Trage CSV-ul aici sau click pentru selectare"}
              </p>
              {file && (
                <p className="mt-1 text-xs text-slate-400">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleInputChange}
              />
            </div>

            {/* File validation error */}
            {fileError && (
              <p className="mt-2 text-sm text-rose-600">{fileError}</p>
            )}

            {/* Footer buttons – file picker view */}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                onClick={handleClose}
              >
                Anulează
              </button>
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={!canUpload}
                onClick={handleUpload}
              >
                {uploading && (
                  <svg className="h-4 w-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                )}
                Previzualizează
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
