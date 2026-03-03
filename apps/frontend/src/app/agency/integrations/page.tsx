"use client";

import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

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
  [key: string]: unknown;
};

function formatDate(value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
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

  async function loadGoogleStatus() {
    try {
      const payload = await apiRequest<GoogleStatusResponse>("/integrations/google-ads/status");
      setGoogleStatus(payload);
    } catch {
      // no-op
    }
  }

  useEffect(() => {
    void loadGoogleStatus();
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
  const warnings = useMemo(() => (Array.isArray(diagnosticsData?.warnings) ? diagnosticsData?.warnings : []), [diagnosticsData]);

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
