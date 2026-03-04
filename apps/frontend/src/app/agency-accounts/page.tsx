"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientRecord = {
  id: number;
  name: string;
  owner_email: string;
  google_customer_id?: string | null;
  display_id?: number;
};

type ClientsResponse = { items: ClientRecord[] };

type AccountSummaryItem = {
  platform: string;
  connected_count: number;
  last_import_at?: string | null;
};

type AccountSummaryResponse = { items: AccountSummaryItem[] };

type GoogleAccount = {
  id: string;
  name: string;
  attached_client_id?: number | null;
  attached_client_name?: string | null;
  sync_start_date?: string | null;
  last_synced_at?: string | null;
  rolling_synced_through?: string | null;
  last_error?: string | null;
};

type GoogleAccountsResponse = {
  items: GoogleAccount[];
  count: number;
  last_import_at?: string | null;
};

type BatchRun = {
  account_id?: string | null;
  status?: string | null;
};

type BatchProgress = {
  total_runs: number;
  queued: number;
  running: number;
  done: number;
  error: number;
  percent: number;
};

type BatchStatusResponse = {
  batch_id: string;
  status?: string;
  progress: BatchProgress;
  runs: BatchRun[];
};

type BatchCreateResponse = {
  batch_id?: string;
  invalid_account_ids?: string[];
};

const DEFAULT_HISTORICAL_START = "2024-01-09";

function prettyPlatform(platform: string): string {
  const map: Record<string, string> = {
    google_ads: "Google Ads",
    meta_ads: "Meta Ads",
    tiktok_ads: "TikTok Ads",
    pinterest_ads: "Pinterest Ads",
    snapchat_ads: "Snapchat Ads",
  };
  return map[platform] ?? platform;
}

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function isValidIsoDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function toIsoDateLocal(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function formatRoDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = date.getFullYear();
  return `${day}.${month}.${year}`;
}

function accountDisplayName(account: GoogleAccount): string {
  const clean = account.name?.trim();
  return clean ? clean : `Google Account ${account.id}`;
}

function actionButtonClass(variant: "primary" | "historical" | "ghost"): string {
  const base = "inline-flex items-center rounded-md px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50";
  if (variant === "primary") {
    return `${base} bg-indigo-600 text-white hover:bg-indigo-700`;
  }
  if (variant === "historical") {
    return `${base} bg-emerald-600 text-white hover:bg-emerald-700`;
  }
  return `${base} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50`;
}

