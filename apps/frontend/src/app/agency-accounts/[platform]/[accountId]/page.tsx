"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

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
};

type SyncRun = {
  job_id: string;
  batch_id?: string | null;
  job_type?: string | null;
  grain?: string | null;
  status?: string | null;
  date_start?: string | null;
  date_end?: string | null;
  chunks_total?: number | null;
  chunks_done?: number | null;
  rows_written?: number | null;
  error_count?: number | null;
  error?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
};

type AccountRunsResponse = {
  platform: string;
  account_id: string;
  limit: number;
  runs: SyncRun[];
};

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

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function normalizeAccountId(value: string): string {
  return value.replace(/-/g, "").trim();
}

function normalizeStatus(status?: string | null): string {
  return String(status ?? "queued").toLowerCase();
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

export default function AgencyAccountDetailPage() {
  const params = useParams<{ platform: string; accountId: string }>();
  const platform = decodeURIComponent(String(params?.platform ?? "")).trim();
  const accountId = decodeURIComponent(String(params?.accountId ?? "")).trim();

  const [accountMeta, setAccountMeta] = useState<GoogleAccount | null>(null);
  const [metaLoading, setMetaLoading] = useState(true);
  const [metaError, setMetaError] = useState("");

  const [runs, setRuns] = useState<SyncRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [runsError, setRunsError] = useState("");

  const [expandedRunIds, setExpandedRunIds] = useState<Set<string>>(new Set());
  const [chunksByRun, setChunksByRun] = useState<Record<string, SyncChunk[]>>({});
  const [chunksLoadingByRun, setChunksLoadingByRun] = useState<Record<string, boolean>>({});
  const [chunksErrorByRun, setChunksErrorByRun] = useState<Record<string, string>>({});

  const runsSorted = useMemo(() => {
    return [...runs].sort((a, b) => {
      const aTime = new Date(a.created_at ?? a.started_at ?? 0).getTime() || 0;
      const bTime = new Date(b.created_at ?? b.started_at ?? 0).getTime() || 0;
      return bTime - aTime;
    });
  }, [runs]);

  const hasActiveRun = useMemo(() => runsSorted.some((run) => isRunActive(run.status)), [runsSorted]);

  async function loadAccountMeta() {
    if (platform !== "google_ads") {
      setAccountMeta(null);
      setMetaLoading(false);
      setMetaError("");
      return;
    }

    setMetaLoading(true);
    setMetaError("");
    try {
      const payload = await apiRequest<GoogleAccountsResponse>("/clients/accounts/google");
      const normalizedTarget = normalizeAccountId(accountId);
      const found = payload.items.find((item) => normalizeAccountId(item.id) === normalizedTarget);
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
      const payload = await apiRequest<AccountRunsResponse>(
        `/agency/sync-runs/accounts/${encodeURIComponent(platform)}/${encodeURIComponent(accountId)}?limit=100`,
      );
      setRuns(payload.runs ?? []);
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

  useEffect(() => {
    if (!platform || !accountId) return;
    void refreshAll();
  }, [platform, accountId]);

  useEffect(() => {
    if (!hasActiveRun) return;
    const intervalId = window.setInterval(() => {
      void loadRuns();
      for (const jobId of expandedRunIds) {
        void loadChunks(jobId);
      }
    }, 2500);

    return () => window.clearInterval(intervalId);
  }, [expandedRunIds, hasActiveRun]);

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
                <p><span className="font-medium">last_run_status:</span> {accountMeta?.last_run_status ?? "N/A"}</p>
                <p><span className="font-medium">last_run_type:</span> {accountMeta?.last_run_type ?? "N/A"}</p>
                <p><span className="font-medium">last_run_started_at:</span> {formatDate(accountMeta?.last_run_started_at)}</p>
                <p><span className="font-medium">last_run_finished_at:</span> {formatDate(accountMeta?.last_run_finished_at)}</p>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className={`rounded px-2 py-1 font-medium ${accountMeta?.has_active_sync ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-600"}`}>
                  {accountMeta?.has_active_sync ? "Sync activ" : "Fără sync activ"}
                </span>
                {accountMeta?.last_run_status ? (
                  <span className={`rounded px-2 py-1 font-medium ${statusBadge(accountMeta.last_run_status)}`}>
                    Ultimul status: {accountMeta.last_run_status}
                  </span>
                ) : null}
              </div>
              </>
            ) : null}
            {accountMeta?.last_error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">{accountMeta.last_error}</div> : null}
          </section>

          <section className="wm-card p-4">
            <div className="flex items-center justify-between gap-2">
              <div>
                <h3 className="text-base font-semibold text-slate-900">Sync runs</h3>
                {hasActiveRun ? <p className="text-xs text-indigo-700">Auto-refresh activ (există run queued/running).</p> : null}
              </div>
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

            {runsError ? <p className="mt-2 text-sm text-red-600">{runsError}</p> : null}
            {runsLoading ? <p className="mt-2 text-sm text-slate-500">Se încarcă sync runs...</p> : null}
            {!runsLoading && runsSorted.length <= 0 && !runsError ? (
              <p className="mt-2 text-sm text-slate-500">Nu există sync runs pentru acest cont încă.</p>
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
