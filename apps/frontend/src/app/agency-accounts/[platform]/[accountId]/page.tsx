"use client";

import React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest, listAccountSyncRuns, repairSyncRun, retryFailedSyncRun, type AccountSyncRun } from "@/lib/api";

type AccountMeta = {
  id: string;
  name: string;
  platform?: string;
  account_id?: string;
  display_name?: string;
  account_name?: string;
  attached_client_id?: number | null;
  attached_client_name?: string | null;
  client_id?: number | null;
  client_name?: string | null;
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

type EffectiveSyncHeader = {
  hasActiveSync: boolean;
  lastRunStatus?: string | null;
  lastRunType?: string | null;
  lastRunStartedAt?: string | null;
  lastRunFinishedAt?: string | null;
  lastError?: string | null;
};

type AccountsListResponse = {
  items: AccountMeta[];
};

type SyncRun = AccountSyncRun;

type SyncChunk = {
  chunk_index: number;
  date_start?: string | null;
  date_end?: string | null;
  status?: string | null;
  attempts?: number | null;
  rows_written?: number | null;
  duration_ms?: number | null;
  error?: string | null;
};

type ChunksResponse = {
  job_id: string;
  chunks: SyncChunk[];
};

type RepairNotice = {
  tone: "success" | "info" | "error";
  text: string;
};

type RetryNotice = {
  tone: "success" | "info" | "error";
  text: string;
};

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function normalizeAccountId(value: string): string {
  return value.replace(/[-_]/g, "").trim();
}

function accountListEndpoint(platform: string): string | null {
  const normalized = String(platform).trim();
  if (normalized === "google_ads") return "/clients/accounts/google";
  if (normalized === "meta_ads") return "/clients/accounts/meta_ads";
  if (normalized === "tiktok_ads") return "/clients/accounts/tiktok_ads";
  return null;
}

function normalizeAccountMetaForPlatform(platform: string, item: AccountMeta): AccountMeta {
  const normalizedPlatform = String(platform).trim();
  const accountId = String(item.id ?? item.account_id ?? "").trim();
  const name = String(item.display_name ?? item.name ?? item.account_name ?? accountId).trim() || accountId;
  const attachedClientId = item.attached_client_id ?? (typeof item.client_id === "number" ? Number(item.client_id) : null);
  const attachedClientName = item.attached_client_name ?? (String(item.client_name ?? "").trim() || null);

  return {
    ...item,
    id: accountId,
    platform: String(item.platform ?? normalizedPlatform),
    name,
    display_name: name,
    attached_client_id: attachedClientId,
    attached_client_name: attachedClientName,
  };
}

function normalizeStatus(status?: string | null): string {
  return String(status ?? "queued").toLowerCase();
}

function normalizeJobType(jobType?: string | null): string {
  return String(jobType ?? "").trim().toLowerCase();
}

function statusBadge(status?: string | null): string {
  const normalized = normalizeStatus(status);
  if (["done", "success", "completed"].includes(normalized)) return "bg-emerald-100 text-emerald-700";
  if (["error", "failed"].includes(normalized)) return "bg-red-100 text-red-700";
  if (normalized === "partial") return "bg-amber-100 text-amber-700";
  if (["running", "queued", "pending"].includes(normalized)) return "bg-indigo-100 text-indigo-700";
  return "bg-slate-100 text-slate-700";
}

function isRunActive(status?: string | null): boolean {
  return ["queued", "running", "pending"].includes(normalizeStatus(status));
}

function isRunTerminal(status?: string | null): boolean {
  return ["done", "success", "completed", "error", "failed", "partial", "cancelled"].includes(normalizeStatus(status));
}

function hasRetryFailedSignals(run: SyncRun): boolean {
  const status = normalizeStatus(run.status);
  if (["error", "failed", "partial"].includes(status)) return true;
  if (Number(run.error_count ?? 0) > 0) return true;
  return String(run.error ?? "").trim().length > 0;
}

function parseDateOnly(value?: string | null): number | null {
  const raw = String(value ?? "").trim();
  if (!raw) return null;
  const parsed = Date.parse(raw.length <= 10 ? `${raw}T00:00:00Z` : raw);
  if (Number.isNaN(parsed)) return null;
  return parsed;
}

function isSuccessStatus(status?: string | null): boolean {
  return ["done", "success", "completed"].includes(normalizeStatus(status));
}

function retrySourceJobId(run: SyncRun): string {
  const metadata = run.metadata && typeof run.metadata === "object" ? run.metadata : {};
  const retryReason = String((metadata as { retry_reason?: unknown }).retry_reason ?? "").trim();
  if (retryReason !== "failed_chunks") return "";
  return String((metadata as { retry_of_job_id?: unknown }).retry_of_job_id ?? "").trim();
}

function coversRunRangeByAccountMeta(run: SyncRun, accountMeta: AccountMeta | null): boolean {
  const accountStart = parseDateOnly(accountMeta?.sync_start_date);
  const accountEnd = parseDateOnly(accountMeta?.backfill_completed_through);
  const runStart = parseDateOnly(run.date_start);
  const runEnd = parseDateOnly(run.date_end);
  if (accountStart === null || accountEnd === null || runStart === null || runEnd === null) return false;
  return accountStart <= runStart && accountEnd >= runEnd;
}

function toRunTimestamp(run?: SyncRun | null): number {
  if (!run) return 0;
  const raw = run.finished_at ?? run.started_at ?? run.created_at ?? null;
  if (!raw) return 0;
  const ts = new Date(raw).getTime();
  return Number.isFinite(ts) ? ts : 0;
}

function toMetaTimestamp(meta?: AccountMeta | null): number {
  if (!meta) return 0;
  const raw = meta.last_run_finished_at ?? meta.last_run_started_at ?? meta.last_success_at ?? null;
  if (!raw) return 0;
  const ts = new Date(raw).getTime();
  return Number.isFinite(ts) ? ts : 0;
}

export default function AgencyAccountDetailPage() {
  const params = useParams<{ platform: string; accountId: string }>();
  const platform = decodeURIComponent(String(params?.platform ?? "")).trim();
  const accountId = decodeURIComponent(String(params?.accountId ?? "")).trim();

  const [accountMeta, setAccountMeta] = useState<AccountMeta | null>(null);
  const [metaLoading, setMetaLoading] = useState(true);
  const [metaError, setMetaError] = useState("");

  const [runs, setRuns] = useState<SyncRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [runsError, setRunsError] = useState("");

  const [expandedRunIds, setExpandedRunIds] = useState<Set<string>>(new Set());
  const [chunksByRun, setChunksByRun] = useState<Record<string, SyncChunk[]>>({});
  const [chunksLoadingByRun, setChunksLoadingByRun] = useState<Record<string, boolean>>({});
  const [chunksErrorByRun, setChunksErrorByRun] = useState<Record<string, string>>({});

  const [repairingJobId, setRepairingJobId] = useState<string | null>(null);
  const [repairNotice, setRepairNotice] = useState<RepairNotice | null>(null);
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null);
  const [retryNotice, setRetryNotice] = useState<RetryNotice | null>(null);

  const runsSorted = useMemo(() => {
    return [...runs].sort((a, b) => {
      const aTime = new Date(a.created_at ?? a.started_at ?? 0).getTime() || 0;
      const bTime = new Date(b.created_at ?? b.started_at ?? 0).getTime() || 0;
      return bTime - aTime;
    });
  }, [runs]);

  const hasActiveRun = useMemo(() => runsSorted.some((run) => isRunActive(run.status)), [runsSorted]);
  const hasActiveHistoricalRun = useMemo(
    () => runsSorted.some((run) => normalizeJobType(run.job_type) === "historical_backfill" && isRunActive(run.status)),
    [runsSorted],
  );
  const repairableRun = useMemo(
    () => runsSorted.find((run) => isRunActive(run.status) && normalizeJobType(run.job_type) === "historical_backfill") ?? null,
    [runsSorted],
  );
  const successfulRetrySourceIds = useMemo(() => {
    const ids = new Set<string>();
    for (const run of runsSorted) {
      if (normalizeJobType(run.job_type) !== "historical_backfill") continue;
      if (!isSuccessStatus(run.status)) continue;
      const sourceJobId = retrySourceJobId(run);
      if (sourceJobId) ids.add(sourceJobId);
    }
    return ids;
  }, [runsSorted]);
  const fullyRecoveredSourceRunIds = useMemo(() => {
    const ids = new Set<string>();
    for (const run of runsSorted) {
      if (normalizeJobType(run.job_type) !== "historical_backfill") continue;
      if (!isRunTerminal(run.status)) continue;
      if (!hasRetryFailedSignals(run)) continue;
      if (!successfulRetrySourceIds.has(run.job_id)) continue;
      if (!coversRunRangeByAccountMeta(run, accountMeta)) continue;
      ids.add(run.job_id);
    }
    return ids;
  }, [accountMeta, runsSorted, successfulRetrySourceIds]);

  const latestTerminalError = useMemo(() => {
    const failedRun = runsSorted.find(
      (run) =>
        ["error", "failed", "partial"].includes(normalizeStatus(run.status)) &&
        !fullyRecoveredSourceRunIds.has(run.job_id),
    );
    if (!failedRun) return "";
    const summary = String((failedRun as { last_error_summary?: unknown }).last_error_summary ?? "").trim();
    if (summary) return summary;
    const runError = String(failedRun.error ?? "").trim();
    if (runError) return runError;
    const details = (failedRun as { last_error_details?: unknown }).last_error_details;
    if (details && typeof details === "object") {
      const providerMessage = String((details as { provider_error_message?: unknown }).provider_error_message ?? "").trim();
      if (providerMessage) return providerMessage;
    }
    return "run failed";
  }, [fullyRecoveredSourceRunIds, runsSorted]);
  const retryableFailedRun = useMemo(
    () =>
      runsSorted.find(
        (run) =>
          normalizeJobType(run.job_type) === "historical_backfill" &&
          isRunTerminal(run.status) &&
          hasRetryFailedSignals(run) &&
          !fullyRecoveredSourceRunIds.has(run.job_id),
      ) ?? null,
    [fullyRecoveredSourceRunIds, runsSorted],
  );
  const retryActionRun = useMemo(() => {
    if (hasActiveHistoricalRun) return null;
    return retryableFailedRun;
  }, [hasActiveHistoricalRun, retryableFailedRun]);
  const latestRun = runsSorted[0] ?? null;
  const effectiveSyncHeader = useMemo<EffectiveSyncHeader>(() => {
    const metaBased: EffectiveSyncHeader = {
      hasActiveSync: Boolean(accountMeta?.has_active_sync),
      lastRunStatus: accountMeta?.last_run_status ?? null,
      lastRunType: accountMeta?.last_run_type ?? null,
      lastRunStartedAt: accountMeta?.last_run_started_at ?? null,
      lastRunFinishedAt: accountMeta?.last_run_finished_at ?? null,
      lastError: accountMeta?.last_error ?? null,
    };
    if (!latestRun) return metaBased;

    const runIsNewerOrEqual = toRunTimestamp(latestRun) >= toMetaTimestamp(accountMeta);
    if (!runIsNewerOrEqual) {
      return { ...metaBased, hasActiveSync: hasActiveRun };
    }

    const runStatus = latestRun.status ?? metaBased.lastRunStatus ?? null;
    const runError = String(latestRun.error ?? "").trim();
    return {
      hasActiveSync: hasActiveRun,
      lastRunStatus: runStatus,
      lastRunType: latestRun.job_type ?? metaBased.lastRunType ?? null,
      lastRunStartedAt: latestRun.started_at ?? metaBased.lastRunStartedAt ?? null,
      lastRunFinishedAt: latestRun.finished_at ?? metaBased.lastRunFinishedAt ?? null,
      lastError: runError || metaBased.lastError || null,
    };
  }, [accountMeta, hasActiveRun, latestRun]);

  const hadActiveRunRef = useRef(false);

  async function loadAccountMeta() {
    const endpoint = accountListEndpoint(platform);
    if (!endpoint) {
      setAccountMeta(null);
      setMetaLoading(false);
      setMetaError("");
      return;
    }

    setMetaLoading(true);
    setMetaError("");
    try {
      const payload = await apiRequest<AccountsListResponse>(endpoint);
      const normalizedTarget = normalizeAccountId(accountId);
      const normalizedItems = (payload.items ?? []).map((item) => normalizeAccountMetaForPlatform(platform, item));
      const found = normalizedItems.find((item) => normalizeAccountId(String(item.id ?? item.account_id ?? "")) === normalizedTarget);
      setAccountMeta(found ?? null);
    } catch (err) {
      setMetaError(err instanceof Error ? err.message : "Nu am putut încărca metadata contului.");
      setAccountMeta(null);
    } finally {
      setMetaLoading(false);
    }
  }

  async function loadRuns() {
    setRunsLoading(true);
    setRunsError("");
    try {
      const runsPayload = await listAccountSyncRuns(platform, accountId, 100);
      setRuns(runsPayload);
    } catch (err) {
      setRuns([]);
      setRunsError(err instanceof Error ? err.message : "Nu am putut încărca sync runs.");
    } finally {
      setRunsLoading(false);
    }
  }

  async function loadChunks(jobId: string) {
    setChunksLoadingByRun((state) => ({ ...state, [jobId]: true }));
    setChunksErrorByRun((state) => ({ ...state, [jobId]: "" }));
    try {
      const payload = await apiRequest<ChunksResponse>(`/agency/sync-runs/${encodeURIComponent(jobId)}/chunks`);
      setChunksByRun((state) => ({ ...state, [jobId]: payload.chunks ?? [] }));
    } catch (err) {
      setChunksByRun((state) => ({ ...state, [jobId]: [] }));
      setChunksErrorByRun((state) => ({ ...state, [jobId]: err instanceof Error ? err.message : "Nu am putut încărca chunks." }));
    } finally {
      setChunksLoadingByRun((state) => ({ ...state, [jobId]: false }));
    }
  }

  function toggleRunExpanded(jobId: string) {
    setExpandedRunIds((current) => {
      const next = new Set(current);
      if (next.has(jobId)) {
        next.delete(jobId);
      } else {
        next.add(jobId);
        if (!chunksByRun[jobId] && !chunksLoadingByRun[jobId]) {
          void loadChunks(jobId);
        }
      }
      return next;
    });
  }

  async function refreshAll() {
    await Promise.all([loadAccountMeta(), loadRuns()]);
  }

  async function handleRepairRun(jobId: string) {
    if (repairingJobId) return;
    setRepairingJobId(jobId);
    setRepairNotice(null);

    try {
      const result = await repairSyncRun(jobId);
      if (!result.ok) {
        if (result.outcome === "not_found") {
          setRepairNotice({ tone: "error", text: "Run-ul nu mai există. Reîncarc lista de sync runs." });
          await refreshAll();
          return;
        }
        setRepairNotice({ tone: "error", text: result.message || "Repair a eșuat. Încearcă din nou." });
        return;
      }

      const outcome = result.payload.outcome;
      if (outcome === "repaired") {
        setRepairNotice({ tone: "success", text: "Repair aplicat. Am reîncărcat statusul run-urilor." });
        await refreshAll();
      } else if (outcome === "noop_not_active") {
        setRepairNotice({ tone: "info", text: "Run-ul nu mai este activ. Am reîncărcat statusul." });
        await refreshAll();
      } else if (outcome === "noop_active_fresh") {
        setRepairNotice({ tone: "info", text: "Run-ul este încă activ și fresh. Repair-ul nu s-a aplicat încă." });
      } else if (outcome === "not_found") {
        setRepairNotice({ tone: "error", text: "Run-ul nu a fost găsit." });
      } else {
        setRepairNotice({ tone: "error", text: "Outcome necunoscut la repair." });
      }

      for (const expandedRunId of expandedRunIds) {
        void loadChunks(expandedRunId);
      }
    } catch (err) {
      setRepairNotice({
        tone: "error",
        text: err instanceof Error ? err.message : "Nu am putut executa repair-ul pentru acest run.",
      });
    } finally {
      setRepairingJobId(null);
    }
  }

  async function handleRetryFailedRun(jobId: string) {
    if (retryingJobId) return;
    setRetryingJobId(jobId);
    setRetryNotice(null);

    try {
      const result = await retryFailedSyncRun(jobId);
      if (!result.ok) {
        if (result.outcome === "not_found") {
          setRetryNotice({ tone: "error", text: "Run-ul nu mai există pentru retry-failed. Reîncarc lista de sync runs." });
          await refreshAll();
          return;
        }
        setRetryNotice({ tone: "error", text: result.message || "Retry-failed a eșuat. Încearcă din nou." });
        return;
      }

      const outcome = result.payload.outcome;
      if (outcome === "created") {
        setRetryNotice({ tone: "success", text: "Retry pornit pentru chunk-urile eșuate. Am reîncărcat statusul run-urilor." });
        await refreshAll();
      } else if (outcome === "already_exists") {
        setRetryNotice({ tone: "info", text: "Există deja un retry activ pentru acest run. Am reîncărcat statusul." });
        await refreshAll();
      } else if (outcome === "no_failed_chunks") {
        setRetryNotice({ tone: "info", text: "Run-ul nu are chunk-uri eșuate de reluat." });
      } else if (outcome === "not_retryable") {
        setRetryNotice({ tone: "info", text: "Run-ul nu este eligibil pentru retry-failed." });
      } else if (outcome === "not_found") {
        setRetryNotice({ tone: "error", text: "Run-ul nu a fost găsit. Reîncarc lista de sync runs." });
        await refreshAll();
      } else {
        setRetryNotice({ tone: "error", text: "Outcome necunoscut la retry-failed." });
      }

      for (const expandedRunId of expandedRunIds) {
        void loadChunks(expandedRunId);
      }
    } catch (err) {
      setRetryNotice({
        tone: "error",
        text: err instanceof Error ? err.message : "Nu am putut executa retry-failed pentru acest run.",
      });
    } finally {
      setRetryingJobId(null);
    }
  }

  useEffect(() => {
    if (!platform || !accountId) return;
    void refreshAll();
  }, [platform, accountId]);

  useEffect(() => {
    if (!hasActiveRun) return;
    const intervalId = window.setInterval(() => {
      void loadAccountMeta();
      void loadRuns();
      for (const jobId of expandedRunIds) {
        void loadChunks(jobId);
      }
    }, 2500);

    return () => window.clearInterval(intervalId);
  }, [expandedRunIds, hasActiveRun]);

  useEffect(() => {
    if (hasActiveRun) {
      hadActiveRunRef.current = true;
      return;
    }
    if (!hadActiveRunRef.current) return;
    hadActiveRunRef.current = false;
    void refreshAll();
  }, [hasActiveRun]);

  return (
    <ProtectedPage>
      <AppShell title="Agency Account Detail">
        <main className="space-y-4 p-6">
          <div>
            <Link href="/agency-accounts" className="text-sm text-indigo-600 hover:underline">← Back to Agency Accounts</Link>
            <h2 className="mt-2 text-lg font-semibold text-slate-900">Account: {accountMeta?.display_name ?? accountMeta?.name ?? accountId}</h2>
          </div>

          <section className="wm-card p-4">
            <h3 className="text-base font-semibold text-slate-900">Account status / coverage</h3>
            {metaError ? <p className="mt-2 text-sm text-red-600">{metaError}</p> : null}
            {metaLoading ? <p className="mt-2 text-sm text-slate-500">Se încarcă metadata contului...</p> : null}
            {!metaLoading ? (
              <>
              <div className="mt-3 grid grid-cols-1 gap-2 text-sm text-slate-700 md:grid-cols-2">
                <p><span className="font-medium">Account name:</span> {accountMeta?.display_name ?? accountMeta?.name ?? "-"}</p>
                <p><span className="font-medium">Account ID:</span> {accountId}</p>
                <p><span className="font-medium">Platform:</span> {accountMeta?.platform ?? platform}</p>
                <p><span className="font-medium">Attached client:</span> {accountMeta?.attached_client_name ?? "Neatașat"}</p>
                <p><span className="font-medium">Timezone:</span> {accountMeta?.timezone ?? "-"}</p>
                <p><span className="font-medium">Currency:</span> {accountMeta?.currency ?? "-"}</p>
                <p><span className="font-medium">sync_start_date:</span> {accountMeta?.sync_start_date ?? "-"}</p>
                <p><span className="font-medium">backfill_completed_through:</span> {accountMeta?.backfill_completed_through ?? "Backfill neinițiat"}</p>
                <p><span className="font-medium">rolling_synced_through:</span> {accountMeta?.rolling_synced_through ?? "Rolling sync neinițiat"}</p>
                <p><span className="font-medium">last_success_at:</span> {accountMeta?.last_success_at ? formatDate(accountMeta?.last_success_at) : "Nu există sync finalizat încă"}</p>
                <p><span className="font-medium">last_run_status:</span> {effectiveSyncHeader.lastRunStatus ?? "N/A"}</p>
                <p><span className="font-medium">last_run_type:</span> {effectiveSyncHeader.lastRunType ?? "N/A"}</p>
                <p><span className="font-medium">last_run_started_at:</span> {formatDate(effectiveSyncHeader.lastRunStartedAt)}</p>
                <p><span className="font-medium">last_run_finished_at:</span> {formatDate(effectiveSyncHeader.lastRunFinishedAt)}</p>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className={`rounded px-2 py-1 font-medium ${effectiveSyncHeader.hasActiveSync ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-600"}`}>
                  {effectiveSyncHeader.hasActiveSync ? "Sync activ" : "Fără sync activ"}
                </span>
                {effectiveSyncHeader.lastRunStatus ? (
                  <span className={`rounded px-2 py-1 font-medium ${statusBadge(effectiveSyncHeader.lastRunStatus)}`}>
                    Ultimul status: {effectiveSyncHeader.lastRunStatus}
                  </span>
                ) : null}
              </div>
              </>
            ) : null}
            {effectiveSyncHeader.lastError ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">{effectiveSyncHeader.lastError}</div> : null}
          </section>

          <section className="wm-card p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-base font-semibold text-slate-900">Sync runs</h3>
                {hasActiveRun ? <p className="text-xs text-indigo-700">Auto-refresh activ (există run queued/running/pending).</p> : <p className="text-xs text-slate-600">Auto-refresh oprit (nu există run activ).</p>}
              </div>
              <div className="flex items-center gap-2">
                {repairableRun ? (
                  <button
                    type="button"
                    className="inline-flex items-center rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800 transition hover:bg-amber-100 disabled:opacity-50"
                    onClick={() => {
                      void handleRepairRun(repairableRun.job_id);
                    }}
                    disabled={Boolean(repairingJobId)}
                  >
                    {repairingJobId === repairableRun.job_id ? "Se repară..." : "Repară sync blocat"}
                  </button>
                ) : null}
                {retryActionRun ? (
                  <button
                    type="button"
                    className="inline-flex items-center rounded-md border border-indigo-300 bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-800 transition hover:bg-indigo-100 disabled:opacity-50"
                    onClick={() => {
                      void handleRetryFailedRun(retryActionRun.job_id);
                    }}
                    disabled={Boolean(retryingJobId)}
                  >
                    {retryingJobId === retryActionRun.job_id ? "Se pornește retry..." : "Reia chunk-urile eșuate"}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
                  onClick={() => {
                    void loadRuns();
                    for (const jobId of expandedRunIds) {
                      void loadChunks(jobId);
                    }
                  }}
                  disabled={runsLoading}
                >
                  {runsLoading ? "Refreshing..." : "Refresh"}
                </button>
              </div>
            </div>

            {repairNotice ? (
              <p
                className={`mt-2 rounded border px-3 py-2 text-sm ${
                  repairNotice.tone === "success"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : repairNotice.tone === "info"
                      ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                      : "border-red-200 bg-red-50 text-red-700"
                }`}
              >
                {repairNotice.text}
              </p>
            ) : null}
            {retryNotice ? (
              <p
                className={`mt-2 rounded border px-3 py-2 text-sm ${
                  retryNotice.tone === "success"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : retryNotice.tone === "info"
                      ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                      : "border-red-200 bg-red-50 text-red-700"
                }`}
              >
                {retryNotice.text}
              </p>
            ) : null}
            {runsError ? <p className="mt-2 text-sm text-red-600">{runsError}</p> : null}
            {runsLoading ? <p className="mt-2 text-sm text-slate-500">Se încarcă sync runs...</p> : null}
            {!runsLoading && runsSorted.length <= 0 && !runsError ? (
              <p className="mt-2 text-sm text-slate-500">Nu există sync runs pentru acest cont încă.</p>
            ) : null}
            {!hasActiveRun && latestTerminalError ? (
              <p className="mt-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                Ultimul run a eșuat: {latestTerminalError}
              </p>
            ) : null}

            {runsSorted.length > 0 ? (
              <div className="mt-3 space-y-3">
                {runsSorted.map((run) => {
                  const expanded = expandedRunIds.has(run.job_id);
                  const chunks = chunksByRun[run.job_id] ?? [];
                  const chunksLoading = Boolean(chunksLoadingByRun[run.job_id]);
                  const chunksError = chunksErrorByRun[run.job_id] ?? "";
                  const done = Number(run.chunks_done ?? 0);
                  const total = Number(run.chunks_total ?? 0);
                  const progressPercent = total > 0 ? Math.round((done / total) * 100) : 0;

                  return (
                    <article key={run.job_id} className="rounded-md border border-slate-200">
                      <button
                        type="button"
                        className="flex w-full flex-wrap items-center justify-between gap-2 px-3 py-3 text-left hover:bg-slate-50"
                        onClick={() => toggleRunExpanded(run.job_id)}
                      >
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-slate-900">{run.job_type ?? "unknown"} · {formatDate(run.created_at)}</p>
                          <p className="text-xs text-slate-600">{run.date_start ?? "-"} → {run.date_end ?? "-"} · start: {formatDate(run.started_at)} · end: {formatDate(run.finished_at)}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`rounded px-2 py-1 text-xs font-medium ${statusBadge(run.status)}`}>{run.status ?? "queued"}</span>
                          <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">{run.trigger_source === "cron" ? "cron" : "manual"}</span>
                          <span className="text-xs text-slate-600">{done}/{total || "-"} chunks</span>
                          <span className="text-xs text-slate-600">errors: {run.error_count ?? (run.error ? 1 : 0)}</span>
                          <span className="text-xs text-indigo-700">{expanded ? "Hide logs" : "Show logs"}</span>
                        </div>
                      </button>

                      {total > 0 ? (
                        <div className="px-3 pb-2">
                          <div className="h-1.5 w-full overflow-hidden rounded bg-slate-200">
                            <div className="h-full bg-indigo-600" style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }} />
                          </div>
                          <p className="mt-1 text-xs text-slate-600">Progress: {progressPercent}% · rows written: {run.rows_written ?? 0}</p>
                        </div>
                      ) : null}

                      {run.error ? <p className="px-3 pb-2 text-xs text-red-600">Error: {run.error}</p> : null}
                      {String((run as { last_error_summary?: unknown }).last_error_summary ?? "").trim() ? (
                        <p className="px-3 pb-2 text-xs text-red-600">Summary: {String((run as { last_error_summary?: unknown }).last_error_summary ?? "")}</p>
                      ) : null}
                      {(run as { last_error_details?: unknown }).last_error_details && typeof (run as { last_error_details?: unknown }).last_error_details === "object" ? (
                        <p className="px-3 pb-2 text-xs text-red-600">Details: {String(((run as { last_error_details?: Record<string, unknown> }).last_error_details?.provider_error_message as string | undefined) || ((run as { last_error_details?: Record<string, unknown> }).last_error_details?.provider_error_code as string | undefined) || "available")}</p>
                      ) : null}

                      {expanded ? (
                        <div className="border-t border-slate-100 bg-slate-50 px-3 py-3">
                          {chunksError ? <p className="text-xs text-red-600">{chunksError}</p> : null}
                          {chunksLoading ? <p className="text-xs text-slate-500">Se încarcă chunk logs...</p> : null}
                          {!chunksLoading && chunks.length <= 0 && !chunksError ? (
                            <p className="text-xs text-slate-500">Nu există chunk logs pentru acest run.</p>
                          ) : null}
                          {chunks.length > 0 ? (
                            <div className="space-y-2">
                              {chunks.map((chunk) => (
                                <div key={`${run.job_id}-${chunk.chunk_index}`} className="rounded border border-slate-200 bg-white p-2 text-xs text-slate-700">
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <p className="font-medium">Chunk #{chunk.chunk_index} · {chunk.date_start ?? "-"} → {chunk.date_end ?? "-"}</p>
                                    <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${statusBadge(chunk.status)}`}>{chunk.status ?? "queued"}</span>
                                  </div>
                                  <p className="mt-1">Attempts: {chunk.attempts ?? 0} · Rows: {chunk.rows_written ?? 0} · Duration: {chunk.duration_ms ?? "-"} ms</p>
                                  {chunk.error ? <p className="mt-1 text-red-600">Error: {chunk.error}</p> : null}
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            ) : null}
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
