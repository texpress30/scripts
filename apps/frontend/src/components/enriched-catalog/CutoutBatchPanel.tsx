"use client";

import { useMemo } from "react";
import { AlertCircle, CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { useCutoutBatch, useEnqueueCutoutBatch } from "@/lib/hooks/useCutouts";

/**
 * Cutout batch progress panel.
 *
 * Used in the Enriched Catalog feed-source detail page to let an admin
 * activate background-removal for an existing feed. First click enqueues a
 * bulk run (one Celery task per unique source image, deduped via the
 * image_cutouts table). The hook then polls the batch job every 2s and
 * surfaces a progress bar — similar to how the existing render job UI
 * works, but scoped to BG removal.
 *
 * Safe to mount/unmount freely: the underlying useQuery key is the job_id
 * which is null until the user clicks Start, so the hook idles until then.
 */

interface CutoutBatchPanelProps {
  subaccountId: number;
  feedSourceId: string;
  feedSourceName?: string;
}

export function CutoutBatchPanel({
  subaccountId,
  feedSourceId,
  feedSourceName,
}: CutoutBatchPanelProps) {
  const enqueue = useEnqueueCutoutBatch();
  const job = useCutoutBatch(enqueue.data?.job_id ?? null);

  const status = job.data?.status ?? (enqueue.isPending ? "pending" : null);
  const total = job.data?.total ?? enqueue.data?.enqueued ?? 0;
  const done = job.data?.done ?? 0;
  const failed = job.data?.failed ?? 0;
  const isTerminal = status === "completed" || status === "failed";

  const percent = useMemo(() => {
    if (!total) return 0;
    return Math.round(((done + failed) / total) * 100);
  }, [done, failed, total]);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-indigo-500" />
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Background removal
          </h3>
          {feedSourceName && (
            <span className="text-xs text-slate-500 dark:text-slate-400">
              — {feedSourceName}
            </span>
          )}
        </div>
        {!status && (
          <button
            onClick={() =>
              enqueue.mutate({
                subaccount_id: subaccountId,
                feed_source_id: feedSourceId,
              })
            }
            disabled={enqueue.isPending}
            className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {enqueue.isPending ? "Starting..." : "Process all products"}
          </button>
        )}
      </div>

      <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
        Strips the background from every product photo in this feed and stores
        the transparent PNG under Stocare Media → Cutouts. Identical photos
        are processed only once, so a 30,000-product catalog with 9,000 unique
        images only runs 9,000 rembg passes.
      </p>

      {status && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
              {isTerminal ? (
                status === "failed" ? (
                  <AlertCircle className="h-3.5 w-3.5 text-rose-500" />
                ) : (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                )
              ) : (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-500" />
              )}
              {done + failed} / {total} processed
              {failed > 0 && (
                <span className="text-rose-500">
                  ({failed} failed)
                </span>
              )}
            </span>
            <span className="text-slate-500 dark:text-slate-400">{percent}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
            <div
              className={`h-full rounded-full transition-all ${
                status === "failed"
                  ? "bg-rose-500"
                  : isTerminal
                    ? "bg-emerald-500"
                    : "bg-indigo-500"
              }`}
              style={{ width: `${percent}%` }}
            />
          </div>
          {job.data?.error && (
            <p className="text-xs text-rose-500">{job.data.error}</p>
          )}
        </div>
      )}

      {enqueue.isError && (
        <p className="mt-2 text-xs text-rose-500">
          Failed to start: {(enqueue.error as Error).message}
        </p>
      )}
    </div>
  );
}
