"use client";

import React, { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

import { MetaIntegrationCard } from "./MetaIntegrationCard";

type GoogleConnectResponse = {
  authorize_url: string;
  state: string;
};

type GoogleImportResponse = {
  status: string;
  imported_count: number;
  accessible_customers: string[];
  last_import_at?: string;
};

type GoogleStatusResponse = {
  status: string;
  message: string;
  mode: string;
  connected_accounts_count?: number;
  last_import_at?: string;
};

type GoogleDiagnosticsResponse = {
  oauth_ok?: boolean;
  developer_token_ok?: boolean;
  api_version?: string;
  warnings?: string[];
  last_error?: string | null;
  refresh_token_present?: boolean;
  refresh_token_source?: string;
  [key: string]: unknown;
};

type MetaStatusResponse = {
  provider?: string;
  status?: string;
  message?: string;
  [key: string]: unknown;
};

type MetaConnectResponse = {
  authorize_url: string;
  state: string;
};

type MetaImportResponse = {
  status: string;
  imported_count: number;
  accessible_accounts: string[];
  last_import_at?: string;
};

type IntegrationStatusUi = {
  toneClass: string;
  label: string;
};

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
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

export default function AgencyIntegrationsPage() {
  const [googleMessage, setGoogleMessage] = useState("");
  const [googleError, setGoogleError] = useState("");
  const [googleStatus, setGoogleStatus] = useState<GoogleStatusResponse | null>(null);
  const [busy, setBusy] = useState<"connect" | "import" | null>(null);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [diagnosticsBusy, setDiagnosticsBusy] = useState(false);
  const [diagnosticsError, setDiagnosticsError] = useState("");
  const [diagnosticsData, setDiagnosticsData] = useState<GoogleDiagnosticsResponse | null>(null);
  const [copyMessage, setCopyMessage] = useState("");
  const [metaStatus, setMetaStatus] = useState<MetaStatusResponse | null>(null);
  const [metaLoading, setMetaLoading] = useState(true);
  const [metaStatusError, setMetaStatusError] = useState("");
  const [metaConnectError, setMetaConnectError] = useState("");
  const [metaImportError, setMetaImportError] = useState("");
  const [metaImportResult, setMetaImportResult] = useState<MetaImportResponse | null>(null);
  const [metaBusy, setMetaBusy] = useState<"connect" | "import" | null>(null);

  async function loadGoogleStatus() {
    try {
      const payload = await apiRequest<GoogleStatusResponse>("/integrations/google-ads/status");
      setGoogleStatus(payload);
    } catch {
      // no-op
    }
  }

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
    void loadGoogleStatus();
    void loadMetaStatus();
  }, []);

  async function connectGoogle() {
    setGoogleError("");
    setGoogleMessage("");
    setBusy("connect");
    try {
      const payload = await apiRequest<GoogleConnectResponse>("/integrations/google-ads/connect");
      setGoogleMessage("Redirecting către Google OAuth...");
      window.location.href = payload.authorize_url;
    } catch (err) {
      setGoogleError(err instanceof Error ? err.message : "Nu am putut iniția Google OAuth");
    } finally {
      setBusy(null);
    }
  }

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

  async function importGoogleAccounts() {
    setGoogleError("");
    setGoogleMessage("");
    setBusy("import");
    try {
      const payload = await apiRequest<GoogleImportResponse>("/integrations/google-ads/import-accounts", { method: "POST" });
      setGoogleMessage(
        `Import complet: ${payload.imported_count} clienți creați din ${payload.accessible_customers.length} conturi accesibile. Ultimul import: ${formatDate(payload.last_import_at)}.`
      );
      await loadGoogleStatus();
    } catch (err) {
      setGoogleError(err instanceof Error ? err.message : "Nu am putut importa conturile Google");
    } finally {
      setBusy(null);
    }
  }

  async function loadDiagnostics() {
    setCopyMessage("");
    setDiagnosticsError("");
    setDiagnosticsBusy(true);
    try {
      const payload = await apiRequest<GoogleDiagnosticsResponse>("/integrations/google-ads/diagnostics");
      setDiagnosticsData(payload);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Nu am putut încărca diagnosticele Google Ads";
      setDiagnosticsError(message);
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

  const isConnected = googleStatus?.status === "connected";

  const metaStatusUi = metaStatusError
    ? { label: "Eroare", toneClass: "bg-red-100 text-red-700" }
    : normalizeIntegrationStatus(metaStatus?.status);

  const warnings = useMemo(() => (Array.isArray(diagnosticsData?.warnings) ? diagnosticsData?.warnings : []), [diagnosticsData]);
  
  const metaOauthConfigured = Boolean(metaStatus?.oauth_configured);
  
  const metaHasUsableToken = Boolean(metaStatus?.has_usable_token);
  
  return (
    <ProtectedPage>
      <AppShell title="Agency Integrations">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <article className="wm-card p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900">Google Ads (Production Ready)</h2>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${isConnected ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                {isConnected ? "Conectat" : "Neconectat"}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              Conectează MCC-ul real prin OAuth și importă automat conturile Google Ads în registry-ul local.
            </p>
            <p className="mt-2 text-xs text-slate-500">Conturi conectate: {googleStatus?.connected_accounts_count ?? 0}</p>
            <p className="mt-1 text-xs text-slate-500">Ultimul import: {formatDate(googleStatus?.last_import_at)}</p>
            {googleError ? <p className="mt-3 text-xs text-red-600">{googleError}</p> : null}
            {googleMessage ? <p className="mt-3 text-xs text-emerald-600">{googleMessage}</p> : null}
            <div className="mt-4 flex flex-wrap gap-2">
              <button onClick={() => void connectGoogle()} disabled={busy !== null} className="wm-btn-primary disabled:opacity-50">
                {busy === "connect" ? "Connecting..." : "Connect Google"}
              </button>
              <button
                onClick={() => void importGoogleAccounts()}
                disabled={busy !== null}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
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
            <p className="mt-3 text-xs text-slate-500">
              După import, rulează sync pe fiecare sub-account pentru a popula dashboard-ul cu date reale.
            </p>
          </article>

          <MetaIntegrationCard />

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
                <p>Actualizat la: {formatDate(String(metaStatus.token_updated_at || ""))}</p>
                <p>Expirare token: {formatDate(String(metaStatus.token_expires_at || ""))}</p>
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

          <article className="wm-card p-4">
            <h2 className="text-base font-semibold text-slate-900">TikTok Ads (stabilized)</h2>
            <p className="mt-2 text-sm text-slate-600">Integrarea TikTok este activă pentru sync și vizibilitate în dashboard.</p>
          </article>

          <article className="wm-card p-4">
            <h2 className="text-base font-semibold text-slate-900">Pinterest Ads</h2>
            <p className="mt-2 text-sm text-slate-600">Integrarea Pinterest este activă pentru sync și monitorizare în Agency View.</p>
            <p className="mt-3 text-xs text-slate-500">Status și sync disponibile. Datele apar în dashboard după prima sincronizare.</p>
          </article>

          <article className="wm-card p-4">
            <h2 className="text-base font-semibold text-slate-900">Snapchat Ads</h2>
            <p className="mt-2 text-sm text-slate-600">Integrarea Snapchat este activă pentru sync și monitorizare în Agency View.</p>
            <p className="mt-3 text-xs text-slate-500">Status și sync disponibile. Datele apar în dashboard după prima sincronizare.</p>
          </article>
        </div>

        {diagnosticsOpen ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4" role="dialog" aria-modal="true">
            <div className="wm-card max-h-[90vh] w-full max-w-3xl overflow-y-auto p-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-slate-900">Google Ads Diagnostics</h3>
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
                      <span className="font-medium">developer_token_ok:</span> {String(Boolean(diagnosticsData.developer_token_ok))}
                    </p>
                    <p>
                      <span className="font-medium">api_version:</span> {diagnosticsData.api_version ?? "-"}
                    </p>
                    <p>
                      <span className="font-medium">refresh_token_present:</span> {String(Boolean(diagnosticsData.refresh_token_present))}
                    </p>
                    <p>
                      <span className="font-medium">refresh_token_source:</span> {String(diagnosticsData.refresh_token_source ?? "missing")}
                    </p>
                  </div>

                  <div>
                    <p className="font-medium">warnings</p>
                    {warnings.length > 0 ? (
                      <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-amber-700">
                        {warnings.map((warning, idx) => (
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
      </AppShell>
    </ProtectedPage>
  );
}