export default function AgencyAccountsPage() {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [clients, setClients] = useState<ClientRecord[]>([]);
  const [summary, setSummary] = useState<AccountSummaryItem[]>([]);
  const [googleAccounts, setGoogleAccounts] = useState<GoogleAccount[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState("google_ads");

  const [selectedAccountIds, setSelectedAccountIds] = useState<Set<string>>(new Set());
  const [accountsPage, setAccountsPage] = useState(1);
  const [accountsPageSize, setAccountsPageSize] = useState(50);

  const [actionBusy, setActionBusy] = useState(false);
  const [runningAction, setRunningAction] = useState<"refresh" | "rolling" | "historical" | null>(null);
  const [attachStatus, setAttachStatus] = useState("");
  const [syncError, setSyncError] = useState("");
  const [syncStatusMessage, setSyncStatusMessage] = useState("");

  const [currentBatchId, setCurrentBatchId] = useState<string | null>(null);
  const [currentJobType, setCurrentJobType] = useState<"rolling_refresh" | "historical_backfill" | null>(null);
  const [currentHistoricalStartDate, setCurrentHistoricalStartDate] = useState<string | null>(null);
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null);
  const [batchRunsByAccount, setBatchRunsByAccount] = useState<Record<string, string>>({});

  const selectedSummary = useMemo(
    () => summary.find((item) => item.platform === selectedPlatform),
    [summary, selectedPlatform],
  );

  const totalAccountsPages = useMemo(
    () => Math.max(1, Math.ceil(googleAccounts.length / accountsPageSize)),
    [googleAccounts.length, accountsPageSize],
  );

  const pagedGoogleAccounts = useMemo(() => {
    const start = (accountsPage - 1) * accountsPageSize;
    return googleAccounts.slice(start, start + accountsPageSize);
  }, [googleAccounts, accountsPage, accountsPageSize]);

  const selectablePageAccountIds = useMemo(
    () => pagedGoogleAccounts.filter((item) => Boolean(item.attached_client_id)).map((item) => item.id),
    [pagedGoogleAccounts],
  );

  const allSelectableOnPageSelected =
    selectablePageAccountIds.length > 0 && selectablePageAccountIds.every((id) => selectedAccountIds.has(id));

  const selectedMappedAccounts = useMemo(
    () => googleAccounts.filter((account) => selectedAccountIds.has(account.id) && Boolean(account.attached_client_id)),
    [googleAccounts, selectedAccountIds],
  );

  async function loadData() {
    setLoading(true);
    setLoadError("");
    try {
      const [clientsPayload, summaryPayload, googlePayload] = await Promise.all([
        apiRequest<ClientsResponse>("/clients"),
        apiRequest<AccountSummaryResponse>("/clients/accounts/summary"),
        apiRequest<GoogleAccountsResponse>("/clients/accounts/google"),
      ]);
      setClients(clientsPayload.items ?? []);
      setSummary(summaryPayload.items ?? []);
      setGoogleAccounts(googlePayload.items ?? []);
    } catch (err) {
      setClients([]);
      setSummary([]);
      setGoogleAccounts([]);
      setLoadError(err instanceof Error ? err.message : "Nu am putut încărca datele Agency Accounts.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  useEffect(() => {
    setSelectedAccountIds(new Set());
    setAccountsPage(1);
  }, [selectedPlatform]);

  useEffect(() => {
    setAccountsPage(1);
  }, [accountsPageSize]);

  useEffect(() => {
    if (accountsPage > totalAccountsPages) {
      setAccountsPage(totalAccountsPages);
    }
  }, [accountsPage, totalAccountsPages]);

  function toggleAccountSelection(accountId: string, checked: boolean) {
    setSelectedAccountIds((current) => {
      const next = new Set(current);
      if (checked) next.add(accountId);
      else next.delete(accountId);
      return next;
    });
  }

  function toggleSelectAllOnPage(checked: boolean) {
    setSelectedAccountIds((current) => {
      const next = new Set(current);
      selectablePageAccountIds.forEach((accountId) => {
        if (checked) next.add(accountId);
        else next.delete(accountId);
      });
      return next;
    });
  }

  async function attachGoogleAccount(clientId: number, customerId: string) {
    setAttachStatus("");
    setActionBusy(true);
    try {
      await apiRequest(`/clients/${clientId}/attach-google-account`, {
        method: "POST",
        body: JSON.stringify({ customer_id: customerId }),
      });
      const targetClient = clients.find((item) => item.id === clientId);
      setAttachStatus(`Contul ${customerId} a fost atașat clientului ${targetClient?.name ?? `#${clientId}`}.`);
      await loadData();
    } catch (err) {
      setAttachStatus(err instanceof Error ? err.message : "Nu am putut atașa contul Google.");
    } finally {
      setActionBusy(false);
    }
  }

  async function detachGoogleAccount(clientId: number, customerId: string) {
    setAttachStatus("");
    setActionBusy(true);
    try {
      await apiRequest(`/clients/${clientId}/detach-google-account`, {
        method: "DELETE",
        body: JSON.stringify({ customer_id: customerId }),
      });
      const targetClient = clients.find((item) => item.id === clientId);
      setAttachStatus(`Contul ${customerId} a fost detașat de la clientul ${targetClient?.name ?? `#${clientId}`}.`);
      setSelectedAccountIds((current) => {
        const next = new Set(current);
        next.delete(customerId);
        return next;
      });
      await loadData();
    } catch (err) {
      setAttachStatus(err instanceof Error ? err.message : "Nu am putut detașa contul Google.");
    } finally {
      setActionBusy(false);
    }
  }

  async function refreshGoogleAccountNames() {
    setAttachStatus("");
    setActionBusy(true);
    setRunningAction("refresh");
    try {
      const payload = await apiRequest<{ refreshed_count: number }>("/integrations/google-ads/refresh-account-names", {
        method: "POST",
      });
      setAttachStatus(`Au fost actualizate ${payload.refreshed_count} conturi Google.`);
      await loadData();
    } catch (err) {
      setAttachStatus(err instanceof Error ? err.message : "Nu am putut actualiza numele conturilor Google.");
    } finally {
      setActionBusy(false);
      setRunningAction(null);
    }
  }

  async function startBatchSync(mode: "rolling" | "historical") {
    if (selectedMappedAccounts.length <= 0) {
      setSyncError("Selectează cel puțin un cont atașat la client.");
      return;
    }

    setSyncError("");
    setSyncStatusMessage("");
    setBatchProgress(null);
    setBatchRunsByAccount({});

    const body: Record<string, unknown> = {
      platform: "google_ads",
      account_ids: selectedMappedAccounts.map((item) => item.id),
      chunk_days: 7,
      grain: "account_daily",
    };

    let historicalStartDateUsed: string | null = null;
    if (mode === "rolling") {
      body.job_type = "rolling_refresh";
      body.days = 7;
      setCurrentJobType("rolling_refresh");
      setCurrentHistoricalStartDate(null);
    } else {
      body.job_type = "historical_backfill";
      const validStarts = selectedMappedAccounts
        .map((item) => item.sync_start_date?.trim() ?? "")
        .filter((dateValue) => isValidIsoDate(dateValue))
        .sort();
      historicalStartDateUsed = validStarts[0] ?? DEFAULT_HISTORICAL_START;
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      body.start_date = historicalStartDateUsed;
      body.end_date = toIsoDateLocal(yesterday);
      setCurrentJobType("historical_backfill");
      setCurrentHistoricalStartDate(historicalStartDateUsed);
    }

    setActionBusy(true);
    setRunningAction(mode);
    try {
      const payload = await apiRequest<BatchCreateResponse>("/agency/sync-runs/batch", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!payload.batch_id) throw new Error("Batch-ul nu a putut fi creat.");
      setCurrentBatchId(payload.batch_id);

      if ((payload.invalid_account_ids ?? []).length > 0) {
        setSyncStatusMessage(`Unele conturi au fost ignorate: ${(payload.invalid_account_ids ?? []).join(", ")}`);
      }

      if (mode === "historical") {
        setCurrentHistoricalStartDate(historicalStartDateUsed);
      }
    } catch (err) {
      setCurrentBatchId(null);
      setSyncError(err instanceof Error ? err.message : "Nu am putut porni sync-ul batch.");
      setRunningAction(null);
    } finally {
      setActionBusy(false);
    }
  }

  useEffect(() => {
    if (!currentBatchId) return;
    let cancelled = false;

    async function pollBatch() {
      try {
        const payload = await apiRequest<BatchStatusResponse>(`/agency/sync-runs/batch/${currentBatchId}`);
        if (cancelled) return;
        setBatchProgress(payload.progress);

        const byAccount: Record<string, string> = {};
        for (const run of payload.runs ?? []) {
          if (run.account_id) byAccount[run.account_id] = String(run.status ?? "queued");
        }
        setBatchRunsByAccount(byAccount);

        const activeCount = Number(payload.progress.queued || 0) + Number(payload.progress.running || 0);
        if (activeCount <= 0) {
          setCurrentBatchId(null);
          setRunningAction(null);
          if (Number(payload.progress.error || 0) > 0) {
            setSyncStatusMessage(`Sync finalizat cu erori: ${payload.progress.error} conturi`);
          } else if (currentJobType === "historical_backfill" && currentHistoricalStartDate) {
            setSyncStatusMessage(`Date istorice descarcate începând cu ${formatRoDate(currentHistoricalStartDate)}`);
          } else {
            setSyncStatusMessage("Sync last 7 days finalizat cu succes.");
          }
          void loadData();
        }
      } catch (err) {
        if (cancelled) return;
        setCurrentBatchId(null);
        setRunningAction(null);
        setSyncError(err instanceof Error ? err.message : "Polling batch eșuat.");
      }
    }

    void pollBatch();
    const intervalId = window.setInterval(() => {
      void pollBatch();
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [currentBatchId, currentHistoricalStartDate, currentJobType]);

  const isBatchActive = Boolean(currentBatchId);
  const controlsDisabled = loading || actionBusy || isBatchActive;

  return (
    <ProtectedPage>
      <AppShell title="Agency Accounts">
        <main className="p-6">
          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Agency Accounts</h2>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
              {summary.map((item) => {
                const active = item.platform === selectedPlatform;
                return (
                  <button
                    key={item.platform}
                    type="button"
                    onClick={() => setSelectedPlatform(item.platform)}
                    className={`wm-card p-4 text-left transition ${active ? "ring-2 ring-indigo-500" : "hover:bg-slate-50"}`}
                  >
                    <p className="text-sm font-semibold text-slate-900">{prettyPlatform(item.platform)}</p>
                    <p className="mt-1 text-xs text-slate-500">Conturi conectate: {item.connected_count}</p>
                    <p className="mt-1 text-xs text-slate-500">Ultimul import: {formatDateTime(item.last_import_at)}</p>
                  </button>
                );
              })}
            </div>

            {selectedPlatform !== "google_ads" ? (
              <div className="mt-4 wm-card p-4 text-sm text-slate-500">
                Pentru acest task, doar Google Ads este funcțional complet. Celelalte platforme rămân informative.
              </div>
            ) : (
              <div className="mt-4 wm-card p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm text-slate-600">
                    Total Google Accounts: <span className="font-semibold text-slate-900">{googleAccounts.length}</span>
                    {selectedSummary ? ` · Conectate: ${selectedSummary.connected_count}` : ""}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className={actionButtonClass("ghost")}
                      onClick={() => void refreshGoogleAccountNames()}
                      disabled={controlsDisabled}
                    >
                      {runningAction === "refresh" ? "Refreshing..." : "Refresh names"}
                    </button>
                    <button
                      type="button"
                      className={actionButtonClass("primary")}
                      onClick={() => void startBatchSync("rolling")}
                      disabled={controlsDisabled || selectedMappedAccounts.length === 0}
                    >
                      {runningAction === "rolling" || isBatchActive ? "Syncing..." : "Sync last 7 days"}
                    </button>
                    <button
                      type="button"
                      className={actionButtonClass("historical")}
                      onClick={() => void startBatchSync("historical")}
                      disabled={controlsDisabled || selectedMappedAccounts.length === 0}
                    >
                      {runningAction === "historical" || isBatchActive ? "Downloading..." : "Download historical"}
                    </button>
                  </div>
                </div>

                <div className="mt-2 text-xs text-slate-600">
                  Selectate: <span className="font-semibold text-slate-900">{selectedAccountIds.size}</span> conturi
                  {selectedMappedAccounts.length !== selectedAccountIds.size ? ` (${selectedMappedAccounts.length} eligibile pentru sync)` : ""}
                </div>

                {isBatchActive && batchProgress ? (
                  <div className="mt-3 rounded-md border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
                    <p className="font-medium">Batch în progres ({batchProgress.percent.toFixed(0)}%)</p>
                    <p className="mt-1 text-xs">
                      {batchProgress.done}/{batchProgress.total_runs} done · {batchProgress.running} running · {batchProgress.queued} queued · {batchProgress.error} errors
                    </p>
                    <div className="mt-2 h-2 w-full overflow-hidden rounded bg-indigo-100">
                      <div className="h-full bg-indigo-600 transition-all" style={{ width: `${Math.max(0, Math.min(100, Number(batchProgress.percent || 0)))}%` }} />
                    </div>
                  </div>
                ) : null}

                {loading ? <p className="mt-3 text-sm text-slate-500">Se încarcă conturile...</p> : null}
                {!loading && googleAccounts.length === 0 ? <p className="mt-3 text-sm text-slate-500">Nu există conturi Google importate.</p> : null}
                {loadError ? <p className="mt-3 text-sm text-red-600">{loadError}</p> : null}
                {syncError ? <p className="mt-2 text-sm text-red-600">{syncError}</p> : null}
                {attachStatus ? <p className="mt-2 text-sm text-emerald-700">{attachStatus}</p> : null}
                {syncStatusMessage ? <p className="mt-2 text-sm text-indigo-700">{syncStatusMessage}</p> : null}

                {!loading && googleAccounts.length > 0 ? (
                  <div className="mt-3 overflow-hidden rounded-md border border-slate-200">
                    <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={allSelectableOnPageSelected}
                          onChange={(event) => toggleSelectAllOnPage(event.target.checked)}
                          disabled={selectablePageAccountIds.length === 0 || controlsDisabled}
                        />
                        Select all pe pagina curentă
                      </label>
                      <span>Pagina {accountsPage}/{totalAccountsPages}</span>
                    </div>

                    <div className="divide-y divide-slate-100">
                      {pagedGoogleAccounts.map((account) => {
                        const attached = Boolean(account.attached_client_id);
                        const selected = selectedAccountIds.has(account.id);
                        const rowStatus = batchRunsByAccount[account.id];

                        return (
                          <div key={account.id} className="flex flex-wrap items-center justify-between gap-3 px-3 py-3">
                            <div className="flex min-w-0 items-start gap-3">
                              <input
                                type="checkbox"
                                checked={selected}
                                disabled={!attached || controlsDisabled}
                                onChange={(event) => toggleAccountSelection(account.id, event.target.checked)}
                              />
                              <div className="min-w-0">
                                <p className="truncate text-sm font-medium text-slate-900">
                                  <Link href={`/agency-accounts/google_ads/${encodeURIComponent(account.id)}`} className="hover:underline">
                                    {accountDisplayName(account)}
                                  </Link>
                                </p>
                                <p className="text-xs text-slate-500">ID: {account.id}</p>
                                <p className={`text-xs ${attached ? "text-emerald-700" : "text-amber-700"}`}>
                                  {attached ? `Atașat la: ${account.attached_client_name}` : "Neatașat la client (nu poate fi selectat)"}
                                </p>
                                <p className="text-xs text-slate-500">
                                  Last synced: {formatDateTime(account.last_synced_at)} · Rolling through: {formatDateTime(account.rolling_synced_through)}
                                </p>
                                {account.last_error ? <p className="text-xs text-red-600">Last error: {account.last_error}</p> : null}
                                {rowStatus ? <p className="text-xs text-indigo-700">Batch status: {rowStatus}</p> : null}
                              </div>
                            </div>

                            <div className="flex items-center gap-2">
                              <select
                                className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                                value={account.attached_client_id?.toString() ?? ""}
                                onChange={(event) => {
                                  const value = Number(event.target.value);
                                  if (value > 0) void attachGoogleAccount(value, account.id);
                                }}
                                disabled={controlsDisabled}
                              >
                                <option value="">Atașează la client...</option>
                                {clients.map((client) => (
                                  <option key={client.id} value={client.id}>#{client.display_id ?? client.id} {client.name}</option>
                                ))}
                              </select>

                              {account.attached_client_id ? (
                                <button
                                  type="button"
                                  className="inline-flex items-center rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                                  onClick={() => void detachGoogleAccount(account.attached_client_id ?? 0, account.id)}
                                  disabled={controlsDisabled}
                                >
                                  Detach
                                </button>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    <div className="flex flex-col gap-2 border-t border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 md:flex-row md:items-center md:justify-between">
                      <p>Afișare {(accountsPage - 1) * accountsPageSize + 1}-{Math.min(accountsPage * accountsPageSize, googleAccounts.length)} din {googleAccounts.length}</p>
                      <div className="flex items-center gap-2">
                        <span>Rânduri/pagină</span>
                        <select
                          className="rounded-md border border-slate-300 px-2 py-1"
                          value={accountsPageSize}
                          onChange={(event) => setAccountsPageSize(Number(event.target.value))}
                          disabled={controlsDisabled}
                        >
                          {[25, 50, 100, 200].map((size) => (<option key={size} value={size}>{size}</option>))}
                        </select>
                        <button
                          type="button"
                          className="rounded border border-slate-300 px-2 py-1 disabled:opacity-50"
                          disabled={accountsPage <= 1 || controlsDisabled}
                          onClick={() => setAccountsPage((current) => Math.max(1, current - 1))}
                        >
                          Anterior
                        </button>
                        <button
                          type="button"
                          className="rounded border border-slate-300 px-2 py-1 disabled:opacity-50"
                          disabled={accountsPage >= totalAccountsPages || controlsDisabled}
                          onClick={() => setAccountsPage((current) => Math.min(totalAccountsPages, current + 1))}
                        >
                          Următor
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
