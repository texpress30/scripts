"use client";

import { useEffect, useState } from "react";
import {
  Filter as FilterIcon,
  FileText,
  RefreshCw,
  Trash2,
  PlusCircle,
  X,
  Info,
} from "lucide-react";
import type { ColumnDef } from "@/lib/hooks/useChannelProducts";

// ---------------------------------------------------------------------------
// Types + pure helpers (exported so page.tsx can reuse `applyFeedFilters` to
// drive the SKU counter and product-row filtering outside the modal).
// ---------------------------------------------------------------------------

export type FeedFilterOperator =
  | "equals"
  | "not_equal"
  | "contains"
  | "not_contain"
  | "greater_than"
  | "less_than"
  | "set"
  | "not_set";

export type FeedFilter = {
  id: string;
  column: string;
  operator: FeedFilterOperator;
  value: string;
};

const OPERATORS: { key: FeedFilterOperator; label: string }[] = [
  { key: "equals", label: "Equals" },
  { key: "not_equal", label: "Not equal" },
  { key: "contains", label: "Contains" },
  { key: "not_contain", label: "Not contain" },
  { key: "greater_than", label: "Greater than" },
  { key: "less_than", label: "Less than" },
  { key: "set", label: "Set" },
  { key: "not_set", label: "Not set" },
];

function operatorNeedsValue(op: FeedFilterOperator): boolean {
  return op !== "set" && op !== "not_set";
}

function isFilterComplete(f: FeedFilter): boolean {
  if (!f.column) return false;
  if (operatorNeedsValue(f.operator) && f.value.trim() === "") return false;
  return true;
}

function evaluate(product: Record<string, unknown>, filter: FeedFilter): boolean {
  const raw = product[filter.column];
  const str = raw == null ? "" : String(raw);
  // String comparisons are case-insensitive and trim-tolerant, matching what
  // users expect when a feed column carries inconsistent casing (e.g. `SUV`
  // vs `suv`). Numeric operators coerce to Number separately.
  const strNorm = str.trim().toLowerCase();
  const val = filter.value;
  const valNorm = val.trim().toLowerCase();
  switch (filter.operator) {
    case "equals":
      return strNorm === valNorm;
    case "not_equal":
      return strNorm !== valNorm;
    case "contains":
      return strNorm.includes(valNorm);
    case "not_contain":
      return !strNorm.includes(valNorm);
    case "greater_than": {
      const a = Number(str);
      const b = Number(val);
      return Number.isFinite(a) && Number.isFinite(b) && a > b;
    }
    case "less_than": {
      const a = Number(str);
      const b = Number(val);
      return Number.isFinite(a) && Number.isFinite(b) && a < b;
    }
    case "set":
      return str.trim() !== "";
    case "not_set":
      return str.trim() === "";
    default:
      return true;
  }
}

/**
 * Apply a list of Enriched Feed filters to a set of raw feed rows. Only
 * complete filters (column + value when required) are evaluated; incomplete
 * rows are ignored so the user can draft a filter without losing all rows.
 */
export function applyFeedFilters(
  products: Record<string, unknown>[],
  filters: FeedFilter[],
): Record<string, unknown>[] {
  const complete = filters.filter(isFilterComplete);
  if (complete.length === 0) return products;
  return products.filter((product) => complete.every((f) => evaluate(product, f)));
}

export function countCompleteFilters(filters: FeedFilter[]): number {
  return filters.filter(isFilterComplete).length;
}

function newEmptyFilter(): FeedFilter {
  return { id: crypto.randomUUID(), column: "", operator: "equals", value: "" };
}

// ---------------------------------------------------------------------------
// Modal component
// ---------------------------------------------------------------------------

type Props = {
  open: boolean;
  onClose: () => void;
  columns: ColumnDef[];
  productRowsCount: number;
  initialFilters: FeedFilter[];
  onApply: (filters: FeedFilter[]) => void;
};

