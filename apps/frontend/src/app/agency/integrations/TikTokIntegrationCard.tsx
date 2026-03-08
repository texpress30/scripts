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
      </div>

      {!isOAuthConfigured ? <p className="mt-2 text-xs text-amber-700">{connectDisabledReason}</p> : null}
      {!hasUsableToken ? <p className="mt-1 text-xs text-slate-500">Finalizează connect OAuth înainte de import accounts.</p> : null}
    </article>
  );
}
