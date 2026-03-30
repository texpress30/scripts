"use client";

import React, { useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";

type TikTokStatusResponse = {
  provider?: string;
  status?: string;
  message?: string;
  token_source?: string;
  token_updated_at?: string | null;
  token_expires_at?: string | null;
  oauth_configured?: boolean;
  has_usable_token?: boolean;
};

type TikTokConnectResponse = {
  authorize_url: string;
  state: string;
};

type TikTokImportResponse = {
  status?: string;
  message?: string;
  platform?: string;
  token_source?: string;
  accounts_discovered?: number;
  imported?: number;
  updated?: number;
  unchanged?: number;
};

type TikTokDiagnosticsResponse = {
  oauth_ok?: boolean;
  oauth_configured?: boolean;
  api_version?: string;
  token_source?: string;
  token_updated_at?: string | null;
  token_expires_at?: string | null;
  has_usable_token?: boolean;
  advertiser_accounts_count?: number;
  db_rows_last_30_days?: number;
  last_sync_at?: string | null;
  warnings?: string[];
  last_error?: string | null;
  mapped_accounts_count?: number;
  [key: string]: unknown;
};

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function statusBadgeTone(status: string): string {
  const normalized = status.trim().toLowerCase();
  if (normalized === "connected") return "bg-emerald-100 text-emerald-700";
  if (normalized === "error") return "bg-red-100 text-red-700";
  if (normalized === "disabled") return "bg-slate-100 text-slate-600";
  return "bg-amber-100 text-amber-700";
}

export function TikTokIntegrationCard() {
  const [status, setStatus] = useState<TikTokStatusResponse | null>(null);
  const [busy, setBusy] = useState<"connect" | "import" | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [importSummary, setImportSummary] = useState<TikTokImportResponse | null>(null);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [diagnosticsBusy, setDiagnosticsBusy] = useState(false);
  const [diagnosticsError, setDiagnosticsError] = useState("");
  const [diagnosticsData, setDiagnosticsData] = useState<TikTokDiagnosticsResponse | null>(null);
  const [copyMessage, setCopyMessage] = useState("");

  async function loadStatus() {
    try {
      const payload = await apiRequest<TikTokStatusResponse>("/integrations/tiktok-ads/status");
      setStatus(payload);
    } catch {
      // keep robust UI fallback
    }
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  async function connectTikTok() {
    setBusy("connect");
    setError("");
    setMessage("");
    setImportSummary(null);
    try {
      const payload = await apiRequest<TikTokConnectResponse>("/integrations/tiktok-ads/connect");
      setMessage("Redirecting către TikTok OAuth...");
      window.location.href = payload.authorize_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut iniția TikTok OAuth");
    } finally {
      setBusy(null);
    }
  }

  async function importAccounts() {
    setBusy("import");
    setError("");
    setMessage("");
    setImportSummary(null);
    try {
      const payload = await apiRequest<TikTokImportResponse>("/integrations/tiktok-ads/import-accounts", { method: "POST" });
      setImportSummary(payload);
      setMessage(payload.message ?? "Import TikTok finalizat.");
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut importa conturile TikTok");
    } finally {
      setBusy(null);
    }
  }

  async function loadDiagnostics() {
    setCopyMessage("");
    setDiagnosticsError("");
    setDiagnosticsBusy(true);
    try {
      const payload = await apiRequest<TikTokDiagnosticsResponse>("/integrations/tiktok-ads/diagnostics");
      setDiagnosticsData(payload);
    } catch (err) {
      setDiagnosticsError(err instanceof Error ? err.message : "Nu am putut încărca diagnosticele TikTok Ads");
      setDiagnosticsData(null);
    } finally {
      setDiagnosticsBusy(false);
    }
  }

  async function openDiagnostics() {
    setDiagnosticsOpen(true);
    await loadDiagnostics();
  }

  async function copyDiagnosticsJson() {
    if (!diagnosticsData) return;
    setCopyMessage("");
    try {
      await navigator.clipboard.writeText(JSON.stringify(diagnosticsData, null, 2));
      setCopyMessage("JSON copiat în clipboard.");
    } catch (err) {
      setCopyMessage(err instanceof Error ? err.message : "Nu am putut copia JSON-ul.");
    }
  }

  const diagnosticsWarnings = useMemo(() => (Array.isArray(diagnosticsData?.warnings) ? diagnosticsData?.warnings : []), [diagnosticsData]);

  const normalizedStatus = String(status?.status ?? "pending");
  const isOAuthConfigured = Boolean(status?.oauth_configured);
  const hasUsableToken = Boolean(status?.has_usable_token);
  const connectDisabledReason = useMemo(() => {
    if (isOAuthConfigured) return "";
    return "Configurează întâi TIKTOK_APP_ID / TIKTOK_APP_SECRET / TIKTOK_REDIRECT_URI în backend.";
  }, [isOAuthConfigured]);

  return (
    <article className="wm-card p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">TikTok Ads</h2>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusBadgeTone(normalizedStatus)}`}>{normalizedStatus}</span>
      </div>

      <p className="mt-2 text-sm text-slate-600">{status?.message ?? "TikTok status indisponibil momentan."}</p>
      <div className="mt-2 space-y-1 text-xs text-slate-500">
        <p>Token source: {status?.token_source ?? "-"}</p>
        <p>Token updated at: {formatDate(status?.token_updated_at)}</p>
        <p>Token expires at: {formatDate(status?.token_expires_at)}</p>
      </div>

      {error ? <p className="mt-3 text-xs text-red-600">{error}</p> : null}
      {message ? <p className="mt-3 text-xs text-emerald-600">{message}</p> : null}

      {importSummary ? (
        <div className="mt-3 rounded-md bg-slate-50 p-2 text-xs text-slate-700">
          <p>Import summary</p>
          <p>accounts_discovered: {importSummary.accounts_discovered ?? 0}</p>
          <p>imported: {importSummary.imported ?? 0}</p>
          <p>updated: {importSummary.updated ?? 0}</p>
          <p>unchanged: {importSummary.unchanged ?? 0}</p>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          onClick={() => void connectTikTok()}
          disabled={busy !== null || !isOAuthConfigured}
          className="wm-btn-primary disabled:opacity-50"
          title={connectDisabledReason}
        >
          {busy === "connect" ? "Connecting..." : "Connect TikTok"}
        </button>
        <button
          onClick={() => void importAccounts()}
          disabled={busy !== null || !hasUsableToken}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          title={hasUsableToken ? "" : "Import necesită token TikTok utilizabil."}
        >
          {busy === "import" ? "Importing..." : "Import Accounts"}
        </button>
        <button
          onClick={() => void openDiagnostics()}
          disabled={busy !== null}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Diagnostics
        </button>
      </div>

      {!isOAuthConfigured ? <p className="mt-2 text-xs text-amber-700">{connectDisabledReason}</p> : null}
      {!hasUsableToken ? <p className="mt-1 text-xs text-slate-500">Finalizează connect OAuth înainte de import accounts.</p> : null}

      {diagnosticsOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4" role="dialog" aria-modal="true">
          <div className="wm-card max-h-[90vh] w-full max-w-3xl overflow-y-auto p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-900">TikTok Ads Diagnostics</h3>
              <button className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700" onClick={() => setDiagnosticsOpen(false)}>
                Close
              </button>
            </div>

            {diagnosticsBusy ? <p className="mt-3 text-sm text-slate-600">Loading diagnostics...</p> : null}
            {diagnosticsError ? <pre className="mt-3 whitespace-pre-wrap break-words rounded bg-red-50 p-3 text-xs text-red-700">{diagnosticsError}</pre> : null}

            {!diagnosticsBusy && diagnosticsData ? (
              <div className="mt-3 space-y-3 text-sm text-slate-700">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <p>
                    <span className="font-medium">oauth_ok:</span> {String(Boolean(diagnosticsData.oauth_ok))}
                  </p>
                  <p>
                    <span className="font-medium">oauth_configured:</span> {String(Boolean(diagnosticsData.oauth_configured))}
                  </p>
                  <p>
                    <span className="font-medium">api_version:</span> {diagnosticsData.api_version ?? "-"}
                  </p>
                  <p>
                    <span className="font-medium">token_source:</span> {String(diagnosticsData.token_source ?? "missing")}
                  </p>
                  <p>
                    <span className="font-medium">has_usable_token:</span> {String(Boolean(diagnosticsData.has_usable_token))}
                  </p>
                  <p>
                    <span className="font-medium">token_expires_at:</span> {diagnosticsData.token_expires_at ?? "-"}
                  </p>
                  <p>
                    <span className="font-medium">advertiser_accounts:</span> {diagnosticsData.advertiser_accounts_count ?? 0}
                  </p>
                  <p>
                    <span className="font-medium">mapped_accounts:</span> {diagnosticsData.mapped_accounts_count ?? 0}
                  </p>
                  <p>
                    <span className="font-medium">db_rows_last_30_days:</span> {diagnosticsData.db_rows_last_30_days ?? 0}
                  </p>
                  <p>
                    <span className="font-medium">last_sync_at:</span> {diagnosticsData.last_sync_at ?? "-"}
                  </p>
                </div>

                <div>
                  <p className="font-medium">warnings</p>
                  {diagnosticsWarnings.length > 0 ? (
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-amber-700">
                      {diagnosticsWarnings.map((warning, idx) => (
                        <li key={`${warning}-${idx}`}>{warning}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-xs text-slate-500">No warnings.</p>
                  )}
                </div>

                <div>
                  <p className="font-medium">last_error</p>
                  <pre className="mt-1 whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-xs text-slate-700">{String(diagnosticsData.last_error ?? "") || "-"}</pre>
                </div>

                <div className="flex items-center gap-3">
                  <button className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50" onClick={() => void copyDiagnosticsJson()}>
                    Copy
                  </button>
                  {copyMessage ? <p className="text-xs text-slate-600">{copyMessage}</p> : null}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </article>
  );
}
