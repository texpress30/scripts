"use client";

import { FormEvent, useState } from "react";
import { Loader2 } from "lucide-react";
import type { FeedSourceType } from "@/lib/types/feed-management";

const FILE_TYPE_OPTIONS: { value: FeedSourceType; label: string }[] = [
  { value: "csv", label: "CSV" },
  { value: "json", label: "JSON" },
  { value: "xml", label: "XML" },
  { value: "google_sheets", label: "Google Sheets" },
];

type FileSourceFormData = {
  name: string;
  file_type: FeedSourceType;
  url: string;
};

export function FileSourceForm({
  initialType,
  onSubmit,
  onCancel,
  busy,
}: {
  initialType: FeedSourceType;
  onSubmit: (data: FileSourceFormData) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");
  const [fileType, setFileType] = useState<FeedSourceType>(initialType);
  const [url, setUrl] = useState("");
  const [errors, setErrors] = useState<Partial<Record<keyof FileSourceFormData, string>>>({});

  function validate(): boolean {
    const next: typeof errors = {};
    if (!name.trim()) next.name = "Numele sursei este obligatoriu.";
    if (!url.trim()) {
      next.url = "URL-ul este obligatoriu.";
    } else {
      try { new URL(url); } catch { next.url = "URL-ul nu este valid."; }
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    onSubmit({ name: name.trim(), file_type: fileType, url: url.trim() });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label htmlFor="fs-name" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Source Name</label>
        <input id="fs-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex: Product Catalog Feed" className="wm-input" />
        {errors.name ? <p className="mt-1 text-xs text-red-600">{errors.name}</p> : null}
      </div>
      <div>
        <label htmlFor="fs-type" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">File Type</label>
        <select id="fs-type" value={fileType} onChange={(e) => setFileType(e.target.value as FeedSourceType)} className="wm-input">
          {FILE_TYPE_OPTIONS.map((opt) => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
        </select>
      </div>
      <div>
        <label htmlFor="fs-url" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Feed URL</label>
        <input id="fs-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder={fileType === "google_sheets" ? "https://docs.google.com/spreadsheets/d/..." : "https://example.com/feed.csv"} className="wm-input" />
        {errors.url ? <p className="mt-1 text-xs text-red-600">{errors.url}</p> : null}
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          {fileType === "google_sheets" ? "Linkul trebuie să fie public sau partajat cu serviciul nostru." : "URL-ul direct către fișierul feed-ului. Trebuie să fie accesibil public."}
        </p>
      </div>
      {fileType === "csv" ? (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/50">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Header Mapping</p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Mapping-ul coloanelor se va configura după prima sincronizare, când structura fișierului este disponibilă.</p>
        </div>
      ) : null}
      <div className="flex items-center gap-3 pt-2">
        <button type="submit" className="wm-btn-primary" disabled={busy}>
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {busy ? "Se creează..." : "Creează sursă"}
        </button>
        <button type="button" onClick={onCancel} className="wm-btn-secondary" disabled={busy}>Anulează</button>
      </div>
    </form>
  );
}
