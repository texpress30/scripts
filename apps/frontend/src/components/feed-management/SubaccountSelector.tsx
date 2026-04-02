"use client";

import { Building2, Loader2 } from "lucide-react";
import type { SubaccountOption } from "@/lib/hooks/useFeedSubaccount";

export function SubaccountSelector({
  clients,
  selectedId,
  onSelect,
  isLoading,
}: {
  clients: SubaccountOption[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading clients...
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-400">
        <Building2 className="h-4 w-4" />
        Client:
      </div>
      <select
        value={selectedId ?? ""}
        onChange={(e) => {
          const val = Number(e.target.value);
          if (val > 0) onSelect(val);
        }}
        className="wm-input max-w-xs text-sm"
      >
        <option value="">-- Selectează un client --</option>
        {clients.map((c) => (
          <option key={c.id} value={c.id}>{c.name}</option>
        ))}
      </select>
    </div>
  );
}
