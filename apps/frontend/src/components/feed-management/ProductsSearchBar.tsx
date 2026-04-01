"use client";

import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";

export function ProductsSearchBar({
  search,
  onSearchChange,
  category,
  onCategoryChange,
  categories,
  totalResults,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  category: string;
  onCategoryChange: (value: string) => void;
  categories: string[];
  totalResults: number;
}) {
  const [localSearch, setLocalSearch] = useState(search);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      onSearchChange(localSearch);
    }, 300);
    return () => clearTimeout(timer);
  }, [localSearch, onSearchChange]);

  // Sync external search changes
  useEffect(() => {
    setLocalSearch(search);
  }, [search]);

  const hasFilters = search.length > 0 || category.length > 0;

  return (
    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-1 gap-3">
        <div className="relative flex-1 sm:max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            placeholder="Cauta produse..."
            className="wm-input pl-9"
          />
        </div>
        <select
          value={category}
          onChange={(e) => onCategoryChange(e.target.value)}
          className="wm-input w-auto min-w-[140px]"
        >
          <option value="">Toate categoriile</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
        {hasFilters ? (
          <button
            type="button"
            onClick={() => { setLocalSearch(""); onSearchChange(""); onCategoryChange(""); }}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            <X className="h-3.5 w-3.5" />
            Clear
          </button>
        ) : null}
      </div>
      <p className="text-sm text-slate-500 dark:text-slate-400">
        {totalResults.toLocaleString()} produs{totalResults !== 1 ? "e" : ""}
      </p>
    </div>
  );
}