export function EnrichedFeedFiltersModal({
  open,
  onClose,
  columns,
  productRowsCount,
  initialFilters,
  onApply,
}: Props) {
  const [drafts, setDrafts] = useState<FeedFilter[]>(initialFilters);

  // Re-seed the draft list whenever the modal opens so the user can cancel
  // with the X / Close button and discard their in-flight changes.
  useEffect(() => {
    if (open) setDrafts(initialFilters);
  }, [open, initialFilters]);

  if (!open) return null;

  const completeCount = countCompleteFilters(drafts);
  const canApply = completeCount > 0;

  const identifierColumns = columns.filter((c) => c.key === "id");
  const otherColumns = columns.filter((c) => c.key !== "id");

  const updateFilter = (id: string, patch: Partial<FeedFilter>) => {
    setDrafts((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  };

  const removeFilter = (id: string) => {
    setDrafts((prev) => prev.filter((f) => f.id !== id));
  };

  const addFilter = () => {
    setDrafts((prev) => [...prev, newEmptyFilter()]);
  };

  const clearAll = () => {
    setDrafts([]);
  };

  const refresh = () => {
    // Refresh is purely cosmetic in V1 — filters are evaluated live whenever
    // `drafts` changes, so re-applying the current list is a no-op. We still
    // wire the button so the UI matches the reference and the click has an
    // effect users can confirm (the button briefly flashes via the `:active`
    // state).
    setDrafts((prev) => [...prev]);
  };

  const handleApply = () => {
    if (!canApply) return;
    onApply(drafts.filter(isFilterComplete));
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="enriched-feed-filters-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-2xl rounded-xl border border-slate-700 bg-slate-800 text-slate-100 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 px-6 pt-5 pb-4">
          <div>
            <h2 id="enriched-feed-filters-title" className="text-lg font-semibold text-white">
              Enriched Feed Filters
            </h2>
            <p className="mt-0.5 text-xs text-slate-400">Apply filters to the Enriched Feed</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-700 hover:text-white"
            aria-label="Close filters"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Status bar */}
        <div className="flex items-center gap-3 border-b border-slate-700/80 px-6 pb-3 text-xs">
          <div className="flex items-center gap-1.5 text-slate-200">
            <FilterIcon className="h-3.5 w-3.5 text-indigo-400" />
            <span className="font-medium">
              {completeCount} Filter{completeCount === 1 ? "" : "(s)"}
            </span>
          </div>
          <span className="h-3 w-px bg-slate-600" />
          <div className="flex items-center gap-1.5 text-slate-200">
            <FileText className="h-3.5 w-3.5 text-slate-400" />
            <span className="font-medium">{productRowsCount} Product Rows</span>
          </div>
          <span className="h-3 w-px bg-slate-600" />
          <button
            type="button"
            onClick={refresh}
            className="rounded p-1 text-slate-400 hover:bg-slate-700 hover:text-white"
            title="Refresh filters"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={clearAll}
            disabled={drafts.length === 0}
            className="ml-auto text-slate-300 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            Clear All
          </button>
        </div>

        {/* Filter rows */}
        <div className="space-y-3 px-6 py-5">
          {drafts.length === 0 ? (
            <p className="py-2 text-center text-xs text-slate-500">
              No filters yet — click &quot;Add Filter&quot; to create one.
            </p>
          ) : (
            drafts.map((filter) => (
              <div key={filter.id} className="flex items-center gap-3">
                {/* Column select */}
                <select
                  value={filter.column}
                  onChange={(e) => updateFilter(filter.id, { column: e.target.value })}
                  className="min-w-0 flex-1 rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                >
                  <option value="">—</option>
                  {identifierColumns.length > 0 && (
                    <optgroup label="IDENTIFIERS">
                      {identifierColumns.map((col) => (
                        <option key={col.key} value={col.key}>
                          {col.key}
                        </option>
                      ))}
                    </optgroup>
                  )}
                  {otherColumns.length > 0 && (
                    <optgroup label="OTHERS">
                      {otherColumns.map((col) => (
                        <option key={col.key} value={col.key}>
                          {col.key}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>

                {/* Operator select */}
                <select
                  value={filter.operator}
                  onChange={(e) =>
                    updateFilter(filter.id, { operator: e.target.value as FeedFilterOperator })
                  }
                  className="w-32 shrink-0 rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                >
                  {OPERATORS.map((op) => (
                    <option key={op.key} value={op.key}>
                      {op.label}
                    </option>
                  ))}
                </select>

                {/* Value input */}
                <div className="relative w-44 shrink-0">
                  <input
                    type="text"
                    value={filter.value}
                    onChange={(e) => updateFilter(filter.id, { value: e.target.value })}
                    disabled={!operatorNeedsValue(filter.operator)}
                    placeholder="Column Value"
                    className="w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 pr-8 text-sm text-slate-100 placeholder:text-slate-500 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  <Info
                    className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500"
                    aria-hidden="true"
                  />
                </div>

                {/* Delete */}
                <button
                  type="button"
                  onClick={() => removeFilter(filter.id)}
                  className="shrink-0 rounded p-1.5 text-slate-400 hover:bg-slate-700 hover:text-red-400"
                  aria-label="Delete filter"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))
          )}

          <button
            type="button"
            onClick={addFilter}
            className="flex items-center gap-1.5 text-sm text-slate-300 hover:text-white"
          >
            <PlusCircle className="h-4 w-4" />
            Add Filter
          </button>
        </div>

        {/* Footer */}
        <div className="flex flex-col items-stretch gap-2 border-t border-slate-700/80 px-6 pb-5 pt-4">
          <button
            type="button"
            onClick={handleApply}
            disabled={!canApply}
            className={`w-full rounded-md py-2.5 text-sm font-medium transition ${
              canApply
                ? "bg-teal-500 text-white hover:bg-teal-400"
                : "bg-slate-700 text-slate-500"
            } disabled:cursor-not-allowed`}
          >
            Apply
          </button>
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-md py-1.5 text-sm text-slate-300 hover:text-white"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
