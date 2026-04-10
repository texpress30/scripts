"use client";

import { X } from "lucide-react";
import type { TreatmentFilter } from "@/lib/hooks/useTreatments";

interface TreatmentFilterRowProps {
  filter: TreatmentFilter;
  onChange: (filter: TreatmentFilter) => void;
  onRemove: () => void;
}

const OPERATORS = [
  { value: "equals", label: "Equals" },
  { value: "contains", label: "Contains" },
  { value: "in_list", label: "In List" },
] as const;

export function TreatmentFilterRow({ filter, onChange, onRemove }: TreatmentFilterRowProps) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        value={filter.field_name}
        onChange={(e) => onChange({ ...filter, field_name: e.target.value })}
        placeholder="Field name"
        className="mcc-input w-32 rounded border px-2 py-1.5 text-sm"
      />
      <select
        value={filter.operator}
        onChange={(e) => onChange({ ...filter, operator: e.target.value as TreatmentFilter["operator"] })}
        className="mcc-input rounded border px-2 py-1.5 text-sm"
      >
        {OPERATORS.map((op) => (
          <option key={op.value} value={op.value}>{op.label}</option>
        ))}
      </select>
      <input
        type="text"
        value={Array.isArray(filter.value) ? filter.value.join(", ") : filter.value}
        onChange={(e) => {
          const val = filter.operator === "in_list"
            ? e.target.value.split(",").map((s) => s.trim())
            : e.target.value;
          onChange({ ...filter, value: val });
        }}
        placeholder={filter.operator === "in_list" ? "val1, val2, val3" : "Value"}
        className="mcc-input flex-1 rounded border px-2 py-1.5 text-sm"
      />
      <button onClick={onRemove} className="rounded p-1 text-slate-400 hover:text-red-500">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
