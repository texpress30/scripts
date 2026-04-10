"use client";

import { useRouter } from "next/navigation";
import { Plus, Loader2 } from "lucide-react";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useOutputFeeds } from "@/lib/hooks/useOutputFeeds";
import { OutputFeedCard } from "@/components/enriched-catalog/OutputFeedCard";

export default function OutputFeedsPage() {
  const router = useRouter();
  const { selectedId } = useFeedManagement();
  const { feeds, isLoading, generate, remove } = useOutputFeeds(selectedId);

  const handleView = (id: string) => {
    router.push(`/agency/enriched-catalog/output-feeds/${id}`);
  };

  const handleGenerate = async (id: string) => {
    try {
      await generate(id);
    } catch (err) {
      console.error("Failed to generate feed:", err);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm("Are you sure you want to delete this output feed?")) {
      await remove(id);
    }
  };

  if (!selectedId) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-500 dark:text-slate-400">
        Select a client to manage output feeds.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Output Feeds</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Create enriched feeds with generated creative images for ad platforms.
          </p>
        </div>
        <button
          onClick={() => router.push("/agency/enriched-catalog/output-feeds/new")}
          className="wm-btn-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white"
        >
          <Plus className="h-4 w-4" /> New Output Feed
        </button>
      </div>

      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : feeds.length === 0 ? (
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-slate-200 dark:border-slate-700">
          <p className="text-sm text-slate-500 dark:text-slate-400">No output feeds yet.</p>
          <button
            onClick={() => router.push("/agency/enriched-catalog/output-feeds/new")}
            className="wm-btn-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white"
          >
            <Plus className="h-4 w-4" /> Create your first output feed
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {feeds.map((feed) => (
            <OutputFeedCard
              key={feed.id}
              feed={feed}
              onView={handleView}
              onGenerate={handleGenerate}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}
