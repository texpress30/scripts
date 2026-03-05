"use client";

import React from "react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest, postAccountSyncProgressBatch, type AccountSyncProgressBatchResult } from "@/lib/api";

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
  platform?: string;
  account_id?: string;
  display_name?: string;
  attached_client_id?: number | null;
  attached_client_name?: string | null;
  timezone?: string | null;
  currency?: string | null;
  sync_start_date?: string | null;
  backfill_completed_through?: string | null;
  rolling_synced_through?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  last_run_status?: string | null;
  last_run_type?: string | null;
  last_run_started_at?: string | null;
  last_run_finished_at?: string | null;
  has_active_sync?: boolean;
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

type RowChunkProgress = {
  chunksDone: number;
  chunksTotal: number;
  percent: number;
  jobType?: string | null;
  status?: string | null;
  dateStart?: string | null;
  dateEnd?: string | null;
};


const DEFAULT_HISTORICAL_START = "2024-01-09";
const _PROGRESS_BATCH_ACCOUNT_IDS_MAX = 200;

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
  const clean = account.display_name?.trim() || account.name?.trim();
  return clean ? clean : `Google Account ${account.id}`;
}

function actionButtonClass(variant: "historical" | "ghost"): string {
  const base = "inline-flex items-center rounded-md px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50";
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
  const [clientFilter, setClientFilter] = useState("");
  const [expandedClientRows, setExpandedClientRows] = useState<Set<string>>(new Set());

  const [actionBusy, setActionBusy] = useState(false);
  const [runningAction, setRunningAction] = useState<"refresh" | "historical" | null>(null);
  const [attachStatus, setAttachStatus] = useState("");
  const [syncError, setSyncError] = useState("");
  const [syncStatusMessage, setSyncStatusMessage] = useState("");

  const [currentBatchId, setCurrentBatchId] = useState<string | null>(null);
  const [currentJobType, setCurrentJobType] = useState<"historical_backfill" | null>(null);
  const [currentHistoricalStartDate, setCurrentHistoricalStartDate] = useState<string | null>(null);
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null);
  const [batchRunsByAccount, setBatchRunsByAccount] = useState<Record<string, string>>({});
  const [rowChunkProgressByAccount, setRowChunkProgressByAccount] = useState<Record<string, RowChunkProgress>>({});

  const selectedSummary = useMemo(
    () => summary.find((item) => item.platform === selectedPlatform),
    [summary, selectedPlatform],
  );


  const filteredGoogleAccounts = useMemo(() => {
    const needle = clientFilter.trim().toLowerCase();
    if (!needle) return googleAccounts;
    return googleAccounts.filter((account) => (account.attached_client_name || "").toLowerCase().includes(needle));
  }, [googleAccounts, clientFilter]);

  const totalAccountsPages = useMemo(
    () => Math.max(1, Math.ceil(filteredGoogleAccounts.length / accountsPageSize)),
    [filteredGoogleAccounts.length, accountsPageSize],
  );

  const pagedGoogleAccounts = useMemo(() => {
    const start = (accountsPage - 1) * accountsPageSize;
    return filteredGoogleAccounts.slice(start, start + accountsPageSize);
  }, [filteredGoogleAccounts, accountsPage, accountsPageSize]);

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

  const accountsByClient = useMemo(() => {
    const grouped = new Map<number, GoogleAccount[]>();
    for (const account of googleAccounts) {
      if (!account.attached_client_id) continue;
      const current = grouped.get(account.attached_client_id) ?? [];
      current.push(account);
      grouped.set(account.attached_client_id, current);
    }
    return grouped;
  }, [googleAccounts]);

  const activeSyncAccountIds = useMemo(() => {
    return googleAccounts
      .filter((account) => {
        const rowStatus = String(batchRunsByAccount[account.id] ?? "").toLowerCase();
        if (rowStatus === "queued" || rowStatus === "running" || rowStatus === "pending") return true;
        return !rowStatus && Boolean(account.has_active_sync);
      })
      .map((account) => account.id);
  }, [googleAccounts, batchRunsByAccount]);

  function toggleClientQuickView(accountId: string, open: boolean) {
    setExpandedClientRows((current) => {
      const next = new Set(current);
      if (open) next.add(accountId);
      else next.delete(accountId);
      return next;
    });
  }

  function renderRollingCoverage(account: GoogleAccount, chunkProgress?: RowChunkProgress | null): string {
    const normalizedStatus = String(chunkProgress?.status ?? "").toLowerCase();
    const normalizedJobType = String(chunkProgress?.jobType ?? "").toLowerCase();
    const hasActiveRollingRun =
      normalizedJobType === "rolling_refresh" && (normalizedStatus === "queued" || normalizedStatus === "running" || normalizedStatus === "pending");

    if (hasActiveRollingRun) {
      if (chunkProgress?.dateStart && chunkProgress?.dateEnd) {
        return `Rolling în curs: ${chunkProgress.dateStart} → ${chunkProgress.dateEnd}`;
      }
      if (chunkProgress?.dateEnd) {
        return `Rolling în curs până la: ${chunkProgress.dateEnd}`;
      }
      return "Rolling în curs";
    }

    return account.rolling_synced_through ?? "Rolling sync neinițiat";
  }

  function renderSyncProgress(
    account: GoogleAccount,
    rowStatus?: string | null,
    chunkProgress?: RowChunkProgress | null,
  ): JSX.Element {
    const normalizedRowStatus = String(rowStatus ?? "").toLowerCase();
    const isBatchActiveRow = normalizedRowStatus === "queued" || normalizedRowStatus === "running" || normalizedRowStatus === "pending";
    const hasStandaloneActiveSync = !rowStatus && Boolean(account.has_active_sync);
    const isActiveSyncRow = isBatchActiveRow || hasStandaloneActiveSync;

    const statusText = rowStatus || account.last_run_status || (account.has_active_sync ? "running" : "idle");
    const normalizedStatusText = String(statusText).toLowerCase();

    const fallbackPercent = normalizedRowStatus === "queued" ? 14 : 52;

    return (
      <div className="w-full">
        <p className="text-xs font-medium text-slate-700">Status: {statusText}</p>
        <div className="mt-1 h-2 w-full overflow-hidden rounded bg-slate-200" data-testid={`sync-progress-track-${account.id}`}>
          {isActiveSyncRow ? (
            <div
              className={`h-full bg-indigo-500 ${normalizedStatusText === "running" ? "animate-pulse" : ""}`}
              style={{ width: `${Math.max(6, Math.min(100, chunkProgress && chunkProgress.chunksTotal > 0 ? chunkProgress.percent : fallbackPercent))}%` }}
              data-testid={`sync-progress-fill-${account.id}`}
            />
          ) : null}
        </div>
        {chunkProgress && chunkProgress.chunksTotal > 0 ? (
          <p className="mt-1 text-xs text-slate-600" data-testid={`sync-progress-chunks-${account.id}`}>
            {chunkProgress.chunksDone}/{chunkProgress.chunksTotal} chunks ({chunkProgress.percent}%)
          </p>
        ) : isActiveSyncRow ? (
          <p className="mt-1 text-xs text-slate-500">Chunk progress în curs de actualizare...</p>
        ) : null}
        {account.last_run_type ? <p className="mt-1 text-xs text-slate-500">Tip run: {account.last_run_type}</p> : null}
        {rowStatus ? <p className="mt-1 text-xs text-indigo-700">Batch status: {rowStatus}</p> : null}
      </div>
    );
  }

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
    setExpandedClientRows(new Set());
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

  useEffect(() => {
    setExpandedClientRows((current) => {
      const visibleIds = new Set(filteredGoogleAccounts.map((account) => account.id));
      const next = new Set(Array.from(current).filter((id) => visibleIds.has(id)));
      if (next.size === current.size) return current;
      return next;
    });
  }, [filteredGoogleAccounts]);

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

  async function startBatchSyncHistorical() {
    if (selectedMappedAccounts.length <= 0) {
      setSyncError("Selectează cel puțin un cont atașat la client.");
      return;
    }

    setSyncError("");
    setSyncStatusMessage("");
    setBatchProgress(null);
    setBatchRunsByAccount({});

    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const historicalStartDateUsed = DEFAULT_HISTORICAL_START;

    const body: Record<string, unknown> = {
      platform: "google_ads",
      account_ids: selectedMappedAccounts.map((item) => item.id),
      chunk_days: 7,
      grain: "account_daily",
      job_type: "historical_backfill",
      start_date: historicalStartDateUsed,
      end_date: toIsoDateLocal(yesterday),
    };

    setActionBusy(true);
    setRunningAction("historical");
    setCurrentJobType("historical_backfill");
    setCurrentHistoricalStartDate(historicalStartDateUsed);
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
    } catch (err) {
      setCurrentBatchId(null);
      setRunningAction(null);
      setSyncError(err instanceof Error ? err.message : "Nu am putut porni backfill-ul istoric.");
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


  useEffect(() => {
    if (selectedPlatform !== "google_ads" || activeSyncAccountIds.length <= 0) {
      setRowChunkProgressByAccount({});
      return;
    }

    let cancelled = false;

    async function refreshActiveRunsProgress() {
      try {
        const chunks: string[][] = [];
        for (let index = 0; index < activeSyncAccountIds.length; index += _PROGRESS_BATCH_ACCOUNT_IDS_MAX) {
          chunks.push(activeSyncAccountIds.slice(index, index + _PROGRESS_BATCH_ACCOUNT_IDS_MAX));
        }

        const batchResponses = await Promise.all(
          chunks.map((accountIdsChunk) => postAccountSyncProgressBatch("google_ads", accountIdsChunk, true)),
        );

        if (cancelled) return;

        const mergedResults: AccountSyncProgressBatchResult[] = [];
        for (const response of batchResponses) {
          mergedResults.push(...(response.results ?? []));
        }

        const next: Record<string, RowChunkProgress> = {};
        for (const item of mergedResults) {
          const accountId = String(item.account_id || "");
          if (!accountId || !item.active_run) continue;

          const done = Math.max(0, Number(item.active_run.chunks_done ?? 0));
          const total = Math.max(0, Number(item.active_run.chunks_total ?? 0));
          next[accountId] = {
            chunksDone: done,
            chunksTotal: total,
            percent: total > 0 ? Math.max(0, Math.min(100, Math.round((done / total) * 100))) : 0,
            jobType: item.active_run.job_type ?? null,
            status: item.active_run.status ?? null,
            dateStart: item.active_run.date_start ?? null,
            dateEnd: item.active_run.date_end ?? null,
          } satisfies RowChunkProgress;
        }

        setRowChunkProgressByAccount(next);
      } catch {
        if (cancelled) return;
      }
    }

    void refreshActiveRunsProgress();
    const intervalId = window.setInterval(() => {
      void refreshActiveRunsProgress();
    }, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [activeSyncAccountIds, selectedPlatform]);

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
                      className={actionButtonClass("historical")}
                      onClick={() => void startBatchSyncHistorical()}
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
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={allSelectableOnPageSelected}
                          onChange={(event) => toggleSelectAllOnPage(event.target.checked)}
                          disabled={selectablePageAccountIds.length === 0 || controlsDisabled}
                        />
                        Select all pe pagina curentă
                      </label>
                      <div className="flex items-center gap-2">
                        <label htmlFor="client-filter" className="text-xs font-medium text-slate-600">Filtru client</label>
                        <input
                          id="client-filter"
                          value={clientFilter}
                          onChange={(event) => setClientFilter(event.target.value)}
                          placeholder="Caută după numele clientului"
                          className="w-56 rounded-md border border-slate-300 px-2 py-1 text-xs"
                        />
                        <span>Pagina {accountsPage}/{totalAccountsPages}</span>
                      </div>
                    </div>

                    <div className="hidden grid-cols-[48px_minmax(220px,2fr)_minmax(180px,1.2fr)_minmax(180px,1.2fr)_minmax(220px,1.4fr)_110px] gap-3 border-b border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 lg:grid">
                      <span>Selecție</span>
                      <span>Cont</span>
                      <span>Sync progress</span>
                      <span>Client atașat</span>
                      <span>Acțiuni</span>
                      <span>Detach</span>
                    </div>

                    <div className="divide-y divide-slate-100">
                      {pagedGoogleAccounts.map((account) => {
                        const attached = Boolean(account.attached_client_id);
                        const selected = selectedAccountIds.has(account.id);
                        const rowStatus = batchRunsByAccount[account.id];

                        return (
                          <div key={account.id} className="grid gap-3 px-3 py-3 lg:grid-cols-[48px_minmax(220px,2fr)_minmax(180px,1.2fr)_minmax(180px,1.2fr)_minmax(220px,1.4fr)_110px] lg:items-start">
                            <div className="flex items-start justify-between lg:justify-center">
                              <span className="text-xs font-semibold uppercase text-slate-500 lg:hidden">Selecție</span>
                              <input
                                type="checkbox"
                                checked={selected}
                                disabled={!attached || controlsDisabled}
                                onChange={(event) => toggleAccountSelection(account.id, event.target.checked)}
                              />
                            </div>

                            <div className="min-w-0">
                              <p className="text-xs font-semibold uppercase text-slate-500 lg:hidden">Cont</p>
                              <p className="truncate text-sm font-medium text-slate-900">
                                <Link href={`/agency-accounts/google_ads/${encodeURIComponent(account.id)}`} className="hover:underline">
                                  {accountDisplayName(account)}
                                </Link>
                              </p>
                              <p className="text-xs text-slate-500">ID: {account.id}</p>
                              <p className="text-xs text-slate-500">Ultimul sync reușit: {account.last_success_at ? formatDateTime(account.last_success_at) : "Nu există sync finalizat încă"}</p>
                              {account.last_error ? <p className="text-xs text-red-600">Eroare recentă: {account.last_error}</p> : null}
                            </div>

                            <div>
                              <p className="text-xs font-semibold uppercase text-slate-500 lg:hidden">Sync progress</p>
                              {renderSyncProgress(account, rowStatus, rowChunkProgressByAccount[account.id])}
                              <p className="mt-1 text-xs text-slate-500">Istoric până la: {account.backfill_completed_through ?? "Backfill neinițiat"}</p>
                              <p className="text-xs text-slate-500">Rolling până la: {renderRollingCoverage(account, rowChunkProgressByAccount[account.id])}</p>
                            </div>

                            <div>
                              <p className="text-xs font-semibold uppercase text-slate-500 lg:hidden">Client atașat</p>
                              {attached ? (
                                <>
                                  <p className="text-sm font-medium text-emerald-700">{account.attached_client_name}</p>
                                  {account.sync_start_date ? <p className="text-xs text-slate-500">Start istoric: {account.sync_start_date}</p> : null}
                                  <div className="mt-1 flex flex-wrap items-center gap-2">
                                    <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                                      {(accountsByClient.get(account.attached_client_id ?? 0) ?? []).length} conturi atribuite
                                    </span>
                                    <button
                                      type="button"
                                      className="text-xs font-medium text-indigo-700 hover:underline"
                                      onClick={() => toggleClientQuickView(account.id, !expandedClientRows.has(account.id))}
                                    >
                                      {expandedClientRows.has(account.id) ? "Ascunde conturile" : "Vezi conturile"}
                                    </button>
                                  </div>
                                  {expandedClientRows.has(account.id) ? (
                                    <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 p-2">
                                      <p className="mb-1 text-xs font-semibold text-slate-600">Conturi atribuite aceluiași client</p>
                                      <ul className="space-y-1">
                                        {(accountsByClient.get(account.attached_client_id ?? 0) ?? []).slice(0, 5).map((related) => (
                                          <li key={`${account.id}-related-${related.id}`} className="text-xs text-slate-700">
                                            <Link href={`/agency-accounts/google_ads/${encodeURIComponent(related.id)}`} className="hover:underline">
                                              {accountDisplayName(related)}
                                            </Link>{" "}
                                            <span className="text-slate-500">({related.id})</span>
                                            {related.id === account.id ? <span className="ml-1 rounded bg-indigo-100 px-1 py-0.5 text-[10px] font-medium text-indigo-700">curent</span> : null}
                                          </li>
                                        ))}
                                      </ul>
                                      {(accountsByClient.get(account.attached_client_id ?? 0) ?? []).length > 5 ? (
                                        <p className="mt-1 text-xs text-slate-500">și încă {(accountsByClient.get(account.attached_client_id ?? 0) ?? []).length - 5}</p>
                                      ) : null}
                                    </div>
                                  ) : null}
                                </>
                              ) : (
                                <p className="text-sm text-amber-700">Neatașat la client</p>
                              )}
                            </div>

                            <div>
                              <p className="text-xs font-semibold uppercase text-slate-500 lg:hidden">Acțiuni</p>
                              <select
                                className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
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
                            </div>

                            <div>
                              <p className="text-xs font-semibold uppercase text-slate-500 lg:hidden">Detach</p>
                              {account.attached_client_id ? (
                                <button
                                  type="button"
                                  className="inline-flex w-full items-center justify-center rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                                  onClick={() => void detachGoogleAccount(account.attached_client_id ?? 0, account.id)}
                                  disabled={controlsDisabled}
                                >
                                  Detach
                                </button>
                              ) : (
                                <span className="inline-flex w-full items-center justify-center rounded-md border border-dashed border-slate-200 px-3 py-2 text-xs text-slate-400">-</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                      {pagedGoogleAccounts.length === 0 ? (
                        <div className="px-3 py-6 text-sm text-slate-500">Nu există conturi care să corespundă filtrului de client.</div>
                      ) : null}
                    </div>

                    <div className="flex flex-col gap-2 border-t border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 md:flex-row md:items-center md:justify-between">
                      <p>Afișare {filteredGoogleAccounts.length === 0 ? 0 : (accountsPage - 1) * accountsPageSize + 1}-{Math.min(accountsPage * accountsPageSize, filteredGoogleAccounts.length)} din {filteredGoogleAccounts.length}</p>
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
