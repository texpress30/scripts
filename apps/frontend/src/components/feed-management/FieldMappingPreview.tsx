"use client";

import { RefreshCw, Loader2, AlertCircle } from "lucide-react";
import type { FieldMappingPreviewRow } from "@/lib/types/feed-management";

export function FieldMappingPreview({
  preview,
  isLoading,
  onRefresh,
}: {
  preview: FieldMappingPreviewRow[];
  isLoading: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="wm-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-700">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Transformation Preview</h3>
        <button
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800"
        >
          {isLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
          Refresh
        </button>
      </div>

      {isLoading && preview.length === 0 ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        </div>
      ) : preview.length === 0 ? (
        <div className="px-4 py-8 text-center text-sm text-slate-400">
          No preview data available. Add mapping rules to see transformations.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50">
                <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400">Product</th>
                <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400">Source Value</th>
                <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400">Transformed</th>
                <th className="w-10 px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {preview.map((row, idx) => (
                <tr key={idx} className="border-b border-slate-100 dark:border-slate-800">
                  <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-300">{row.product_name}</td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-600 dark:text-slate-400">{row.source_value || <span className="italic text-slate-300">empty</span>}</td>
                  <td className={`px-4 py-2 font-mono text-xs ${row.error ? "text-red-600 dark:text-red-400" : "text-emerald-700 dark:text-emerald-400"}`}>
                    {row.error ? row.error : (row.transformed_value || <span className="italic text-slate-300">empty</span>)}
                  </td>
                  <td className="px-4 py-2">
                    {row.error && <AlertCircle className="h-4 w-4 text-red-500" />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
