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
  description,
  required,
  fieldType,
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
    <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900 sm:flex-row sm:items-center sm:gap-4">
      {/* Left: target field info */}
      <div className="flex min-w-[180px] items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${required ? "bg-indigo-500" : "bg-slate-300 dark:bg-slate-600"}`} />
        <div>
          <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{displayName}</span>
          <span className="ml-1.5 font-mono text-[10px] text-slate-400">{targetField}</span>
          {required && (
            <span className="ml-1.5 rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-900/40 dark:text-red-400">
              Required
            </span>
          )}
        </div>
      </div>

      {/* Right: mapping config */}
      <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
        {/* Mapping type tabs */}
        <div className="flex gap-1">
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

        {/* Value input based on type */}
        <div className="flex-1">
          {value.mapping_type === "direct" && (
            <div className="relative">
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
              className="wm-input"
            />
          )}

          {value.mapping_type === "template" && (
            <input
              type="text"
              value={value.template_value ?? ""}
              onChange={(e) => onChange({ ...value, template_value: e.target.value })}
              placeholder="e.g. {{make}} {{model}} {{year}}"
              className="wm-input font-mono text-xs"
            />
          )}
        </div>
      </div>
    </div>
  );
}
