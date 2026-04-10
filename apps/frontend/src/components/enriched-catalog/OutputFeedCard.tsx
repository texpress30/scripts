"use client";

import { ExternalLink, Play, RefreshCw, Trash2 } from "lucide-react";
import type { OutputFeed } from "@/lib/hooks/useOutputFeeds";

interface OutputFeedCardProps {
  feed: OutputFeed;
  onView: (id: string) => void;
  onGenerate: (id: string) => void;
  onDelete: (id: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400",
  rendering: "bg-amber-100 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400",
  published: "bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400",
  error: "bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400",
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function OutputFeedCard({ feed, onView, onGenerate, onDelete }: OutputFeedCardProps) {
  return (
    <div className="mcc-card rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="mb-3 flex items-start justify-between">
        <div>
          <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">{feed.name}</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Format: {feed.feed_format.toUpperCase()}
          </p>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[feed.status] || STATUS_COLORS.draft}`}>
          {feed.status}
        </span>
      </div>

      {/* Stats */}
      <div className="mb-3 grid grid-cols-2 gap-2 text-xs text-slate-500 dark:text-slate-400">
        <div>
          <span className="font-medium text-slate-700 dark:text-slate-300">{feed.products_count}</span> products
        </div>
        <div>{formatBytes(feed.file_size_bytes)}</div>
        <div>Refresh: {feed.refresh_interval_hours}h</div>
        <div>
          {feed.last_generated_at
            ? `Last: ${new Date(feed.last_generated_at).toLocaleDateString()}`
            : "Never generated"}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={() => onView(feed.id)}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
        >
          <ExternalLink className="h-3.5 w-3.5" /> View
        </button>
        <button
          onClick={() => onGenerate(feed.id)}
          disabled={feed.status === "rendering"}
          className="flex items-center gap-1.5 rounded-md bg-indigo-50 px-3 py-1.5 text-sm text-indigo-600 hover:bg-indigo-100 disabled:opacity-50 dark:bg-indigo-900/20 dark:text-indigo-400 dark:hover:bg-indigo-900/30"
        >
          {feed.status === "rendering" ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
        </button>
        <button
          onClick={() => onDelete(feed.id)}
          className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
