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
  attached_client_id?: number | null;
  attached_client_name?: string | null;
  account_timezone?: string | null;
  account_currency?: string | null;
  sync_start_date?: string | null;
  backfill_completed_through?: string | null;
  rolling_synced_through?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
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
  error?: string | null;
  created_at?: string | null;
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

function statusBadge(status?: string | null): string {
  const normalized = (status ?? "").toLowerCase();
  if (normalized === "done") return "bg-emerald-100 text-emerald-700";
  if (normalized === "error") return "bg-red-100 text-red-700";
  if (normalized === "running") return "bg-indigo-100 text-indigo-700";
  return "bg-slate-100 text-slate-700";
}

export default function AgencyAccountDetailPage() {
  const params = useParams<{ platform: string; accountId: string }>();
  const platform = decodeURIComponent(String(params?.platform ?? "")).trim();
  const accountId = decodeURIComponent(String(params?.accountId ?? "")).trim();

  const [accountMeta, setAccountMeta] = useState<GoogleAccount | null>(null);
  const [runs, setRuns] = useState<SyncRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [runsError, setRunsError] = useState("");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [chunks, setChunks] = useState<SyncChunk[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);
  const [chunksError, setChunksError] = useState("");

  const selectedRun = useMemo(() => runs.find((item) => item.job_id === selectedJobId) ?? null, [runs, selectedJobId]);
  const selectedRunActive = ["queued", "running"].includes(String(selectedRun?.status ?? "").toLowerCase());

  async function loadAccountMeta() {
    if (platform !== "google_ads") {
      setAccountMeta(null);
      return;
    }
    const payload = await apiRequest<GoogleAccountsResponse>("/clients/accounts/google");
    const normalizedTarget = normalizeAccountId(accountId);
    const found = payload.items.find((item) => normalizeAccountId(item.id) === normalizedTarget);
    setAccountMeta(found ?? null);
  }

  async function loadRuns() {
    setRunsLoading(true);
    setRunsError("");
    try {
      const payload = await apiRequest<AccountRunsResponse>(`/agency/sync-runs/accounts/${encodeURIComponent(platform)}/${encodeURIComponent(accountId)}?limit=50`);
      setRuns(payload.runs ?? []);
      setSelectedJobId((current) => {
        if (!payload.runs || payload.runs.length <= 0) return null;
        if (current && payload.runs.some((item) => item.job_id === current)) return current;
        return payload.runs[0].job_id;
      });
    } catch {
      setRuns([]);
      setRunsError("Nu am putut încărca log-urile");
      setSelectedJobId(null);
    } finally {
      setRunsLoading(false);
    }
  }

  async function loadChunks(jobId: string) {
    setChunksLoading(true);
    setChunksError("");
    try {
      const payload = await apiRequest<ChunksResponse>(`/agency/sync-runs/${encodeURIComponent(jobId)}/chunks`);
      setChunks(payload.chunks ?? []);
    } catch {
      setChunks([]);
      setChunksError("Nu am putut încărca chunk-urile");
    } finally {
      setChunksLoading(false);
    }
  }

  useEffect(() => {
    if (!platform || !accountId) return;
    void loadAccountMeta();
    void loadRuns();
  }, [platform, accountId]);

  useEffect(() => {
    if (!selectedJobId) {
      setChunks([]);
      return;
    }
    void loadChunks(selectedJobId);
  }, [selectedJobId]);

  return (
    <ProtectedPage>
      <AppShell title="Agency Account Detail">
        <main className="p-6 space-y-4">
          <div>
            <Link href="/agency-accounts" className="text-sm text-indigo-600 hover:underline">← Back to Agency Accounts</Link>
            <h2 className="mt-2 text-lg font-semibold text-slate-900">Account: {accountMeta?.name ?? accountId}</h2>
          </div>

          <section className="wm-card p-4">
            <h3 className="text-base font-semibold text-slate-900">Account status / coverage</h3>
            <div className="mt-3 grid grid-cols-1 gap-2 text-sm text-slate-700 md:grid-cols-2">
              <p><span className="font-medium">Account ID:</span> {accountId}</p>
              <p><span className="font-medium">Platform:</span> {platform}</p>
              <p>
                <span className="font-medium">Attached client:</span>{" "}
                {accountMeta?.attached_client_name ? `${accountMeta.attached_client_name} (#${accountMeta.attached_client_id ?? "-"})` : "-"}
              </p>
              <p><span className="font-medium">Timezone:</span> {accountMeta?.account_timezone ?? "-"}</p>
              <p><span className="font-medium">Currency:</span> {accountMeta?.account_currency ?? "-"}</p>
              <p><span className="font-medium">sync_start_date:</span> {accountMeta?.sync_start_date ?? "-"}</p>
              <p><span className="font-medium">backfill_completed_through:</span> {accountMeta?.backfill_completed_through ?? "-"}</p>
              <p><span className="font-medium">rolling_synced_through:</span> {accountMeta?.rolling_synced_through ?? "-"}</p>
              <p><span className="font-medium">last_success_at:</span> {formatDate(accountMeta?.last_success_at)}</p>
            </div>
            {accountMeta?.last_error ? <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">{accountMeta.last_error}</div> : null}
          </section>

          <section className="wm-card p-4">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-base font-semibold text-slate-900">Sync runs</h3>
              {selectedRunActive ? (
                <button
                  className="wm-btn"
                  onClick={() => {
                    void loadRuns();
                    if (selectedJobId) void loadChunks(selectedJobId);
                  }}
                >
                  Refresh
                </button>
              ) : null}
            </div>
            {runsError ? <p className="mt-2 text-sm text-red-600">{runsError}</p> : null}
            {runsLoading ? <p className="mt-2 text-sm text-slate-500">Se încarcă sync runs...</p> : null}
            {!runsLoading && runs.length <= 0 && !runsError ? <p className="mt-2 text-sm text-slate-500">Nu există sync runs pentru acest cont încă.</p> : null}
            {runs.length > 0 ? (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="text-left text-slate-500">
                    <tr>
                      <th className="px-2 py-2">created_at</th>
                      <th className="px-2 py-2">job_type</th>
                      <th className="px-2 py-2">range</th>
                      <th className="px-2 py-2">status</th>
                      <th className="px-2 py-2">chunks</th>
                      <th className="px-2 py-2">rows_written</th>
                      <th className="px-2 py-2">error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr
                        key={run.job_id}
                        className={`cursor-pointer border-t border-slate-100 hover:bg-slate-50 ${selectedJobId === run.job_id ? "bg-indigo-50" : ""}`}
                        onClick={() => setSelectedJobId(run.job_id)}
                      >
                        <td className="px-2 py-2">{formatDate(run.created_at)}</td>
                        <td className="px-2 py-2">{run.job_type ?? "-"}</td>
                        <td className="px-2 py-2">{run.date_start ?? "-"} → {run.date_end ?? "-"}</td>
                        <td className="px-2 py-2"><span className={`rounded px-2 py-1 text-xs font-medium ${statusBadge(run.status)}`}>{run.status ?? "queued"}</span></td>
                        <td className="px-2 py-2">{run.chunks_done ?? 0}/{run.chunks_total ?? 0}</td>
                        <td className="px-2 py-2">{run.rows_written ?? 0}</td>
                        <td className="max-w-[260px] truncate px-2 py-2" title={run.error ?? ""}>{run.error ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>

          {selectedJobId ? (
            <section className="wm-card p-4">
              <h3 className="text-base font-semibold text-slate-900">Chunks ({selectedJobId})</h3>
              {chunksError ? <p className="mt-2 text-sm text-red-600">{chunksError}</p> : null}
              {chunksLoading ? <p className="mt-2 text-sm text-slate-500">Se încarcă chunks...</p> : null}
              {!chunksLoading && chunks.length <= 0 && !chunksError ? <p className="mt-2 text-sm text-slate-500">Nu există chunk-uri pentru acest run.</p> : null}
              {chunks.length > 0 ? (
                <div className="mt-3 overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead className="text-left text-slate-500">
                      <tr>
                        <th className="px-2 py-2">chunk_index</th>
                        <th className="px-2 py-2">range</th>
                        <th className="px-2 py-2">status</th>
                        <th className="px-2 py-2">attempts</th>
                        <th className="px-2 py-2">rows_written</th>
                        <th className="px-2 py-2">duration_ms</th>
                        <th className="px-2 py-2">error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {chunks.map((chunk) => (
                        <tr key={chunk.chunk_index} className="border-t border-slate-100">
                          <td className="px-2 py-2">{chunk.chunk_index}</td>
                          <td className="px-2 py-2">{chunk.date_start ?? "-"} → {chunk.date_end ?? "-"}</td>
                          <td className="px-2 py-2"><span className={`rounded px-2 py-1 text-xs font-medium ${statusBadge(chunk.status)}`}>{chunk.status ?? "queued"}</span></td>
                          <td className="px-2 py-2">{chunk.attempts ?? 0}</td>
                          <td className="px-2 py-2">{chunk.rows_written ?? 0}</td>
                          <td className="px-2 py-2">{chunk.duration_ms ?? "-"}</td>
                          <td className="max-w-[260px] truncate px-2 py-2" title={chunk.error ?? ""}>{chunk.error ?? "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </section>
          ) : null}
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
