"use client";

import { Loader2 } from "lucide-react";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useOutputFeeds } from "@/lib/hooks/useOutputFeeds";

export default function CreativeLibraryPage() {
  const { selectedId } = useFeedManagement();
  const { feeds, isLoading } = useOutputFeeds(selectedId);

  if (!selectedId) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-500 dark:text-slate-400">
        Select a client to browse the creative library.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  const publishedFeeds = feeds.filter((f) => f.status === "published");

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Creative Library</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Browse all generated creative images across your output feeds.
        </p>
      </div>

      {publishedFeeds.length === 0 ? (
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-slate-200 dark:border-slate-700">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            No published feeds yet. Generate an output feed to see creatives here.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {publishedFeeds.map((feed) => (
            <div key={feed.id} className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">{feed.name}</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {feed.products_count} products | Generated: {feed.last_generated_at ? new Date(feed.last_generated_at).toLocaleString() : "N/A"}
                  </p>
                </div>
                <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/20 dark:text-green-400">
                  {feed.status}
                </span>
              </div>
              <p className="text-xs text-slate-400 dark:text-slate-500">
                View the output feed detail page to preview individual product creatives.
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
