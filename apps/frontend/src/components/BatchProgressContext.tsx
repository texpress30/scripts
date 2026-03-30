"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { PollBackoff } from "@/lib/poll-backoff";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type BatchProgress = {
  total_runs: number;
  queued: number;
  running: number;
  done: number;
  error: number;
  percent: number;
};

type BatchRun = {
  account_id?: string | null;
  status?: string | null;
};

type BatchStatusResponse = {
  batch_id: string;
  status?: string;
  progress: BatchProgress;
  runs: BatchRun[];
};

export type GlobalBatchState = {
  batchId: string;
  platform: string;
  jobType: "historical_backfill" | null;
  progress: BatchProgress | null;
};

type BatchProgressContextValue = {
  /** Currently active batch (null when idle) */
  activeBatch: GlobalBatchState | null;
  /** Register a new batch — called by the agency-accounts page when a batch starts */
  registerBatch: (batchId: string, platform: string, jobType: "historical_backfill" | null) => void;
};

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const BATCH_STORAGE_PREFIX = "agency-accounts-batch";
const PLATFORMS = ["google_ads", "meta_ads", "tiktok_ads"] as const;

function getBatchStorageKey(platform: string): string {
  return `${BATCH_STORAGE_PREFIX}:${platform}`;
}

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

/* ------------------------------------------------------------------ */
/*  Context                                                            */
/* ------------------------------------------------------------------ */

const BatchProgressContext = createContext<BatchProgressContextValue>({
  activeBatch: null,
  registerBatch: () => {},
});

export function useBatchProgress() {
  return useContext(BatchProgressContext);
}

export { prettyPlatform as batchPrettyPlatform };

/* ------------------------------------------------------------------ */
/*  Provider                                                           */
/* ------------------------------------------------------------------ */

export function BatchProgressProvider({ children }: { children: React.ReactNode }) {
  const [activeBatch, setActiveBatch] = useState<GlobalBatchState | null>(null);
  const pollRef = useRef<{ cancelled: boolean; timeoutId: number | null }>({ cancelled: false, timeoutId: null });

  /* ---------- Rehydrate from sessionStorage on mount ---------- */
  useEffect(() => {
    if (typeof window === "undefined") return;
    for (const platform of PLATFORMS) {
      try {
        const raw = window.sessionStorage.getItem(getBatchStorageKey(platform));
        if (!raw) continue;
        const stored = JSON.parse(raw) as { batchId?: string; platform?: string; jobType?: "historical_backfill" | null };
        if (stored.batchId && stored.platform) {
          setActiveBatch({ batchId: stored.batchId, platform: stored.platform, jobType: stored.jobType ?? "historical_backfill", progress: null });
          return; // only one active batch at a time
        }
      } catch {
        // ignore malformed
      }
    }
  }, []);

  /* ---------- Register a new batch ---------- */
  const registerBatch = useCallback((batchId: string, platform: string, jobType: "historical_backfill" | null) => {
    setActiveBatch({ batchId, platform, jobType, progress: null });
  }, []);

  /* ---------- Poll batch status ---------- */
  useEffect(() => {
    if (!activeBatch?.batchId) return;

    const ctrl = { cancelled: false, timeoutId: null as number | null };
    pollRef.current = ctrl;
    const backoff = new PollBackoff(2500, 15000, 15000);
    let prevJson = "";

    async function poll() {
      if (ctrl.cancelled) return;
      try {
        const payload = await apiRequest<BatchStatusResponse>(`/agency/sync-runs/batch/${activeBatch!.batchId}`);
        if (ctrl.cancelled) return;

        const progressJson = JSON.stringify(payload.progress);
        if (progressJson !== prevJson) {
          backoff.active();
          prevJson = progressJson;
        } else {
          backoff.idle();
        }

        const activeCount = (payload.progress.queued || 0) + (payload.progress.running || 0);
        if (activeCount <= 0) {
          // Batch finished — clean up
          setActiveBatch(null);
          for (const p of PLATFORMS) {
            window.sessionStorage.removeItem(getBatchStorageKey(p));
          }
          return;
        }

        setActiveBatch((prev) => prev ? { ...prev, progress: payload.progress } : null);
      } catch {
        // On error, stop polling
        setActiveBatch(null);
        return;
      }

      if (ctrl.cancelled) return;
      ctrl.timeoutId = window.setTimeout(poll, backoff.nextMs());
    }

    void poll();

    return () => {
      ctrl.cancelled = true;
      if (ctrl.timeoutId !== null) window.clearTimeout(ctrl.timeoutId);
    };
  }, [activeBatch?.batchId]);

  return (
    <BatchProgressContext.Provider value={{ activeBatch, registerBatch }}>
      {children}
    </BatchProgressContext.Provider>
  );
}

/* ------------------------------------------------------------------ */
/*  Global banner component (rendered inside AppShell)                 */
/* ------------------------------------------------------------------ */

export function GlobalBatchBanner() {
  const { activeBatch } = useBatchProgress();
  if (!activeBatch) return null;

  const progress = activeBatch.progress;
  const pct = progress ? Math.max(0, Math.min(100, Number(progress.percent || 0))) : 0;

  return (
    <div className="border-b border-indigo-200 bg-indigo-50 px-4 py-2 text-sm text-indigo-900 dark:border-indigo-800 dark:bg-indigo-950 dark:text-indigo-200 md:px-6">
      <div className="flex items-center gap-3">
        <div className="flex h-5 w-5 items-center justify-center">
          <div className="h-3 w-3 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">
              Download {prettyPlatform(activeBatch.platform)} în progres
              {progress ? ` (${pct.toFixed(0)}%)` : "…"}
            </span>
            {progress ? (
              <span className="shrink-0 text-xs text-indigo-600 dark:text-indigo-400">
                {progress.done}/{progress.total_runs} done · {progress.running} running · {progress.queued} queued
                {progress.error > 0 ? ` · ${progress.error} errors` : ""}
              </span>
            ) : null}
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-indigo-100 dark:bg-indigo-900">
            <div
              className="h-full bg-indigo-600 transition-all duration-500 dark:bg-indigo-400"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
