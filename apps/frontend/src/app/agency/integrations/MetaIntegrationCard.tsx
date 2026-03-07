"use client";

import React, { useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";

type MetaConnectResponse = {
  authorize_url: string;
  state: string;
};

type MetaImportResponse = {
  status?: string;
  message?: string;
  platform?: string;
  token_source?: string;
  accounts_discovered?: number;
  imported?: number;
  updated?: number;
  unchanged?: number;
};

type MetaStatusResponse = {
  provider?: string;
  status?: string;
  message?: string;
  token_source?: string;
  token_updated_at?: string | null;
  token_expires_at?: string | null;
  oauth_configured?: boolean;
  has_usable_token?: boolean;
  [key: string]: unknown;
};

type IntegrationStatusUi = {
  toneClass: string;
  label: string;
};

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function normalizeIntegrationStatus(value?: string | null): IntegrationStatusUi {
  const normalized = String(value || "").trim().toLowerCase();
  if (["connected", "ok", "active", "enabled", "ready", "healthy", "success"].includes(normalized)) {
    return { label: "Conectat", toneClass: "bg-emerald-100 text-emerald-700" };
  }
  if (["pending", "not_configured", "not_connected", "setup_required", "placeholder"].includes(normalized)) {
    return { label: "În așteptare", toneClass: "bg-amber-100 text-amber-700" };
  }
  if (["disabled", "off", "inactive"].includes(normalized)) {
    return { label: "Dezactivat", toneClass: "bg-slate-200 text-slate-700" };
  }
  if (["error", "failed", "failure", "unhealthy"].includes(normalized)) {
    return { label: "Eroare", toneClass: "bg-red-100 text-red-700" };
  }
  return { label: "Necunoscut", toneClass: "bg-slate-200 text-slate-700" };
}

export function MetaIntegrationCard() {
  const [metaStatus, setMetaStatus] = useState<MetaStatusResponse | null>(null);
  const [metaLoading, setMetaLoading] = useState(true);
  const [metaStatusError, setMetaStatusError] = useState("");
  const [metaConnectError, setMetaConnectError] = useState("");
  const [metaImportError, setMetaImportError] = useState("");
  const [metaImportResult, setMetaImportResult] = useState<MetaImportResponse | null>(null);
  const [metaBusy, setMetaBusy] = useState<"connect" | "import" | null>(null);

  async function loadMetaStatus() {
    setMetaLoading(true);
    setMetaStatusError("");
    try {
      const payload = await apiRequest<MetaStatusResponse>("/integrations/meta-ads/status");
      setMetaStatus(payload);
    } catch (err) {
      setMetaStatus(null);
      setMetaStatusError(err instanceof Error ? err.message : "Nu am putut încărca statusul Meta Ads");
    } finally {
      setMetaLoading(false);
    }
  }

  useEffect(() => {
    void loadMetaStatus();
  }, []);

  async function connectMetaAds() {
    setMetaConnectError("");
    setMetaBusy("connect");
    try {
      const payload = await apiRequest<MetaConnectResponse>("/integrations/meta-ads/connect");
      window.location.href = payload.authorize_url;
    } catch (err) {
      setMetaConnectError(err instanceof Error ? err.message : "Nu am putut iniția conectarea Meta Ads");
      setMetaBusy(null);
    }
  }

  async function importMetaAccounts() {
    setMetaImportError("");
    setMetaImportResult(null);
    setMetaBusy("import");
    try {
      const payload = await apiRequest<MetaImportResponse>("/integrations/meta-ads/import-accounts", { method: "POST" });
      setMetaImportResult(payload);
      await loadMetaStatus();
    } catch (err) {
      setMetaImportError(err instanceof Error ? err.message : "Nu am putut importa conturile Meta Ads");
    } finally {
      setMetaBusy(null);
    }
  }

  const metaStatusUi = metaStatusError
    ? { label: "Eroare", toneClass: "bg-red-100 text-red-700" }
    : normalizeIntegrationStatus(metaStatus?.status);
  const metaOauthConfigured = Boolean(metaStatus?.oauth_configured);
  const metaTokenSource = String(metaStatus?.token_source || "missing").trim().toLowerCase();
  const metaHasUsableToken = Boolean(metaStatus?.has_usable_token) || metaStatus?.status === "connected" || ["database", "env_fallback", "runtime"].includes(metaTokenSource);

  return (
    <article className="wm-card p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">Meta Ads</h2>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${metaStatusUi.toneClass}`}>{metaStatusUi.label}</span>
      </div>
      <p className="mt-2 text-sm text-slate-600">Status integrare Meta Ads pentru agency. OAuth/import/sync real vor fi activate în taskurile următoare.</p>
      {metaLoading ? <p className="mt-3 text-xs text-slate-500">Se încarcă statusul Meta Ads...</p> : null}
      {!metaLoading ? <p className="mt-3 text-xs text-slate-600">{metaStatus?.message || "Status Meta Ads indisponibil momentan."}</p> : null}
      {metaStatusError ? <p className="mt-2 text-xs text-red-600">{metaStatusError}</p> : null}
      {metaConnectError ? <p className="mt-2 text-xs text-red-600">{metaConnectError}</p> : null}
      {metaImportError ? <p className="mt-2 text-xs text-red-600">{metaImportError}</p> : null}

      {!metaLoading && metaStatus ? (
        <div className="mt-3 space-y-1 text-xs text-slate-500">
          {typeof metaStatus.provider === "string" && metaStatus.provider.trim() ? <p>Provider: {metaStatus.provider}</p> : null}
          {typeof metaStatus.status === "string" && metaStatus.status.trim() ? <p>Status raw: {metaStatus.status}</p> : null}
          <p>Sursă token: {String(metaStatus.token_source || "missing")}</p>
          <p>Actualizat la: {formatDate(metaStatus.token_updated_at)}</p>
          <p>Expirare token: {formatDate(metaStatus.token_expires_at)}</p>
        </div>
      ) : null}

      {!metaLoading && !metaOauthConfigured ? (
        <p className="mt-3 text-xs text-amber-700">Meta OAuth nu este configurat complet în backend (META_APP_ID/META_APP_SECRET/META_REDIRECT_URI).</p>
      ) : null}
      {!metaLoading && !metaHasUsableToken ? <p className="mt-2 text-xs text-amber-700">Importul conturilor Meta necesită un token activ (database sau env fallback).</p> : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          onClick={() => void connectMetaAds()}
          disabled={metaBusy !== null || metaLoading || !metaOauthConfigured}
          className="wm-btn-primary disabled:opacity-50"
        >
          {metaBusy === "connect" ? "Connecting..." : "Connect Meta Ads"}
        </button>
        <button
          onClick={() => void importMetaAccounts()}
          disabled={metaBusy !== null || metaLoading || !metaHasUsableToken}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {metaBusy === "import" ? "Importing..." : "Import Accounts"}
        </button>
      </div>

      {metaImportResult ? (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
          <p className="font-medium text-slate-800">Ultimul import Meta</p>
          <p className="mt-1">{metaImportResult.message || "Import Meta finalizat."}</p>
          <p className="mt-1">
            Descoperite: {metaImportResult.accounts_discovered ?? 0} · Imported: {metaImportResult.imported ?? 0} · Updated: {metaImportResult.updated ?? 0} · Unchanged: {metaImportResult.unchanged ?? 0}
          </p>
          {metaImportResult.token_source ? <p className="mt-1">Token source: {metaImportResult.token_source}</p> : null}
        </div>
      ) : null}
    </article>
  );
}
