"use client";

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
  rolling_window_days?: number | null;
};

type GoogleAccountsResponse = {
  items: GoogleAccount[];
  count: number;
  last_import_at?: string | null;
};

type BatchRun = {
  account_id?: string;
  status?: string;
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
  progress: BatchProgress;
  runs: BatchRun[];
};

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

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatRoDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = date.getFullYear();
  return `${day}.${month}.${year}`;
}

function toIsoDateLocal(value: Date): string {
  const y = value.getFullYear();
  const m = String(value.getMonth() + 1).padStart(2, "0");
  const d = String(value.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export default function AgencyAccountsPage() {
  const [clients, setClients] = useState<ClientRecord[]>([]);
  const [summary, setSummary] = useState<AccountSummaryItem[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState<string>("google_ads");
  const [googleAccounts, setGoogleAccounts] = useState<GoogleAccount[]>([]);
  const [attachStatus, setAttachStatus] = useState("");
  const [loadError, setLoadError] = useState("");
  const [refreshBusy, setRefreshBusy] = useState(false);
  const [scheduleBusy, setScheduleBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [selectedAccountIds, setSelectedAccountIds] = useState<Set<string>>(new Set());
  const [accountsPage, setAccountsPage] = useState(1);
  const [accountsPageSize, setAccountsPageSize] = useState(50);
  const [currentBatchId, setCurrentBatchId] = useState<string | null>(null);
  const [currentJobType, setCurrentJobType] = useState<"rolling_refresh" | "historical_backfill" | null>(null);
  const [currentStartDateUsed, setCurrentStartDateUsed] = useState<string | null>(null);
  const [syncError, setSyncError] = useState("");
  const [syncStatusMessage, setSyncStatusMessage] = useState("");
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null);
  const [batchRunsByAccount, setBatchRunsByAccount] = useState<Record<string, string>>({});

  async function loadClients() {
    const payload = await apiRequest<ClientsResponse>("/clients");
    setClients(payload.items);
  }

  async function loadAccountSummary() {
    const payload = await apiRequest<AccountSummaryResponse>("/clients/accounts/summary");
    setSummary(payload.items);
  }

  async function loadGoogleAccounts() {
    const payload = await apiRequest<GoogleAccountsResponse>("/clients/accounts/google");
    setGoogleAccounts(payload.items);
  }

  async function reloadAccountsData() {
    try {
      setLoadError("");
      setLoading(true);
      await Promise.all([loadClients(), loadAccountSummary(), loadGoogleAccounts()]);
      setSelectedAccountIds(new Set());
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Nu am putut încărca datele Agency Accounts");
      setClients([]);
      setSummary([]);
      setGoogleAccounts([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reloadAccountsData();
  }, []);

  useEffect(() => {
    setSelectedAccountIds(new Set());
  }, [selectedPlatform]);

  async function attachGoogleAccount(clientId: number, customerId: string) {
    setAttachStatus("");
    try {
      await apiRequest(`/clients/${clientId}/attach-google-account`, {
        method: "POST",
        body: JSON.stringify({ customer_id: customerId }),
      });
      const target = clients.find((c) => c.id === clientId);
      setAttachStatus(`Contul ${customerId} a fost atașat clientului ${target?.name ?? `#${clientId}`}.`);
      await reloadAccountsData();
    } catch (err) {
      setAttachStatus(err instanceof Error ? err.message : "Nu am putut atașa contul Google");
    }
  }

  async function detachGoogleAccount(clientId: number, customerId: string) {
    setAttachStatus("");
    try {
      await apiRequest(`/clients/${clientId}/detach-google-account`, {
        method: "DELETE",
        body: JSON.stringify({ customer_id: customerId }),
      });
      const target = clients.find((c) => c.id === clientId);
      setAttachStatus(`Contul ${customerId} a fost detașat de la clientul ${target?.name ?? `#${clientId}`}.`);
      await reloadAccountsData();
    } catch (err) {
      setAttachStatus(err instanceof Error ? err.message : "Nu am putut detașa contul Google");
    }
  }

  async function refreshGoogleAccountNames() {
    setAttachStatus("");
    setRefreshBusy(true);
    try {
      const payload = await apiRequest<{ refreshed_count: number }>("/integrations/google-ads/refresh-account-names", {
        method: "POST",
      });
      setAttachStatus(`Au fost actualizate ${payload.refreshed_count} conturi Google.`);
      await reloadAccountsData();
    } catch (err) {
      setAttachStatus(err instanceof Error ? err.message : "Nu am putut actualiza numele conturilor Google");
    } finally {
      setRefreshBusy(false);
    }
  }

  const selectedSummary = useMemo(() => summary.find((item) => item.platform === selectedPlatform), [summary, selectedPlatform]);

  const totalAccountsPages = useMemo(() => Math.max(1, Math.ceil(googleAccounts.length / accountsPageSize)), [googleAccounts.length, accountsPageSize]);

  const pagedGoogleAccounts = useMemo(() => {
    const start = (accountsPage - 1) * accountsPageSize;
    return googleAccounts.slice(start, start + accountsPageSize);
  }, [googleAccounts, accountsPage, accountsPageSize]);

  const selectedCount = selectedAccountIds.size;
  const syncInProgress = currentBatchId !== null;

  const selectablePageAccountIds = useMemo(
    () => pagedGoogleAccounts.filter((item) => item.attached_client_id).map((item) => item.id),
    [pagedGoogleAccounts],
  );

  const allSelectableOnPageSelected =
    selectablePageAccountIds.length > 0 && selectablePageAccountIds.every((accountId) => selectedAccountIds.has(accountId));

  useEffect(() => {
    setAccountsPage(1);
  }, [accountsPageSize]);

  useEffect(() => {
    if (accountsPage > totalAccountsPages) {
      setAccountsPage(totalAccountsPages);
    }
  }, [accountsPage, totalAccountsPages]);

  async function startBatchSync(mode: "rolling" | "historical") {
    const selectedMapped = googleAccounts.filter((account) => selectedAccountIds.has(account.id) && account.attached_client_id);
    if (selectedMapped.length <= 0) {
      setSyncError("Selectează cel puțin un cont atașat la client.");
      return;
    }

    if (mode === "historical") {
      const confirmed = window.confirm(`Vrei să descarci istoric pentru ${selectedMapped.length} conturi selectate?`);
      if (!confirmed) return;
    }

    setSyncError("");
    setSyncStatusMessage("");
    setBatchProgress(null);
    setBatchRunsByAccount({});

    const accountIds = selectedMapped.map((item) => item.id);
    const body: Record<string, unknown> = {
      platform: "google_ads",
      account_ids: accountIds,
      chunk_days: 7,
      grain: "account_daily",
    };

    let startDateUsed: string | null = null;
    if (mode === "rolling") {
      body.job_type = "rolling_refresh";
      body.days = 7;
      setCurrentJobType("rolling_refresh");
      setCurrentStartDateUsed(null);
    } else {
      body.job_type = "historical_backfill";
      const selectedStartDates = selectedMapped
        .map((item) => (item.sync_start_date ? item.sync_start_date.trim() : ""))
        .filter((value) => /^\d{4}-\d{2}-\d{2}$/.test(value));
      startDateUsed = selectedStartDates.sort()[0] ?? "2024-01-09";
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      body.start_date = startDateUsed;
      body.end_date = toIsoDateLocal(yesterday);
      setCurrentJobType("historical_backfill");
      setCurrentStartDateUsed(startDateUsed);
    }

    try {
      const response = await apiRequest<{ batch_id?: string; invalid_account_ids?: string[] }>("/agency/sync-runs/batch", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!response.batch_id) {
        throw new Error("Batch-ul nu a putut fi creat.");
      }
      setCurrentBatchId(response.batch_id);
      if ((response.invalid_account_ids ?? []).length > 0) {
        setSyncStatusMessage(`Unele conturi au fost ignorate: ${(response.invalid_account_ids ?? []).join(", ")}`);
      }
      if (mode === "historical") {
        setCurrentStartDateUsed(startDateUsed);
      }
    } catch (err) {
      setCurrentBatchId(null);
      setSyncError(err instanceof Error ? err.message : "Nu am putut porni sync-ul batch.");
    }
  }

  useEffect(() => {
    if (!currentBatchId) return;

    let cancelled = false;
    const poll = async () => {
      try {
        const payload = await apiRequest<BatchStatusResponse>(`/agency/sync-runs/batch/${currentBatchId}`);
        if (cancelled) return;

        setBatchProgress(payload.progress);
        const byAccount: Record<string, string> = {};
        payload.runs.forEach((item) => {
          if (item.account_id) {
            byAccount[item.account_id] = String(item.status || "queued");
          }
        });
        setBatchRunsByAccount(byAccount);

        const runningCount = Number(payload.progress.queued || 0) + Number(payload.progress.running || 0);
        if (runningCount <= 0) {
          setCurrentBatchId(null);
          if (Number(payload.progress.error || 0) > 0) {
            setSyncStatusMessage(`Sync finalizat cu erori: ${payload.progress.error} conturi`);
          } else if (currentJobType === "historical_backfill") {
            setSyncStatusMessage(`Date istorice descarcate începând cu ${formatRoDate(currentStartDateUsed ?? "")}`);
          } else {
            setSyncStatusMessage("Sync last 7 days finalizat cu succes.");
          }
        }
      } catch (err) {
        if (cancelled) return;
        setCurrentBatchId(null);
        setSyncError(err instanceof Error ? err.message : "Polling-ul batch a eșuat.");
      }
    };

    void poll();
    const intervalId = window.setInterval(() => {
      void poll();
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [currentBatchId, currentJobType, currentStartDateUsed]);

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
                    onClick={() => setSelectedPlatform(item.platform)}
                    className={`wm-card p-4 text-left transition ${active ? "ring-2 ring-indigo-500" : "hover:bg-slate-50"}`}
                  >
                    <p className="text-sm font-semibold text-slate-900">{prettyPlatform(item.platform)}</p>
                    <p className="mt-1 text-xs text-slate-500">Conturi conectate: {item.connected_count}</p>
                    <p className="mt-1 text-xs text-slate-500">Ultimul import: {formatDate(item.last_import_at)}</p>
                  </button>
                );
              })}
            </div>

            {selectedPlatform === "google_ads" ? (
              <div className="mt-4 wm-card p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-base font-semibold text-slate-900">Google Accounts disponibile</h3>
                  <div className="flex items-center gap-2">
                    <button className="wm-btn-primary" onClick={() => void startBatchSync("rolling")} disabled={scheduleBusy || refreshBusy}>
                      {scheduleBusy ? "Scheduling..." : "Sync last 7 days"}
                    </button>
                    <button className="wm-btn-secondary" onClick={() => void startBatchSync("historical")} disabled={scheduleBusy || refreshBusy}>
                      {scheduleBusy ? "Scheduling..." : "Download historical"}
                    </button>
                    <button className="wm-btn" onClick={() => void refreshGoogleAccountNames()} disabled={refreshBusy || scheduleBusy}>
                      {refreshBusy ? "Refresh..." : "Refresh Names"}
                    </button>
                  </div>
                </div>
                <p className="mt-1 text-xs text-slate-500">Ultimul import: {formatDate(selectedSummary?.last_import_at)}</p>
                {batchProgress ? (
                  <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-2">
                    <p className="text-xs text-slate-700">
                      Progres: {Math.round(Number(batchProgress.percent || 0))}% • {batchProgress.done}/{batchProgress.total_runs} done • {batchProgress.error} errors
                    </p>
                    <div className="mt-2 h-2 w-full overflow-hidden rounded bg-slate-200">
                      <div className="h-full bg-indigo-600" style={{ width: `${Math.max(0, Math.min(100, Number(batchProgress.percent || 0)))}%` }} />
                    </div>
                  </div>
                ) : null}
                {loadError ? <p className="mt-2 text-xs text-red-600">{loadError}</p> : null}
                {syncError ? <p className="mt-2 text-xs text-red-600">{syncError}</p> : null}
                {attachStatus ? <p className="mt-2 text-xs text-emerald-700">{attachStatus}</p> : null}
                {syncStatusMessage ? <p className="mt-2 text-xs text-indigo-700">{syncStatusMessage}</p> : null}
                <div className="mt-3 space-y-2">
                  {pagedGoogleAccounts.map((account) => (
                    <div key={account.id} className="flex flex-wrap items-center justify-between rounded-md border border-slate-200 px-3 py-2">
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={selectedAccountIds.has(account.id)}
                          onChange={(event) => {
                            setSelectedAccountIds((current) => {
                              const next = new Set(current);
                              if (event.target.checked) next.add(account.id);
                              else next.delete(account.id);
                              return next;
                            });
                          }}
                        />
                        <div>
                          <p className="text-sm font-medium text-slate-900">{account.name}</p>
                          <p className="text-xs text-slate-500">ID: {account.id}</p>
                          {account.attached_client_name ? <p className="text-xs text-emerald-700">Atașat la: {account.attached_client_name}</p> : null}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <select
                          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                          value={account.attached_client_id?.toString() ?? ""}
                          onChange={(event) => {
                            const value = Number(event.target.value);
                            if (value > 0) {
                              void attachGoogleAccount(value, account.id);
                            }
                          }}
                          disabled={scheduleBusy || loading}
                        >
                          <option value="">Atașează la client...</option>
                          {clients.map((client) => (
                            <option key={client.id} value={client.id}>
                              #{client.display_id ?? client.id} {client.name}
                            </option>
                          ))}
                        </select>
                        {account.attached_client_id ? (
                          <button className="wm-btn" onClick={() => void detachGoogleAccount(account.attached_client_id ?? 0, account.id)} disabled={scheduleBusy || loading}>
                            Detașează
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ))}
                  {googleAccounts.length === 0 ? <p className="text-sm text-slate-500">Nu există conturi importate.</p> : null}
                </div>
                {googleAccounts.length > 0 ? (
                  <div className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3 text-sm text-slate-600 md:flex-row md:items-center md:justify-between">
                    <p>
                      Afișare {(accountsPage - 1) * accountsPageSize + 1}-{Math.min(accountsPage * accountsPageSize, googleAccounts.length)} din {googleAccounts.length}
                    </p>
                    <div className="flex items-center gap-2">
                      <span>Rânduri/pagină</span>
                      <select
                        className="rounded-md border border-slate-300 px-2 py-1"
                        value={accountsPageSize}
                        onChange={(event) => setAccountsPageSize(Number(event.target.value))}
                      >
                        {[25, 50, 100, 200, 500].map((size) => (
                          <option key={size} value={size}>{size}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="rounded border border-slate-300 px-2 py-1 disabled:opacity-50"
                        disabled={accountsPage <= 1}
                        onClick={() => setAccountsPage((current) => Math.max(1, current - 1))}
                      >
                        Anterior
                      </button>
                      <span>Pagina {accountsPage}/{totalAccountsPages}</span>
                      <button
                        type="button"
                        className="rounded border border-slate-300 px-2 py-1 disabled:opacity-50"
                        disabled={accountsPage >= totalAccountsPages}
                        onClick={() => setAccountsPage((current) => Math.min(totalAccountsPages, current + 1))}
                      >
                        Următor
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="mt-4 wm-card p-4 text-sm text-slate-500">Detalierea conturilor este disponibilă momentan pentru Google Ads.</div>
            )}
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
