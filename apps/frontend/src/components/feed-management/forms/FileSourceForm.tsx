"use client";

import { FormEvent, useState } from "react";
import { ChevronDown, ChevronRight, Eye, EyeOff, Loader2 } from "lucide-react";
import type { FeedSourceType } from "@/lib/types/feed-management";

const FILE_TYPE_OPTIONS: { value: FeedSourceType; label: string }[] = [
  { value: "csv", label: "CSV" },
  { value: "json", label: "JSON" },
  { value: "xml", label: "XML" },
  { value: "google_sheets", label: "Google Sheets" },
];

// Google Sheets uses public URLs / service-account sharing, not HTTP Basic
// Auth — hide the auth panel for that one type. Every other file type
// (CSV / JSON / XML) can optionally be protected with Basic Auth.
const AUTH_CAPABLE_TYPES: ReadonlySet<FeedSourceType> = new Set([
  "csv",
  "json",
  "xml",
]);

type FileSourceFormData = {
  name: string;
  file_type: FeedSourceType;
  url: string;
  feed_auth_username?: string;
  feed_auth_password?: string;
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
  const [authUsername, setAuthUsername] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [showAuthPanel, setShowAuthPanel] = useState(false);
  const [showAuthPassword, setShowAuthPassword] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<keyof FileSourceFormData, string>>>({});

  const canUseBasicAuth = AUTH_CAPABLE_TYPES.has(fileType);

  function validate(): boolean {
    const next: typeof errors = {};
    if (!name.trim()) next.name = "Numele sursei este obligatoriu.";
    if (!url.trim()) {
      next.url = "URL-ul este obligatoriu.";
    } else {
      try { new URL(url); } catch { next.url = "URL-ul nu este valid."; }
    }
    // Basic Auth: both fields must be set together or neither. A
    // username without a password (or vice versa) would produce a half-
    // configured source the backend would reject with 400.
    if (canUseBasicAuth) {
      const hasUsername = authUsername.trim().length > 0;
      const hasPassword = authPassword.trim().length > 0;
      if (hasUsername && !hasPassword) {
        next.feed_auth_password = "Parola este obligatorie când setezi username.";
      }
      if (!hasUsername && hasPassword) {
        next.feed_auth_username = "Username-ul este obligatoriu când setezi parola.";
      }
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    const data: FileSourceFormData = {
      name: name.trim(),
      file_type: fileType,
      url: url.trim(),
    };
    if (canUseBasicAuth && authUsername.trim() && authPassword.trim()) {
      data.feed_auth_username = authUsername.trim();
      data.feed_auth_password = authPassword;
    }
    onSubmit(data);
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
          {fileType === "google_sheets" ? "Linkul trebuie să fie public sau partajat cu serviciul nostru." : "URL-ul direct către fișierul feed-ului. Trebuie să fie accesibil public sau protejat cu HTTP Basic Auth."}
        </p>
      </div>

      {canUseBasicAuth ? (
        <div className="rounded-lg border border-slate-200 dark:border-slate-700">
          <button
            type="button"
            onClick={() => setShowAuthPanel((v) => !v)}
            className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800/50"
            aria-expanded={showAuthPanel}
          >
            <span className="flex items-center gap-2">
              {showAuthPanel ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              Autentificare (opțional)
            </span>
            {authUsername.trim() && authPassword.trim() ? (
              <span className="text-xs text-emerald-600 dark:text-emerald-400">
                ✓ setat
              </span>
            ) : (
              <span className="text-xs text-slate-400">neconfigurat</span>
            )}
          </button>
          {showAuthPanel ? (
            <div className="space-y-4 border-t border-slate-200 p-4 dark:border-slate-700">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Completează dacă feed-ul necesită autentificare HTTP Basic Auth.
                Credențialele sunt criptate la stocare și folosite doar pentru
                descărcarea feed-ului.
              </p>
              <div>
                <label
                  htmlFor="fs-auth-username"
                  className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
                >
                  Username
                </label>
                <input
                  id="fs-auth-username"
                  value={authUsername}
                  onChange={(e) => setAuthUsername(e.target.value)}
                  placeholder="ex: feed_user"
                  className="wm-input"
                  autoComplete="off"
                  spellCheck={false}
                />
                {errors.feed_auth_username ? (
                  <p className="mt-1 text-xs text-red-600">
                    {errors.feed_auth_username}
                  </p>
                ) : null}
              </div>
              <div>
                <label
                  htmlFor="fs-auth-password"
                  className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
                >
                  Password
                </label>
                <div className="relative">
                  <input
                    id="fs-auth-password"
                    type={showAuthPassword ? "text" : "password"}
                    value={authPassword}
                    onChange={(e) => setAuthPassword(e.target.value)}
                    placeholder="••••••••"
                    className="wm-input pr-10"
                    autoComplete="new-password"
                    spellCheck={false}
                  />
                  <button
                    type="button"
                    onClick={() => setShowAuthPassword((v) => !v)}
                    className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    aria-label={showAuthPassword ? "Ascunde parola" : "Afișează parola"}
                    tabIndex={-1}
                  >
                    {showAuthPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {errors.feed_auth_password ? (
                  <p className="mt-1 text-xs text-red-600">
                    {errors.feed_auth_password}
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

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
