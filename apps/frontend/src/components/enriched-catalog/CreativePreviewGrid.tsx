"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";

interface CreativeEntry {
  product_id: string;
  product_data: Record<string, unknown>;
  template_id: string | null;
  treatment_id: string | null;
  enriched_image_url: string | null;
}

interface CreativePreviewGridProps {
  entries: CreativeEntry[];
  isLoading: boolean;
}

const PAGE_SIZE = 20;

export function CreativePreviewGrid({ entries, isLoading }: CreativePreviewGridProps) {
  const [page, setPage] = useState(0);
  const totalPages = Math.ceil(entries.length / PAGE_SIZE);
  const pageEntries = entries.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  if (isLoading) {
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
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {entries.length} creative{entries.length !== 1 ? "s" : ""} generated
        </p>
        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="rounded p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30"
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
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {pageEntries.map((entry) => (
          <div
            key={entry.product_id}
            className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800"
          >
            {entry.enriched_image_url ? (
              <img
                src={entry.enriched_image_url}
                alt={String(entry.product_data?.title || entry.product_id)}
                className="h-48 w-full object-contain bg-slate-50 dark:bg-slate-900"
                loading="lazy"
              />
            ) : (
              <div className="flex h-48 items-center justify-center bg-slate-50 text-xs text-slate-400 dark:bg-slate-900">
                No image generated
              </div>
            )}
            <div className="p-3">
              <p className="text-xs font-medium text-slate-900 dark:text-slate-100 line-clamp-1">
                {String(entry.product_data?.title || entry.product_id)}
              </p>
              {"price" in (entry.product_data || {}) && (
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {String((entry.product_data as Record<string, unknown>).price)}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
