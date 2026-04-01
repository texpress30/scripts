"use client";

import type { FeedImport, FeedImportStatus } from "@/lib/types/feed-management";

const IMPORT_STATUS_STYLES: Record<FeedImportStatus, { label: string; className: string }> = {
  pending: { label: "Pending", className: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400" },
  running: { label: "Running", className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400" },
  completed: { label: "Completed", className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" },
  failed: { label: "Failed", className: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" },
};

function formatDate(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatDuration(start: string, end: string | null): string {
  if (!end) return "...";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (Number.isNaN(ms) || ms < 0) return "-";
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

export function ImportHistoryTable({ imports }: { imports: FeedImport[] }) {
  if (imports.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">
        Nu există importuri pentru această sursă.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-100 text-left text-slate-600 dark:bg-slate-800 dark:text-slate-400">
          <tr>
            <th className="px-4 py-3">Started At</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Products</th>
            <th className="px-4 py-3">Duration</th>
            <th className="px-4 py-3">Errors</th>
          </tr>
        </thead>
        <tbody>
          {imports.map((imp) => {
            const statusConfig = IMPORT_STATUS_STYLES[imp.status];
            return (
              <tr key={imp.id} className="border-t border-slate-100 dark:border-slate-800">
                <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{formatDate(imp.started_at)}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusConfig.className}`}>
                    {imp.status === "running" ? (<span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />) : null}
                    {statusConfig.label}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                  <span title={`Imported: ${imp.products_imported}, Updated: ${imp.products_updated}, Failed: ${imp.products_failed}`}>
                    {imp.products_imported + imp.products_updated}
                    {imp.products_failed > 0 ? (<span className="ml-1 text-red-500">({imp.products_failed} failed)</span>) : null}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{formatDuration(imp.started_at, imp.completed_at)}</td>
                <td className="px-4 py-3">
                  {imp.error_message ? (
                    <span className="text-xs text-red-600 dark:text-red-400" title={imp.error_message}>
                      {imp.error_message.length > 60 ? `${imp.error_message.slice(0, 60)}...` : imp.error_message}
                    </span>
                  ) : (<span className="text-slate-400">-</span>)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
