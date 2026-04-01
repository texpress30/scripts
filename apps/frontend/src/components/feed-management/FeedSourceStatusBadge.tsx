import type { FeedSourceStatus } from "@/lib/types/feed-management";

const STATUS_CONFIG: Record<FeedSourceStatus, { label: string; className: string }> = {
  active: {
    label: "Active",
    className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  },
  syncing: {
    label: "Syncing",
    className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  },
  error: {
    label: "Error",
    className: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  },
  inactive: {
    label: "Inactive",
    className: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  },
};

export function FeedSourceStatusBadge({ status }: { status: FeedSourceStatus }) {
  const config = STATUS_CONFIG[status];

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${config.className}`}
    >
      {status === "syncing" ? (
        <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      ) : null}
      {config.label}
    </span>
  );
}
