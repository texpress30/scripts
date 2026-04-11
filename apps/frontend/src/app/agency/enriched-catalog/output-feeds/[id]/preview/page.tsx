"use client";

import { useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useOutputFeed, useRenderStatus } from "@/lib/hooks/useOutputFeeds";
import { CreativePreviewGrid } from "@/components/enriched-catalog/CreativePreviewGrid";
import { apiRequest } from "@/lib/api";

export default function OutputFeedPreviewPage() {
  const params = useParams();
  const router = useRouter();
  const feedId = params.id as string;

  const { data: feed, isLoading: feedLoading } = useOutputFeed(feedId);
  const { data: renderStatus, isLoading: renderLoading } = useRenderStatus(feedId, true);

  if (feedLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (!feed) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-500">
        Output feed not found.
      </div>
    );
  }

  // Build entries from render status if available
  const entries = (renderStatus as unknown as { entries?: unknown[] })?.entries ?? [];

  // Lazy dispatch: when the grid scrolls to a new page it tells us the
  // product_ids currently on screen (plus one page of prefetch). We turn
  // that into a POST /render/page call which checks the
  // template_render_results cache and only enqueues Celery tasks for the
  // stale entries. For a 100k-product feed we therefore only ever render
  // the ~40 products the user is actually looking at.
  //
  // The dispatchedIdsRef guard keeps us from re-enqueueing the same product
  // ids every time the React state ticks — we only fire when the set of
  // visible ids actually changes.
  const dispatchedIdsRef = useRef<string>("");
  const handleVisibleRangeChange = useCallback(
    async (visibleIds: string[]) => {
      if (!feedId || visibleIds.length === 0) return;
      const signature = visibleIds.slice().sort().join("|");
      if (signature === dispatchedIdsRef.current) return;
      dispatchedIdsRef.current = signature;
      try {
        await apiRequest(`/creative/output-feeds/${feedId}/render/page`, {
          method: "POST",
          body: JSON.stringify({ product_ids: visibleIds, priority: "hi" }),
        });
      } catch (err) {
        // Best-effort: the grid will simply show skeletons for longer if
        // dispatch fails. Surface in the console so we can spot systemic
        // failures during rollout.
        console.warn("render_page_dispatch_failed", err);
      }
    },
    [feedId],
  );

  return (
    <div>
      <button
        onClick={() => router.push(`/agency/enriched-catalog/output-feeds/${feedId}`)}
        className="mb-4 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
      >
        <ArrowLeft className="h-4 w-4" /> Back to {feed.name}
      </button>

      <h2 className="mb-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
        Creative Preview — {feed.name}
      </h2>
      <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
        Preview generated creative images for each product in this feed.
      </p>

      {renderStatus && renderStatus.status !== "no_jobs" && renderStatus.status !== "completed" && (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-900/10">
          <p className="text-sm text-amber-700 dark:text-amber-400">
            Render in progress: {(renderStatus as unknown as { rendered_products: number }).rendered_products} / {(renderStatus as unknown as { total_products: number }).total_products} products
          </p>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-amber-100 dark:bg-amber-900/20">
            <div
              className="h-full rounded-full bg-amber-500 transition-all"
              style={{
                width: `${
                  (renderStatus as unknown as { total_products: number }).total_products > 0
                    ? ((renderStatus as unknown as { rendered_products: number }).rendered_products / (renderStatus as unknown as { total_products: number }).total_products) * 100
                    : 0
                }%`,
              }}
            />
          </div>
        </div>
      )}

      <CreativePreviewGrid
        entries={entries as { product_id: string; product_data: Record<string, unknown>; template_id: string | null; treatment_id: string | null; enriched_image_url: string | null }[]}
        isLoading={renderLoading}
        onVisibleRangeChange={handleVisibleRangeChange}
      />
    </div>
  );
}
