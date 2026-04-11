"use client";

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, ImageOff, Loader2 } from "lucide-react";

interface CreativeEntry {
  product_id: string;
  product_data: Record<string, unknown>;
  template_id: string | null;
  treatment_id: string | null;
  enriched_image_url: string | null;
  status?: "ready" | "pending" | "failed" | null;
}

interface CreativePreviewGridProps {
  entries: CreativeEntry[];
  isLoading: boolean;
  /** Called whenever the visible page changes — parent can enqueue just this
   *  page's product ids so we don't eagerly render 100k products up front. */
  onVisibleRangeChange?: (visibleIds: string[]) => void;
}

const PAGE_SIZE = 20;

/**
 * Creative preview grid, redesigned for lazy async rendering.
 *
 * The old version assumed every product already had a rendered PNG on S3.
 * The new pipeline dispatches renders asynchronously through Celery, so the
 * grid is expected to:
 *
 * 1. Show skeletons for products that don't have a rendered image yet. The
 *    parent passes entries with ``enriched_image_url === null`` and
 *    ``status === "pending"`` until a worker finishes.
 * 2. Emit the visible range (current page + prefetch) so the parent can
 *    enqueue exactly those products on the ``render_hi`` queue. This is the
 *    reason 100k-product feeds stay cheap — we only pay for the ~20-40
 *    products the user is actually looking at.
 * 3. Gracefully show a broken-image chip for failed renders so users can
 *    retry without blocking the rest of the grid.
 */
export function CreativePreviewGrid({
  entries,
  isLoading,
  onVisibleRangeChange,
}: CreativePreviewGridProps) {
  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil(entries.length / PAGE_SIZE));
  const pageEntries = entries.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const pendingCount = useMemo(
    () => pageEntries.filter((e) => !e.enriched_image_url && e.status !== "failed").length,
    [pageEntries],
  );

  // Let the parent know which product ids are currently on screen so it can
  // trigger async renders exactly for them (plus the next page for prefetch).
  // We do this inside a useMemo-derived effect so the parent isn't called on
  // every render — only when the page boundary actually changes.
  useMemo(() => {
    if (!onVisibleRangeChange) return;
    const idsThisPage = pageEntries.map((e) => e.product_id);
    const nextPage = entries.slice((page + 1) * PAGE_SIZE, (page + 2) * PAGE_SIZE);
    const idsNextPage = nextPage.map((e) => e.product_id);
    onVisibleRangeChange([...idsThisPage, ...idsNextPage]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, entries.length]);

  if (isLoading && entries.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-500 dark:text-slate-400">
        No generated creatives yet. Generate the feed to see previews.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {entries.length} creative{entries.length !== 1 ? "s" : ""}
          </p>
          {pendingCount > 0 && (
            <span className="flex items-center gap-1.5 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
              <Loader2 className="h-3 w-3 animate-spin" />
              {pendingCount} rendering
            </span>
          )}
        </div>
        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="rounded p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {page + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="rounded p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30"
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {pageEntries.map((entry) => (
          <PreviewCard key={entry.product_id} entry={entry} />
        ))}
      </div>
    </div>
  );
}

function PreviewCard({ entry }: { entry: CreativeEntry }) {
  const title = String(entry.product_data?.title || entry.product_id);
  const price =
    entry.product_data && typeof entry.product_data === "object" && "price" in entry.product_data
      ? String((entry.product_data as Record<string, unknown>).price)
      : null;

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <PreviewMedia entry={entry} title={title} />
      <div className="p-3">
        <p className="line-clamp-1 text-xs font-medium text-slate-900 dark:text-slate-100">
          {title}
        </p>
        {price && (
          <p className="text-xs text-slate-500 dark:text-slate-400">{price}</p>
        )}
      </div>
    </div>
  );
}

function PreviewMedia({ entry, title }: { entry: CreativeEntry; title: string }) {
  if (entry.enriched_image_url) {
    return (
      <img
        src={entry.enriched_image_url}
        alt={title}
        className="h-48 w-full bg-slate-50 object-contain dark:bg-slate-900"
        loading="lazy"
      />
    );
  }
  if (entry.status === "failed") {
    return (
      <div className="flex h-48 w-full flex-col items-center justify-center gap-1 bg-rose-50 text-xs text-rose-600 dark:bg-rose-900/10 dark:text-rose-400">
        <ImageOff className="h-5 w-5" />
        <span>Render failed</span>
      </div>
    );
  }
  // Skeleton card for pending renders — the animation gives the user a hint
  // that the preview is being generated in the background.
  return (
    <div className="relative h-48 w-full overflow-hidden bg-slate-50 dark:bg-slate-900">
      <div className="absolute inset-0 animate-pulse bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-800 dark:to-slate-700" />
      <div className="absolute inset-0 flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    </div>
  );
}
