"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { SourceField } from "@/lib/hooks/useMasterFields";

type MappingType = "direct" | "static" | "template";

export type MasterFieldRowValue = {
  target_field: string;
  source_field: string | null;
  mapping_type: MappingType;
  static_value: string | null;
  template_value: string | null;
  is_required: boolean;
  sort_order: number;
};

type Props = {
  targetField: string;
  displayName: string;
  description: string;
  required: boolean;
  category: string;
  fieldType: string;
  suggestedSourceField: string | null;
  sourceFields: SourceField[];
  value: MasterFieldRowValue;
  onChange: (value: MasterFieldRowValue) => void;
};

export function MasterFieldRow({
  targetField,
  displayName,
  required,
  suggestedSourceField,
  sourceFields,
  value,
  onChange,
}: Props) {
  const [showAdvanced, setShowAdvanced] = useState(value.mapping_type !== "direct");

  const currentSourceField = value.source_field ?? "";
  const isSuggested = !value.source_field && !!suggestedSourceField;

  function handleSourceChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const sf = e.target.value || null;
    onChange({ ...value, source_field: sf, mapping_type: "direct", static_value: null, template_value: null });
  }

  function handleMappingTypeChange(mt: MappingType) {
    setShowAdvanced(mt !== "direct");
    onChange({ ...value, mapping_type: mt, source_field: mt === "direct" ? value.source_field : null });
  }

  return (
    <div className="flex items-center bg-white dark:bg-slate-900">
      {/* Col 1: Target field name + badge */}
      <div className="flex w-[220px] shrink-0 items-center gap-2 border-r border-slate-200 px-3 py-2.5 dark:border-slate-700">
        <span className={`h-2 w-2 shrink-0 rounded-full ${required ? "bg-indigo-500" : "bg-slate-300 dark:bg-slate-600"}`} />
        <div className="min-w-0">
          <span className="block truncate text-sm font-medium text-slate-900 dark:text-slate-100">
            {displayName}
          </span>
          <span className="font-mono text-[10px] text-slate-400">{targetField}</span>
        </div>
        {required && (
          <span className="ml-auto shrink-0 rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-900/40 dark:text-red-400">
            Required
          </span>
        )}
      </div>

      {/* Col 2: Mapping type toggle */}
      <div className="flex w-[140px] shrink-0 items-center justify-center gap-1 border-r border-slate-200 px-2 py-2.5 dark:border-slate-700">
        {(["direct", "static", "template"] as MappingType[]).map((mt) => (
          <button
            key={mt}
            type="button"
            onClick={() => handleMappingTypeChange(mt)}
            className={`rounded px-2 py-1 text-[11px] font-medium transition ${
              value.mapping_type === mt
                ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400"
                : "text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
            }`}
          >
            {mt === "direct" ? "Field" : mt === "static" ? "Static" : "Template"}
          </button>
        ))}
      </div>

      {/* Col 3: Source field / value input */}
      <div className="flex min-w-0 flex-1 items-center px-3 py-2.5">
        {value.mapping_type === "direct" && (
          <div className="relative w-full">
            <select
              value={currentSourceField || (isSuggested ? suggestedSourceField ?? "" : "")}
              onChange={handleSourceChange}
              className={`wm-input appearance-none pr-8 ${
                isSuggested ? "border-emerald-300 text-emerald-700 dark:border-emerald-700 dark:text-emerald-400" : ""
              }`}
            >
              <option value="">-- Select source field --</option>
              {sourceFields.map((sf) => (
                <option key={sf.field} value={sf.field}>
                  {sf.field} {sf.sample ? `(${sf.sample.slice(0, 40)})` : ""}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            {isSuggested && (
              <span className="absolute -top-2 right-8 rounded bg-emerald-100 px-1.5 py-0.5 text-[9px] font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400">
                Suggested
              </span>
            )}
          </div>
        )}

        {value.mapping_type === "static" && (
          <input
            type="text"
            value={value.static_value ?? ""}
            onChange={(e) => onChange({ ...value, static_value: e.target.value })}
            placeholder="Enter static value..."
            className="wm-input w-full"
          />
        )}

        {value.mapping_type === "template" && (
          <input
            type="text"
            value={value.template_value ?? ""}
            onChange={(e) => onChange({ ...value, template_value: e.target.value })}
            placeholder="e.g. {{make}} {{model}} {{year}}"
            className="wm-input w-full font-mono text-xs"
          />
        )}
      </div>
    </div>
  );
}
